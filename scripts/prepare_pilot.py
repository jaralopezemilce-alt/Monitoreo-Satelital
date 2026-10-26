"""Ingesta piloto de A/B: recortes DN, reflectancias, NDVI y máscaras de calidad.

Usa assets STAC ya verificados. No crea pseudoetiquetas, splits, parches ni modelo.
Todas las salidas grandes van a una carpeta externa a Git.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image, ImageDraw
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import reproject, Resampling, transform_bounds, transform_geom
from rasterio.windows import Window, from_bounds

# Permite invocar el script desde PowerShell sin instalar el paquete como editable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from chaco_monitor.preprocessing import (
    BANDS, CHANNELS, effective_radiometry, metric_grid, ndvi, quality_mask, to_reflectance,
)

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_TIMEOUT", "45")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "2")


def checksum(path: Path) -> str:
    """Hash por bloques: sirve para validar transferencia y reutilización offline."""
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            result.update(block)
    return result.hexdigest()


def write_raster(path: Path, values: np.ndarray, crs, transform, nodata,
                 descriptions: tuple = ()) -> None:
    """Escribe TIFF comprimido mediante archivo temporal, sin sobrescritura parcial."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if values.ndim == 2:
        values = values[None]
    temporary = path.with_suffix(".tmp.tif")
    with rasterio.open(
        temporary, "w", driver="GTiff", height=values.shape[1], width=values.shape[2],
        count=values.shape[0], dtype=values.dtype, crs=crs, transform=transform,
        nodata=nodata, compress="deflate", tiled=True, blockxsize=256, blockysize=256,
    ) as dst:
        dst.write(values)
        for index, name in enumerate(descriptions, 1):
            dst.set_band_description(index, name)
    temporary.replace(path)


def cache_native(asset: dict, bbox: list, path: Path) -> None:
    """Lee sólo la ventana necesaria de un COG, conservando DN y grilla nativa."""
    if path.exists():
        with rasterio.open(path) as existing:
            if existing.tags().get("source_url") != asset["href"]:
                raise ValueError(f"Caché incompatible: {path}")
        return
    with rasterio.open(asset["href"]) as src:
        bounds = transform_bounds("EPSG:4326", src.crs, *bbox, densify_pts=21)
        window = from_bounds(*bounds, transform=src.transform)
        # Dos píxeles de margen para interpolación en la nueva grilla.
        col, row = math.floor(window.col_off)-2, math.floor(window.row_off)-2
        right, bottom = math.ceil(window.col_off+window.width)+2, math.ceil(window.row_off+window.height)+2
        window = Window(col, row, right-col, bottom-row).intersection(Window(0, 0, src.width, src.height))
        values = src.read(1, window=window)
        metadata = asset["raster:bands"][0]
        write_raster(path, values, src.crs, src.window_transform(window), metadata["nodata"])
    with rasterio.open(path, "r+") as dst:
        dst.update_tags(source_url=asset["href"], raster_metadata=json.dumps(metadata))


def align_cached(path: Path, asset: dict, crs, transform, shape: tuple, categorical=False,
                 radiometry=None):
    """Bilineal para reflectancia; vecino más cercano para SCL, sin mezclar clases."""
    with rasterio.open(path) as src:
        raw = src.read(1)
        if categorical:
            values, nodata_value = raw, 0
            output = np.zeros(shape, dtype="uint8")
        else:
            values = to_reflectance(raw, radiometry)
            nodata_value = np.nan
            output = np.full(shape, np.nan, dtype="float32")
        reproject(
            values, output, src_transform=src.transform, src_crs=src.crs,
            src_nodata=nodata_value, dst_transform=transform, dst_crs=crs,
            dst_nodata=nodata_value,
            resampling=Resampling.nearest if categorical else Resampling.bilinear,
        )
    return output


