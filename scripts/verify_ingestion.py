"""Verifica archivos descargados, grillas, bandas, nodata y máscaras sin internet."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio


def sha256(path: Path) -> str:
    """Hash de integridad para detectar transferencias incompletas."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(root: Path) -> dict:
    """Falla ante cualquier inconsistencia; no se necesitan imágenes remotas."""
    manifest = json.loads((root / "manifest.json").read_text())
    checks, grids, masks = 0, {}, {}
    paths = manifest["footprints"] + manifest["zone_pairs"]
    paths += [file for row in manifest["records"] for file in row["files"]]
    for file in paths:
        path = root / file["path"]
        if not path.is_file() or sha256(path) != file["sha256"]:
            raise ValueError(f"Archivo ausente o checksum incorrecto: {path}")
        checks += 1
    for row in manifest["records"]:
        folder = root / row["zone"] / row["datetime"][:10]
        with rasterio.open(folder / "stack.tif") as src:
            stack = src.read()
            grid = (str(src.crs), tuple(src.transform), src.shape)
            assert src.count == 5 and src.descriptions == tuple(manifest["band_order"])
            assert src.res == (10, 10) and src.nodata == -9999
            assert grid[0] == row["crs"] and list(src.shape) == row["shape"]
        for file in ("scl.tif", "valid.tif"):
            with rasterio.open(folder / file) as src:
                assert (str(src.crs), tuple(src.transform), src.shape) == grid
        if row["zone"] in grids:
            assert grid == grids[row["zone"]], "Fechas con grillas distintas"
        grids[row["zone"]] = grid
        with rasterio.open(folder / "valid.tif") as src:
            raw_valid = src.read(1)
            assert set(np.unique(raw_valid)).issubset({0, 1})
            valid = raw_valid.astype(bool)
        assert int(valid.sum()) == row["valid_pixels"]
        assert np.all(np.isfinite(stack[:, valid]))
        assert np.all((stack[:4, valid] >= 0) & (stack[:4, valid] <= 1))
        assert np.all((stack[4, valid] >= -1) & (stack[4, valid] <= 1))
        assert np.all(stack[:, ~valid] == -9999)
        expected = (stack[3, valid]-stack[2, valid])/(stack[3, valid]+stack[2, valid])
        np.testing.assert_allclose(stack[4, valid], expected, atol=1e-6)
        masks[(row["zone"], row["role"])] = valid
        checks += 10
    for pair in manifest["zone_pairs"]:
        roles = ("historical_2022_0","historical_2023_1") if pair["period"]=="historical" else (
            "recent_2026_2","recent_2026_3")
        expected = masks[(pair["zone"],roles[0])] & masks[(pair["zone"],roles[1])]
        with rasterio.open(root / pair["path"]) as src:
            np.testing.assert_array_equal(src.read(1), expected)
        assert int(expected.sum()) == pair["joint_valid_pixels"]
        checks += 2
    result = {"status":"passed", "records":len(manifest["records"]),
              "zones":sorted(grids), "file_checksums_verified":len(paths),
              "checks_count":checks, "network_required":False,
              "labels_present":False, "model_present":False}
    (root / "verification.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.root),indent=2))
