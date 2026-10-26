"""Fase 1: NDVI entre dos fechas y baseline de pérdida por umbrales (Earth Engine).

Qué hace, en orden:
1. Se conecta a Earth Engine con el proyecto compartido (variable GEE_PROJECT).
2. Arma una mediana Sentinel-2 sin nubes (Cloud Score+) para T1 y para T2.
3. Calcula NDVI en cada fecha y dNDVI = NDVI_T2 - NDVI_T1.
4. Marca como "pérdida" lo que era vegetación densa en T1, cayó fuerte y quedó
   baja en T2 (regla de umbrales: es la BASELINE contra la que se compara la U-Net).
5. Calcula hectáreas, descarga GeoTIFF en UTM y genera un mapa HTML (Leaflet).

Uso (desde la raíz del repositorio, Windows):
    $env:GEE_PROJECT="id-del-proyecto"
    .\\.venv\\Scripts\\python.exe scripts/fase1_ndvi_baseline.py --zone A_boqueron
    .\\.venv\\Scripts\\python.exe scripts/fase1_ndvi_baseline.py --bbox -60.72 -21.95 -60.60 -21.85

Las fechas T1/T2 deben estar en la MISMA estación: el bosque chaqueño es
semicaducifolio y en invierno baja su NDVI sin que haya desmonte.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from chaco_monitor.gee import EXTRA_BANDS, NODATA, SPECTRAL_BANDS, download_geotiff, init_ee, s2_composite  # noqa: E402
from chaco_monitor.zones import bbox_center, load_zones, utm_epsg  # noqa: E402


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    where = p.add_mutually_exclusive_group(required=True)
    where.add_argument("--zone", help="id en configs/candidate_zones.geojson")
    where.add_argument("--bbox", nargs=4, type=float, metavar=("OESTE", "SUR", "ESTE", "NORTE"))
    p.add_argument("--t1", nargs=2, default=["2025-06-01", "2025-09-30"], metavar=("INICIO", "FIN"))
    p.add_argument("--t2", nargs=2, default=["2026-06-01", "2026-09-30"], metavar=("INICIO", "FIN"))
    p.add_argument("--ndvi-forest-min", type=float, default=0.55)
    p.add_argument("--dndvi-loss-max", type=float, default=-0.25)
    p.add_argument("--ndvi-t2-max", type=float, default=0.40)
    p.add_argument("--min-patch-px", type=int, default=50, help="50 px de 10 m = 0,5 ha")
    p.add_argument("--out", type=Path, default=Path("outputs/fase1"))
    p.add_argument("--no-download", action="store_true", help="sólo estadísticas y mapa")
    return p.parse_args()


def main():
    args = parse_args()
    name = args.zone or "bbox_" + "_".join(f"{v:.3f}" for v in args.bbox)
    bbox = load_zones()[args.zone] if args.zone else args.bbox
    crs = f"EPSG:{utm_epsg(*bbox_center(bbox))}"
    out = args.out / name
    out.mkdir(parents=True, exist_ok=True)

    ee = init_ee()
    aoi = ee.Geometry.Rectangle(bbox)
    bands = SPECTRAL_BANDS + EXTRA_BANDS

    print(f"Zona {name} {bbox} -> {crs}")
    img_t1, n1 = s2_composite(ee, aoi, *args.t1, bands)
    img_t2, n2 = s2_composite(ee, aoi, *args.t2, bands)
    print(f"  T1 {args.t1[0]} -> {args.t1[1]}: {n1} escenas")
    print(f"  T2 {args.t2[0]} -> {args.t2[1]}: {n2} escenas")

    ndvi_t1 = img_t1.normalizedDifference(["B8", "B4"]).rename("NDVI_T1")
    ndvi_t2 = img_t2.normalizedDifference(["B8", "B4"]).rename("NDVI_T2")
    dndvi = ndvi_t2.subtract(ndvi_t1).rename("dNDVI")

    loss = (ndvi_t1.gt(args.ndvi_forest_min)
            .And(dndvi.lt(args.dndvi_loss_max))
            .And(ndvi_t2.lt(args.ndvi_t2_max))
            .rename("loss").selfMask())
    loss = loss.updateMask(loss.connectedPixelCount(100, True).gte(args.min_patch_px))

    def mean(img):
        return img.reduceRegion(ee.Reducer.mean(), aoi, 10, maxPixels=1e10).values().get(0)

    stats = ee.Dictionary({
        "area_aoi_ha": aoi.area(1).divide(1e4),
        "area_perdida_ha": loss.multiply(ee.Image.pixelArea()).divide(1e4)
        .reduceRegion(ee.Reducer.sum(), aoi, 10, maxPixels=1e10).get("loss"),
        "ndvi_t1_medio": mean(ndvi_t1),
        "ndvi_t2_medio": mean(ndvi_t2),
    }).getInfo()
    stats.update({"zona": name, "bbox": bbox, "crs": crs, "t1": args.t1, "t2": args.t2,
                  "escenas_t1": n1, "escenas_t2": n2,
                  "umbrales": {"ndvi_forest_min": args.ndvi_forest_min,
                               "dndvi_loss_max": args.dndvi_loss_max,
                               "ndvi_t2_max": args.ndvi_t2_max,
                               "min_patch_px": args.min_patch_px},
                  "nota": "Baseline por umbrales; no es una estimación validada."})
    print("\n=== Resultados preliminares (baseline) ===")
    for key in ("area_aoi_ha", "area_perdida_ha", "ndvi_t1_medio", "ndvi_t2_medio"):
        print(f"  {key:16s}: {stats[key] or 0:,.3f}")
    (out / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    if not args.no_download:
        import rasterio

        print("\nDescargando GeoTIFF...")
        nd_path = download_geotiff(ee.Image.cat([ndvi_t1, ndvi_t2, dndvi]).unmask(NODATA).toFloat(),
                                   aoi, out / "ndvi_T1_T2_dNDVI.tif", 10, crs)
        download_geotiff(loss.unmask(0).toByte(), aoi, out / "mask_perdida_baseline.tif", 10, crs)
        with rasterio.open(nd_path) as src:
            arr = src.read().astype("float32")
        arr[(arr <= NODATA) | ~np.isfinite(arr)] = np.nan
        valid = np.isfinite(arr[2])
        print(f"  Píxeles válidos: {valid.mean() * 100:.1f}%")
        print(f"  dNDVI min/medio/max: {np.nanmin(arr[2]):.3f} / {np.nanmean(arr[2]):.3f} / "
              f"{np.nanmax(arr[2]):.3f}")

    import folium

    def ee_layer(m, image, vis, label, show=True):
        tiles = ee.Image(image).getMapId(vis)["tile_fetcher"].url_format
        folium.raster_layers.TileLayer(tiles=tiles, attr="Google Earth Engine / Copernicus",
                                       name=label, overlay=True, show=show).add_to(m)

    lon, lat = bbox_center(bbox)
    m = folium.Map(location=[lat, lon], zoom_start=13, tiles=None)
    folium.TileLayer("Esri.WorldImagery", name="Satélite Esri").add_to(m)
    rgb = {"bands": ["B4", "B3", "B2"], "min": 0.0, "max": 0.25}
    ndvi_vis = {"min": 0, "max": 0.9, "palette": ["#a50026", "#fdae61", "#ffffbf", "#a6d96a", "#006837"]}
    ee_layer(m, img_t1, rgb, "RGB T1", show=False)
    ee_layer(m, img_t2, rgb, "RGB T2")
    ee_layer(m, ndvi_t1, ndvi_vis, "NDVI T1", show=False)
    ee_layer(m, ndvi_t2, ndvi_vis, "NDVI T2", show=False)
    ee_layer(m, dndvi, {"min": -0.5, "max": 0.5, "palette": ["#b2182b", "#f7f7f7", "#1a9850"]},
             "dNDVI", show=False)
    ee_layer(m, loss, {"palette": ["#FF0000"]}, "Pérdida (baseline)")
    folium.GeoJson(aoi.getInfo(), name="Zona",
                   style_function=lambda _: {"color": "yellow", "fill": False, "weight": 2}).add_to(m)
    folium.LayerControl().add_to(m)
    m.save(out / "mapa.html")
    print(f"\nListo: {out / 'stats.json'} y {out / 'mapa.html'}")


if __name__ == "__main__":
    main()
