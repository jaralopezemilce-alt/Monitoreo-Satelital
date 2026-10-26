"""Fase 2a: exporta imágenes Sentinel-2 + etiquetas MapBiomas Chaco por zona y año.

Para cada zona y año genera UN GeoTIFF alineado (misma grilla UTM de 10 m) con
7 bandas int16:
    1 B2   2 B3   3 B4   4 B8      reflectancia x 10000 (nodata -9999)
    5 NDVI                          x 10000 (nodata -9999)
    6 valid                         1 = hubo observación sin nubes, 0 = no
    7 mb_code                       código original MapBiomas (0 = sin dato)

La conversión a bosque/no bosque NO se hace aquí, sino en fase2_make_patches.py
con chaco_monitor.labels (una sola definición, probada en CI).

Uso (Windows, desde la raíz del repositorio):
    $env:GEE_PROJECT="id-del-proyecto"
    .\\.venv\\Scripts\\python.exe scripts/fase2_export_gee.py --zones A_boqueron B_alto_paraguay C_presidente_hayes
"""

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from chaco_monitor.gee import NODATA, SPECTRAL_BANDS, download_geotiff, init_ee, s2_composite  # noqa: E402
from chaco_monitor.labels import CLASS_NAMES, MAPBIOMAS_ASSET, MAPBIOMAS_YEARS  # noqa: E402
from chaco_monitor.zones import bbox_center, load_zones, utm_epsg, window_around  # noqa: E402

BAND_ORDER = ["B2", "B3", "B4", "B8", "NDVI", "valid", "mb_code"]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--zones", nargs="+", required=True)
    p.add_argument("--years", nargs="+", type=int, default=[2022, 2023])
    p.add_argument("--season", nargs=2, default=["07-01", "10-31"], metavar=("MM-DD", "MM-DD"),
                   help="ventana dentro de cada año (estación seca, igual para todos)")
    p.add_argument("--window-km", type=float, default=10.0, help="lado de la ventana de entrenamiento")
    p.add_argument("--out", type=Path, default=Path("data/interim/gee"))
    p.add_argument("--manifest", type=Path, default=Path("manifests/gee_exports.json"))
    return p.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    args = parse_args()
    zones = load_zones()
    unknown = [z for z in args.zones if z not in zones]
    if unknown:
        raise SystemExit(f"Zonas desconocidas: {unknown}. Disponibles: {list(zones)}")
    bad_years = [y for y in args.years if y not in MAPBIOMAS_YEARS]
    if bad_years:
        raise SystemExit(f"MapBiomas Chaco Col. 5 cubre 1985-2023; fuera de rango: {bad_years}")

    ee = init_ee()
    mapbiomas = ee.Image(MAPBIOMAS_ASSET)
    entries = []
    for zone in args.zones:
        window = window_around(zones[zone], args.window_km)
        crs = f"EPSG:{utm_epsg(*bbox_center(window))}"
        region = ee.Geometry.Rectangle(window)
        for year in args.years:
            start, end = f"{year}-{args.season[0]}", f"{year}-{args.season[1]}"
            composite, n_scenes = s2_composite(ee, region, start, end, SPECTRAL_BANDS)
            ndvi = composite.normalizedDifference(["B8", "B4"]).rename("NDVI")
            valid = composite.mask().reduce(ee.Reducer.min()).gt(0).rename("valid")
            spectral = composite.addBands(ndvi).multiply(10000).round().unmask(NODATA)
            label = mapbiomas.select(f"classification_{year}").rename("mb_code").unmask(0)
            stack = ee.Image.cat([spectral, valid.unmask(0), label]).toInt16().select(
                list(range(7)), BAND_ORDER)

            path = args.out / f"{zone}_{year}.tif"
            print(f"{zone} {year}: {n_scenes} escenas ({start} -> {end}), {crs}")
            download_geotiff(stack, region, path, 10, crs)

            import rasterio

            with rasterio.open(path) as src:
                valid_px = src.read(6)
                codes = src.read(7)
                shape = (src.height, src.width)
            values, counts = np.unique(codes[valid_px == 1], return_counts=True)
            total = counts.sum() or 1
            histogram = {int(v): round(int(c) / total * 100, 2) for v, c in zip(values, counts)}
            print(f"  {shape[1]}x{shape[0]} px, válidos {valid_px.mean() * 100:.1f}%")
            for code, pct in sorted(histogram.items(), key=lambda kv: -kv[1])[:6]:
                print(f"    {code:>3} {CLASS_NAMES.get(code, '?'):28s} {pct:6.2f}%")

            entries.append({
                "file": path.name, "zone": zone, "year": year, "bbox_wgs84": window,
                "crs": crs, "scale_m": 10, "width": shape[1], "height": shape[0],
                "bands": BAND_ORDER, "scale_factor": 10000, "nodata": NODATA,
                "s2_window": [start, end], "s2_scenes": n_scenes,
                "s2_collection": "COPERNICUS/S2_SR_HARMONIZED + GOOGLE/CLOUD_SCORE_PLUS cs_cdf>=0.60",
                "labels": f"{MAPBIOMAS_ASSET} classification_{year}",
                "valid_pct": round(float(valid_px.mean() * 100), 2),
                "mapbiomas_class_pct": histogram,
                "bytes": path.stat().st_size, "sha256": sha256(path),
                "license": "Contains modified Copernicus Sentinel data; MapBiomas Chaco CC BY 4.0",
            })

    previous = []
    if args.manifest.exists():
        previous = json.loads(args.manifest.read_text(encoding="utf-8")).get("files", [])
    keep = [e for e in previous if e["file"] not in {n["file"] for n in entries}]
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps({"generated": date.today().isoformat(),
                                         "files": keep + entries}, indent=2, ensure_ascii=False),
                             encoding="utf-8")
    print(f"\nManifiesto actualizado: {args.manifest}")


if __name__ == "__main__":
    main()
