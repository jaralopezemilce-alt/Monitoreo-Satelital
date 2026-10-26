"""Prepara evidencia visual de prospección: RGB, SCL y pérdida histórica.

Los datos descargados son sólo para seleccionar zonas y revisar muestras, no un
dataset listo para entrenar. La selección dirigida impide inferir tasas regionales.
"""

import argparse
import csv
import json
from pathlib import Path
import os

import numpy as np
from PIL import Image, ImageDraw
import rasterio
from rasterio.warp import transform_bounds, reproject, Resampling
from rasterio.windows import from_bounds


# Evita que GDAL liste directorios remotos completos o busque archivos auxiliares.
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_TIMEOUT", "45")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "2")


def read_aoi(url: str, bbox: list, size: int = 512):
    """Lee un recorte remoto y devuelve su grilla; nunca descarga el país entero."""
    with rasterio.open(url) as src:
        bounds = transform_bounds("EPSG:4326", src.crs, *bbox)
        window = from_bounds(*bounds, transform=src.transform)
        array = src.read(window=window, out_shape=(src.count, size, size))
        transform = src.window_transform(window) * rasterio.Affine.scale(
            window.width / size, window.height / size
        )
        # Grilla común sólo para inspección: no se usaría WGS84 para medir hectáreas.
        common_transform = rasterio.transform.from_bounds(*bbox, size, size)
        common = np.zeros_like(array)
        reproject(
            array, common, src_transform=transform, src_crs=src.crs,
            dst_transform=common_transform, dst_crs="EPSG:4326",
            resampling=Resampling.nearest,
        )
        return common, common_transform, "EPSG:4326"


def best_scene(features: list, start: str, end: str, bbox: list) -> dict:
    """Ordena por nubosidad de escena y exige cobertura completa del rectángulo."""
    west, south, east, north = bbox
    valid = []
    for f in features:
        b = f["bbox"]
        if (
            start <= f["properties"]["datetime"] < end
            and b[0] <= west and b[1] <= south and b[2] >= east and b[3] >= north
        ):
            valid.append(f)
    if not valid:
        raise ValueError(f"Sin escena para {start}/{end}")
    return min(valid, key=lambda f: f["properties"].get("eo:cloud_cover", 100))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rows, selections = [], []
    for candidate in json.loads((args.evidence / "candidates.json").read_text()):
        name, bbox = candidate["id"], candidate["bbox"]
        specs = [
            ("historical_2022", "2022-06", "2022-11"),
            ("historical_2023", "2023-09", "2023-11"),
            ("recent_2026", "2026-05", "2026-07"),
            ("recent_2026", "2026-09", "2026-10-27"),
        ]
        panels, images = [], []
        for index, (period, start, end) in enumerate(specs):
            features = json.loads((args.evidence / f"{name}_{period}_stac.json").read_text())
            feature = best_scene(features, start, end, bbox)
            assets = feature["assets"]
            rgb, transform, crs = read_aoi(assets["visual"]["href"], bbox)
            scl_asset = assets.get("scl") or assets.get("SCL")
            scl, _, _ = read_aoi(scl_asset["href"], bbox)
            values = scl[0]
            cloud_shadow = float(np.isin(values, [3, 8, 9, 10]).mean()*100)
            conservative_invalid = float(np.isin(values, [0, 1, 2, 3, 7, 8, 9, 10, 11]).mean()*100)
            p = feature["properties"]
            row = {
                "candidate": name, "role": f"{period}_{index}", "id": feature["id"],
                "datetime": p["datetime"], "cloud_scene_pct": p["eo:cloud_cover"],
                "scl_cloud_shadow_aoi_pct": round(cloud_shadow, 3),
                "scl_invalid_conservative_aoi_pct": round(conservative_invalid, 3),
                "item_url": next(l["href"] for l in feature["links"] if l["rel"] == "self"),
            }
            rows.append(row)
            selections.append({"candidate":name, "role":row["role"], "item":feature})
            image = Image.fromarray(np.moveaxis(rgb[:3], 0, -1).astype(np.uint8))
            images.append(image)
            image.save(args.out / f"{name}_{index}_rgb.png")
            # Guardar grilla/píxeles sólo en caché local, fuera del repositorio.
            np.savez_compressed(
                args.out / f"{name}_{index}_review.npz",
                rgb=rgb, scl=values, transform=tuple(transform), crs=str(crs),
            )
            panel = Image.new("RGB", (512, 560), "white")
            panel.paste(image, (0, 48))
            draw = ImageDraw.Draw(panel)
            draw.text((8, 5), f"{name} | {p['datetime'][:10]}", fill="black")
            draw.text((8, 23), f"Nubes/sombra AOI: {cloud_shadow:.2f}% (SCL)", fill="black")
            panels.append(panel)
            print(json.dumps(row), flush=True)
        # Pérdida anual 2022/2023 sobre la grilla de revisión de Sentinel.
        tile = "20S_070W" if bbox[0] < -60 else "20S_060W"
        with rasterio.open(args.raw / f"lossyear_{tile}.tif") as src:
            win = from_bounds(*bbox, transform=src.transform).round_offsets().round_lengths()
            loss = src.read(1, window=win)
            aligned = np.zeros((512, 512), dtype=np.uint8)
            reproject(
                loss, aligned, src_transform=src.window_transform(win), src_crs=src.crs,
                dst_transform=transform, dst_crs=crs, resampling=Resampling.nearest,
            )
        np.save(args.out / f"{name}_lossyear.npy", aligned)
        overview = Image.new("RGB", (1024, 1120), "white")
        for i, panel in enumerate(panels):
            overview.paste(panel, ((i % 2)*512, (i//2)*560))
        overview.save(args.out / f"{name}_overview.jpg", quality=88)
        # 12 puntos por zona: 6 de pérdida 2022, 6 pérdida 2023.
        # Semilla fija; el denominador no es "todos los píxeles del dataset".
        rng = np.random.default_rng(42)
        sample_rows = []
        sheet = Image.new("RGB", (960, 12*112), "white")
        draw = ImageDraw.Draw(sheet)
        for i, year in enumerate([22]*6+[23]*6):
            mask = aligned == year
            mask[:40] = False; mask[-40:] = False
            mask[:, :40] = False; mask[:, -40:] = False
            coords = np.argwhere(mask)
            if not len(coords):
                continue
            y, x = coords[rng.integers(len(coords))]
            sample_rows.append({"id":f"{name}_{i+1:02}", "x":int(x), "y":int(y),
                                "lossyear":int(2000+year), "review":"pending"})
            draw.text((5, i*112+4), f"{i+1:02} Hansen {2000+year}", fill="black")
            for k in range(4):
                crop = images[k].crop((x-40, y-40, x+40, y+40)).resize((100,100))
                marker = ImageDraw.Draw(crop)
                marker.ellipse((47,47,53,53), outline="red", width=1)
                sheet.paste(crop, (140+k*200, i*112+4))
        sheet.save(args.out / f"{name}_audit.jpg", quality=92)
        (args.out / f"{name}_audit_samples.json").write_text(
            json.dumps(sample_rows, indent=2), encoding="utf-8")
    with (args.out / "selected_scenes.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    (args.out / "selected_items.json").write_text(
        json.dumps(selections, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
