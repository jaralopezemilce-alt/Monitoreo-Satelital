"""Pruebas de fase 2 con datos sintéticos: no requieren internet ni Earth Engine."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from chaco_monitor.labels import IGNORE, change_label, remap_mapbiomas, unknown_codes
from chaco_monitor.patches import assign_blocks, iter_patches, prepare_features
from chaco_monitor.zones import load_zones, utm_epsg

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fase2_make_patches.py"
LEFT, TOP = 744980, 7591690


def test_zones_load_and_utm():
    assert {"A_boqueron", "B_alto_paraguay"} <= set(load_zones())
    assert utm_epsg(-60.58, -21.8) == 32720   # Boquerón: zona 20S
    assert utm_epsg(-59.40, -20.35) == 32721  # Alto Paraguay: zona 21S


def test_mapbiomas_remap():
    codes = np.array([3, 4, 6, 45, 15, 18, 0, 27, 12])
    assert remap_mapbiomas(codes).tolist() == [1, 1, 1, 255, 0, 0, 255, 255, 0]
    valid = np.array([True] * 8 + [False])
    assert remap_mapbiomas(codes, valid)[-1] == IGNORE


def test_nodata_and_unknown_codes_are_never_non_forest():
    """Regresión: 255 (nodata de la exportación) y códigos no listados -> ignorar."""
    codes = np.array([255, 99, 200, 1, 15])
    assert remap_mapbiomas(codes).tolist() == [255, 255, 255, 255, 0]
    assert unknown_codes(codes) == {1: 1, 99: 1, 200: 1}


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


def test_prepare_features_masks_nodata_and_invalid():
    stack = np.full((5, 2, 2), 0.3, dtype=np.float32)
    stack[0, 0, 0] = -9999
    valid_tif = np.array([[1, 1], [0, 1]], dtype=np.uint8)
    x, valid = prepare_features(stack, valid_tif)
    assert valid.tolist() == [[False, True], [False, True]]
    assert x[0, 0, 0] == 0 and x[0, 1, 1] == pytest.approx(0.3)


# ---------- prueba de punta a punta con un paquete sintético ----------

def _write(path, data, dtype, transform, nodata):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = data if data.ndim == 3 else data[None]
    with rasterio.open(path, "w", driver="GTiff", height=data.shape[1], width=data.shape[2],
                       count=data.shape[0], dtype=dtype, crs="EPSG:32720",
                       transform=transform, nodata=nodata) as dst:
        dst.write(data.astype(dtype))


def _package(tmp_path, size=768):
    inputs, labels = tmp_path / "inputs", tmp_path / "labels"
    t10 = from_origin(LEFT, TOP, 10, 10)
    t30 = from_origin(LEFT, TOP, 30, 30)
    records = []
    for role, dt in (("historical_2022_0", "2022-10-21T14:18:51Z"),
                     ("historical_2023_1", "2023-09-21T14:18:52Z")):
        stack = np.full((5, size, size), 0.2, dtype=np.float32)
        stack[4] = 0.7
        folder = inputs / "Z" / dt[:10]
        _write(folder / "stack.tif", stack, "float32", t10, -9999)
        _write(folder / "valid.tif", np.ones((size, size)), "uint8", t10, None)
        records.append({"zone": "Z", "role": role, "datetime": dt})
    (inputs / "manifest.json").write_text(json.dumps({"records": records}))
    n30 = size // 3
    y22 = np.full((n30, n30), 3, dtype=np.uint8)            # bosque cerrado
    y23 = y22.copy()
    y23[:n30 // 6, :n30 // 6] = 15                           # desmonte -> pastura
    y23[-n30 // 6:, -n30 // 6:] = 255                        # nodata en la exportación
    _write(labels / "Z_mapbiomas_c5_v2_2022.tif", y22, "uint8", t30, 255)
    _write(labels / "Z_mapbiomas_c5_v2_2023.tif", y23, "uint8", t30, 255)
    return inputs, labels


def _run(inputs, labels, out, *extra, check=True):
    return subprocess.run([sys.executable, str(SCRIPT), "--inputs", str(inputs),
                           "--labels", str(labels), "--out", str(out), *extra],
                          check=check, capture_output=True, text=True)


def test_make_patches_end_to_end(tmp_path):
    inputs, labels = _package(tmp_path)
    out = tmp_path / "dataset"
    _run(inputs, labels, out)
    rows = list(csv.DictReader((out / "index.csv").open(encoding="utf-8")))
    assert len(rows) == 35          # 36 parches menos 1 dominado por nodata
    blocks = {}
    for row in rows:                # un bloque -> un solo split
        blocks.setdefault(row["block"], set()).add(row["split"])
    assert all(len(s) == 1 for s in blocks.values())
    first = next(r for r in rows if r["row"] == "0" and r["col"] == "0")
    assert int(first["loss_px"]) == 126 * 126   # 42 celdas de 30 m = 126 px de 10 m
    sample = np.load(out / first["path"])
    assert sample["x_t1"].shape == (5, 128, 128) and sample["change"].max() == 1
    # el parche con nodata 255 en 2023 nunca aparece como no bosque
    assert not (out / "patches" / "Z_2022_2023_r0640_c0640.npz").exists()
    for row in rows:
        y2 = np.load(out / row["path"])["y_t2"]
        assert set(np.unique(y2)) <= {0, 1, 255}


def test_regenerating_with_other_seed_leaves_no_duplicates(tmp_path):
    """Regresión: otra semilla no debe dejar parches viejos en otro split."""
    inputs, labels = _package(tmp_path)
    out = tmp_path / "dataset"
    _run(inputs, labels, out, "--seed", "42")
    failed = _run(inputs, labels, out, "--seed", "7", check=False)
    assert failed.returncode != 0 and "--overwrite" in failed.stderr
    _run(inputs, labels, out, "--seed", "7", "--overwrite")
    rows = list(csv.DictReader((out / "index.csv").open(encoding="utf-8")))
    files = sorted(p.name for p in (out / "patches").glob("*.npz"))
    assert len(files) == len(rows) == len({r["patch_id"] for r in rows})
    assert files == sorted(Path(r["path"]).name for r in rows)
