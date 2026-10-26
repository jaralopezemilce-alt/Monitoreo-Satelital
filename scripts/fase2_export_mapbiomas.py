"""Fase 2a: descarga las etiquetas MapBiomas Chaco de A/B desde Python (sin Drive).

Equivalente a scripts/export_mapbiomas_pilot.js: mismas zonas y grilla
(configs/training_zones.geojson), píxel de 30 m alineado al origen de la grilla
Sentinel de 10 m, clases ORIGINALES en uint8 y nodata 255. No convierte a
bosque/no bosque: eso lo hace fase2_make_patches.py con chaco_monitor.labels.

Uso (Windows, desde la raíz del repositorio):
    $env:GEE_PROJECT="id-del-proyecto"
    .\\.venv\\Scripts\\python.exe scripts/fase2_export_mapbiomas.py

Salida: data/interim/labels-mapbiomas-v1/<zona>_mapbiomas_c5_v2_<año>.tif
        manifests/mapbiomas-labels-v1.json (tamaños, SHA-256, histograma de clases)
"""

import argparse
import hashlib
import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import rasterio

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from chaco_monitor.gee import download_geotiff_params, init_ee  # noqa: E402
from chaco_monitor.labels import CLASS_NAMES, LABEL_NODATA, MAPBIOMAS_ASSET, MAPBIOMAS_YEARS, unknown_codes  # noqa: E402

LABEL_RES = 30


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--zones-file", type=Path, default=REPO / "configs" / "training_zones.geojson")
    p.add_argument("--years", nargs="+", type=int, default=[2022, 2023])
    p.add_argument("--out", type=Path, default=Path("data/interim/labels-mapbiomas-v1"))
    p.add_argument("--manifest", type=Path, default=Path("manifests/mapbiomas-labels-v1.json"))
    return p.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    args = parse_args()
    bad = [y for y in args.years if y not in MAPBIOMAS_YEARS]
    if bad:
        raise SystemExit(f"MapBiomas Chaco Col. 5 cubre 1985-2023; fuera de rango: {bad}")
    zones = json.loads(args.zones_file.read_text(encoding="utf-8"))["features"]

    ee = init_ee()
    image = ee.Image(MAPBIOMAS_ASSET)
    print("Bandas disponibles:", len(image.bandNames().getInfo()))
    entries = []
    for zone in zones:
        props = zone["properties"]
        zone_id, crs = props["id"], props["target_crs"]
        _, _, left, _, _, top = props["grid"]["transform"]
        height, width = props["grid"]["shape"]
        # Celdas de 30 m que cubren completamente la grilla de 10 m.
        cols = math.ceil(width * 10 / LABEL_RES)
        rows = math.ceil(height * 10 / LABEL_RES)
        for year in args.years:
            layer = image.select(f"classification_{year}").unmask(LABEL_NODATA).toUint8()
            path = args.out / f"{zone_id}_mapbiomas_c5_v2_{year}.tif"
            download_geotiff_params(layer, path, {
                "crs": crs, "crs_transform": [LABEL_RES, 0, left, 0, -LABEL_RES, top],
                "dimensions": f"{cols}x{rows}", "format": "GEO_TIFF",
            })
            with rasterio.open(path) as src:
                codes = src.read(1)
                grid = {"crs": str(src.crs), "transform": list(src.transform)[:6],
                        "shape": [src.height, src.width]}
            values, counts = np.unique(codes, return_counts=True)
            hist = {int(v): round(int(c) / codes.size * 100, 3) for v, c in zip(values, counts)}
            print(f"{zone_id} {year}: {grid['shape'][1]}x{grid['shape'][0]} px de 30 m, {crs}")
            for code, pct in sorted(hist.items(), key=lambda kv: -kv[1])[:6]:
                print(f"    {code:>3} {CLASS_NAMES.get(code, '?'):28s} {pct:7.3f}%")
            unknown = unknown_codes(codes)
            if unknown:
                print(f"    ATENCIÓN códigos no listados (se ignorarán): {unknown}")
            entries.append({
                "path": path.name, "zone": zone_id, "year": year, "asset": MAPBIOMAS_ASSET,
                "band": f"classification_{year}", "nodata": LABEL_NODATA, **grid,
                "class_pct": hist, "unknown_codes": unknown,
                "bytes": path.stat().st_size, "sha256": sha256(path),
                "license": "MapBiomas Chaco, CC BY 4.0",
            })
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps({"version": "mapbiomas-labels-v1",
                                         "generated": date.today().isoformat(),
                                         "files": entries}, indent=2, ensure_ascii=False),
                             encoding="utf-8")
    print(f"\nManifiesto: {args.manifest}")


if __name__ == "__main__":
    main()
