"""Pruebas de fase 2 con datos sintéticos: no requieren internet ni Earth Engine."""

import csv
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from chaco_monitor.labels import IGNORE, change_label, remap_mapbiomas
from chaco_monitor.patches import assign_blocks, iter_patches, normalize_features
from chaco_monitor.zones import load_zones, utm_epsg, window_around
from chaco_monitor.contracts import bbox_area_km2

ROOT = Path(__file__).resolve().parents[1]


def test_zones_load_and_utm():
    zones = load_zones()
    assert set(zones) == {"A_boqueron", "B_alto_paraguay", "C_presidente_hayes"}
    assert utm_epsg(-60.58, -21.8) == 32720   # Boquerón: zona 20S
    assert utm_epsg(-59.40, -20.35) == 32721  # Alto Paraguay: zona 21S


def test_window_has_requested_area():
    window = window_around(load_zones()["A_boqueron"], 10)
    assert 98 < bbox_area_km2(window) < 102


def test_mapbiomas_remap():
    codes = np.array([3, 4, 6, 45, 15, 18, 0, 27, 12])
    assert remap_mapbiomas(codes).tolist() == [1, 1, 1, 255, 0, 0, 255, 255, 0]
    valid = np.array([True] * 8 + [False])
    assert remap_mapbiomas(codes, valid)[-1] == IGNORE


def test_change_label():
    y1 = np.array([1, 1, 0, 0, 255, 1])
    y2 = np.array([0, 1, 1, 0, 1, 255])
    assert change_label(y1, y2).tolist() == [1, 0, 0, 0, 255, 255]


def test_block_split_is_reproducible_and_complete():
    a = assign_blocks(3, 3, seed=42)
    assert a == assign_blocks(3, 3, seed=42)
    assert set(a.values()) == {"train", "val", "test"}
    assert len(a) == 9


def test_patches_never_cross_blocks():
    for br, bc, r, c in iter_patches(600, 520, 256, 128):
        assert r // 256 == br and c // 256 == bc
        assert r + 128 <= 512 and c + 128 <= 512
    with pytest.raises(ValueError):
        list(iter_patches(256, 256, 250, 128))


def test_normalize_features_masks_nodata():
    stack = np.full((5, 2, 2), 5000, dtype=np.int16)
    stack[0, 0, 0] = -9999
    x, valid = normalize_features(stack)
    assert not valid[0, 0] and valid[1, 1]
    assert x[0, 1, 1] == pytest.approx(0.5)


def _synthetic(path: Path, codes: np.ndarray):
    h, w = codes.shape
    data = np.zeros((7, h, w), dtype=np.int16)
    data[:4] = 1500
    data[4] = 7000
    data[5] = 1
    data[6] = codes
    with rasterio.open(path, "w", driver="GTiff", height=h, width=w, count=7, dtype="int16",
                       crs="EPSG:32720", transform=from_origin(500000, 7600000, 10, 10)) as dst:
        dst.write(data)


def test_make_patches_end_to_end(tmp_path):
    src = tmp_path / "gee"
    src.mkdir()
    t1 = np.full((512, 512), 3, dtype=np.int16)         # todo bosque cerrado
    t2 = t1.copy()
    t2[:128, :128] = 15                                  # desmonte -> pastura
    _synthetic(src / "Z_2022.tif", t1)
    _synthetic(src / "Z_2023.tif", t2)
    out = tmp_path / "patches"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "fase2_make_patches.py"),
                    "--zones", "Z", "--src", str(src), "--out", str(out)], check=True)
    rows = list(csv.DictReader((out / "index.csv").open(encoding="utf-8")))
    assert len(rows) == 16
    blocks = {}
    for row in rows:                                     # un bloque -> un solo split
        blocks.setdefault(row["block"], set()).add(row["split"])
    assert all(len(s) == 1 for s in blocks.values())
    first = next(r for r in rows if r["row"] == "0" and r["col"] == "0")
    assert int(first["loss_px"]) == 128 * 128
    sample = np.load(out / first["path"])
    assert sample["x_t1"].shape == (5, 128, 128) and sample["change"].max() == 1
