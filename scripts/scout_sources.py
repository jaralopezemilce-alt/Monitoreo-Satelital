"""Prospección reproducible de candidatos; no genera el dataset de entrenamiento.

Descarga dos tiles pequeños de Hansen lossyear (comprimidos), busca un núcleo
de pérdida histórica y consulta escenas Sentinel-2. Guarda evidencia JSON/CSV.
La nubosidad STAC es de la escena completa, no del área candidata.
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds
import requests


STAC = "https://earth-search.aws.element84.com/v1"
GFC = "https://storage.googleapis.com/earthenginepartners-hansen/GFC-2025-v1.13"
# Ventanas iniciales propuestas, no límites administrativos.
SEARCH_AREAS = {
    "A_boqueron": [-60.6, -21.9, -60.2, -21.5],
    "B_alto_paraguay": [-59.6, -20.7, -59.2, -20.3],
    "C_presidente_hayes": [-59.5, -23.5, -59.1, -23.1],
}


def download(url: str, path: Path) -> None:
    """Descarga en bloques y renombra sólo al terminar; no usa credenciales."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    with requests.get(url, stream=True, timeout=(15, 120)) as response:
        response.raise_for_status()
        with temporary.open("wb") as output:
            for block in response.iter_content(1024 * 1024):
                output.write(block)
    temporary.replace(path)


def select_candidate(name: str, bounds: list, raw: Path) -> dict:
    """Selecciona bloque con pérdidas 2022–2023, sin usar Sentinel como etiqueta.

    Este muestreo dirigido sirve para elegir demos, no para estimar precisión
    representativa del departamento. Devuelve un AOI de ~4 km de lado.
    """
    tile = "20S_070W" if bounds[0] < -60 else "20S_060W"
    url = f"{GFC}/Hansen_GFC-2025-v1.13_lossyear_{tile}.tif"
    path = raw / f"lossyear_{tile}.tif"
    download(url, path)
    with rasterio.open(path) as src:
        window = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths()
        loss = src.read(1, window=window)
        transform = src.window_transform(window)
        # Bloques no solapados de ~4 km; priorizar pérdida del período etiquetable.
        size = 144
        candidates = []
        for row in range(0, loss.shape[0] - size + 1, size):
            for col in range(0, loss.shape[1] - size + 1, size):
                block = loss[row:row+size, col:col+size]
                score = int(np.isin(block, [22, 23]).sum())
                candidates.append((score, row, col))
        score, row, col = max(candidates)
        west, north = transform * (col, row)
        east, south = transform * (col+size, row+size)
        block = loss[row:row+size, col:col+size]
        return {
            "id": name, "bbox": [west, south, east, north],
            "center_lonlat": [(west+east)/2, (south+north)/2],
            "gfc_version": "2025-v1.13", "gfc_url": url,
            "loss_pixels_by_year": {
                str(2000+y): int((block == y).sum()) for y in range(1, 26)
            },
            "selection_loss_pixels_2022_2023": score,
            "status": "candidate_not_approved",
        }


def search_scenes(bbox: list, interval: str, collection: str = "sentinel-2-c1-l2a") -> list:
    """Consulta/pagina por GET y conserva el ID y las URLs originales del catálogo."""
    params = {
        "collections": collection,
        "bbox": ",".join(map(str, bbox)),
        "datetime": interval,
        "limit": 100,
    }
    url = STAC + "/search"
    features = []
    for _ in range(20):
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        body = response.json()
        features.extend(body.get("features", []))
        next_link = next((link for link in body.get("links", []) if link["rel"] == "next"), None)
        if next_link is None:
            return features
        if next_link.get("method", "GET") != "GET":
            raise RuntimeError("Paginación inesperada: revisar el contrato del catálogo")
        url, params = next_link["href"], None
    raise RuntimeError("Límite de paginación: no devolver resultados truncados")


def main() -> None:
    """Emite candidatos y escenas <=10% de nubosidad de escena, sin elegir fechas aún."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    candidates = []
    rows = []
    intervals = {
        "historical_2022": "2022-06-01T00:00:00Z/2022-10-31T23:59:59Z",
        "historical_2023": "2023-06-01T00:00:00Z/2023-10-31T23:59:59Z",
        "recent_2026": "2026-05-01T00:00:00Z/2026-10-26T23:59:59Z",
    }
    for name, bounds in SEARCH_AREAS.items():
        candidate = select_candidate(name, bounds, args.cache)
        candidates.append(candidate)
        print(json.dumps(candidate), flush=True)
        for period, interval in intervals.items():
            # La colección C1 no contiene todo el archivo antiguo del proveedor.
            collection = "sentinel-2-l2a" if period == "historical_2022" else "sentinel-2-c1-l2a"
            features = search_scenes(candidate["bbox"], interval, collection)
            # Mantener metadata completa para poder verificar escalas, fechas y assets.
            (args.out / f"{name}_{period}_stac.json").write_text(
                json.dumps(features, indent=2), encoding="utf-8"
            )
            good = sorted(
                (f for f in features if f["properties"].get("eo:cloud_cover", 100) <= 10),
                key=lambda f: f["properties"]["datetime"],
            )
            for feature in good:
                p = feature["properties"]
                rows.append({
                    "candidate": name, "period": period, "id": feature["id"],
                    "datetime": p["datetime"], "cloud_cover_scene_pct": p["eo:cloud_cover"],
                    "item_url": next(l["href"] for l in feature["links"] if l["rel"] == "self"),
                })
            print(name, period, "all", len(features), "cloud<=10", len(good), flush=True)
    (args.out / "candidates.json").write_text(json.dumps(candidates, indent=2), encoding="utf-8")
    if rows:
        with (args.out / "scenes.csv").open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