def main() -> None:
    """Procesa únicamente features aprobadas; C reserva nunca se descarga aquí."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--zones", type=Path, help="Configuración alternativa, por ejemplo ventanas de entrenamiento")
    parser.add_argument("--historical-only", action="store_true")
    args = parser.parse_args()
    zones_file = args.zones or args.repo / "configs/candidate_zones.geojson"
    zones = json.loads(zones_file.read_text())["features"]
    items = json.loads((args.repo / "docs/evidence/selected_items.json").read_text())
    result = {"version":"ingestion-v1", "status":"imagery_only_labels_pending",
              "configuration":str(zones_file.name), "historical_only":args.historical_only,
              "band_order":list(CHANNELS), "records":[], "zone_pairs":[], "footprints":[],
              "configuration_sha256":checksum(zones_file),
              "code_sha256":{
                  "prepare_pilot.py":checksum(Path(__file__)),
                  "preprocessing.py":checksum(args.repo / "src/chaco_monitor/preprocessing.py"),
              }}
    started = time.perf_counter()
    for zone in zones:
        if zone["properties"]["status"] != "approved":
            continue
        name, crs = zone["properties"]["id"], zone["properties"]["target_crs"]
        coords = np.array(zone["geometry"]["coordinates"][0])
        bbox = [*coords.min(axis=0), *coords.max(axis=0)]
        transform, shape = metric_grid(bbox, crs)
        if "grid" in zone["properties"]:
            grid = zone["properties"]["grid"]
            transform, shape = rasterio.Affine(*grid["transform"]), tuple(grid["shape"])
        footprint = geometry_mask(
            [transform_geom("EPSG:4326", crs, zone["geometry"])],
            out_shape=shape, transform=transform, invert=True,
        )
        zone_dir = args.out / name
        write_raster(zone_dir / "footprint.tif", footprint.astype("uint8"), crs, transform, 0)
        result["footprints"].append({
            "zone":name, "path":str((zone_dir / "footprint.tif").relative_to(args.out)),
            "sha256":checksum(zone_dir / "footprint.tif"),
        })
        masks, thumbnails = {}, []
        for selection in (x for x in items if x["candidate"] == name):
            if args.historical_only and not selection["role"].startswith("historical"):
                continue
            begin = time.perf_counter()
            item, role = selection["item"], selection["role"]
            date = item["properties"]["datetime"][:10]
            folder = zone_dir / date
            assets, raw_paths = item["assets"], {}
            for band in (*BANDS, "scl"):
                raw_paths[band] = folder / "raw" / f"{band}.tif"
                cache_native(assets[band], bbox, raw_paths[band])
            reflectance = np.stack([
                align_cached(raw_paths[b], assets[b], crs, transform, shape,
                             radiometry=effective_radiometry(item, b)) for b in BANDS
            ])
            scl = align_cached(raw_paths["scl"], assets["scl"], crs, transform, shape, categorical=True)
            index = ndvi(reflectance[2], reflectance[3])
            valid = quality_mask(scl, reflectance, footprint) & np.isfinite(index)
            if valid.sum()/footprint.sum() < 0.80:
                raise ValueError(
                    f"{name}/{date}: menos de 80% observable. Revisar radiometría/nubes; "
                    "no continuar silenciosamente con datos descartados."
                )
            masks[role] = valid
            stack = np.concatenate([reflectance, index[None]])
            stack[:, ~valid] = -9999
            write_raster(folder / "stack.tif", stack, crs, transform, -9999, CHANNELS)
            write_raster(folder / "valid.tif", valid.astype("uint8"), crs, transform, 0, ("observable",))
            write_raster(folder / "scl.tif", scl, crs, transform, 0, ("SCL",))
            # Vista fija de reflectancia corregida; NDVI NO es un mapa de pérdida.
            rgb = np.nan_to_num(reflectance[[2, 1, 0]], nan=0)
            rgb = (np.clip(rgb / 0.3, 0, 1) ** (1/1.5)*255).astype("uint8")
            rgb[:, ~valid] = 120
            thumb = Image.fromarray(np.moveaxis(rgb, 0, -1)).resize((400, 420))
            panel = Image.new("RGB", (400, 465), "white")
            panel.paste(thumb, (0, 45))
            draw = ImageDraw.Draw(panel)
            draw.text((6, 5), f"{name} | {date}", fill="black")
            draw.text((6, 23), f"Observables: {valid.sum()/footprint.sum()*100:.2f}%", fill="black")
            thumbnails.append(panel)
            files = []
            for path in sorted(folder.rglob("*.tif")):
                files.append({"path":str(path.relative_to(args.out)), "bytes":path.stat().st_size,
                              "sha256":checksum(path)})
            record = {
                "zone":name, "role":role, "datetime":item["properties"]["datetime"],
                "item_id":item["id"], "source_item_url":next(l["href"] for l in item["links"] if l["rel"]=="self"),
                "assets":{b:assets[b] for b in (*BANDS,"scl")},
                "effective_radiometry":{b:effective_radiometry(item,b) for b in BANDS},
                "crs":crs, "transform":list(transform)[:6], "shape":list(shape),
                "footprint_pixels":int(footprint.sum()), "valid_pixels":int(valid.sum()),
                "valid_pct":round(valid.sum()/footprint.sum()*100,4),
                "ndvi_percentiles":dict(zip(["p05","p50","p95"], map(float,np.percentile(index[valid],[5,50,95])))),
                "scl_histogram":{str(k):int((scl[footprint]==k).sum()) for k in np.unique(scl[footprint])},
                "processing_seconds":round(time.perf_counter()-begin,3), "files":files,
                "license":"Copernicus Sentinel Data Terms and Conditions",
                "attribution":f"Contains modified Copernicus Sentinel data {date[:4]}",
            }
            result["records"].append(record)
            print(json.dumps({k:record[k] for k in ["zone","datetime","shape","valid_pct","processing_seconds"]}),flush=True)
        for period, before, after in [
            ("historical","historical_2022_0","historical_2023_1"),
            ("recent","recent_2026_2","recent_2026_3"),
        ]:
            if before not in masks or after not in masks:
                continue
            joint = masks[before] & masks[after]
            path = zone_dir / f"{period}_joint_valid.tif"
            write_raster(path, joint.astype("uint8"), crs, transform, 0)
            result["zone_pairs"].append({
                "zone":name, "period":period, "joint_valid_pixels":int(joint.sum()),
                "joint_valid_pct":round(joint.sum()/footprint.sum()*100,4),
                "observable_ha":float(joint.sum()*0.01),
                "meaning":"observable_area_not_deforested_area",
                "path":str(path.relative_to(args.out)), "sha256":checksum(path),
            })
        sheet = Image.new("RGB",(800,930),"white")
        for i, panel in enumerate(thumbnails):
            sheet.paste(panel,((i%2)*400,(i//2)*465))
        sheet.save(zone_dir / "pilot_preview.jpg",quality=90)
    result["preparation_wall_seconds"] = round(time.perf_counter()-started,3)
    (args.out / "manifest.json").write_text(json.dumps(result,indent=2),encoding="utf-8")


if __name__ == "__main__":
    main()
