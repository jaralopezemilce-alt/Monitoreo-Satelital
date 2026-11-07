"""API REST del monitor de deforestación (modo offline, zonas precargadas).

Arranque desde la raíz del repo:
    .venv\\Scripts\\python.exe -m uvicorn api.main:app --port 8000

Documentación interactiva: http://127.0.0.1:8000/docs

Variables de entorno (todas opcionales):
    CHACO_INPUTS        carpeta de ingesta      (data/interim/historical-inputs-v1)
    CHACO_LABELS        etiquetas MapBiomas     (data/interim/labels-mapbiomas-v1)
    CHACO_MODEL         pesos de la U-Net       (models/unet-v1.pt)
    CHACO_DATASET       dataset de parches      (data/processed/dataset-v1)
    CHACO_MAX_AREA_KM2  área máxima por pedido  (4)

El visor web queda en http://127.0.0.1:8000/visor/
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import rasterio  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import RedirectResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pyproj import Transformer  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from chaco_monitor.inference import (  # noqa: E402
    PAIRS, PIXEL_HA, ZoneStore, load_model, mask_to_geojson, predict_window, rgb_png)
from chaco_monitor.labels import IGNORE  # noqa: E402


def _path(env: str, default: str) -> Path:
    p = Path(os.environ.get(env, default))
    return p if p.is_absolute() else ROOT / p


INPUTS = _path("CHACO_INPUTS", "data/interim/historical-inputs-v1")
LABELS = _path("CHACO_LABELS", "data/interim/labels-mapbiomas-v1")
MODEL = _path("CHACO_MODEL", "models/unet-v1.pt")
DATASET = _path("CHACO_DATASET", "data/processed/dataset-v1")
MAX_AREA_KM2 = float(os.environ.get("CHACO_MAX_AREA_KM2", "4"))

app = FastAPI(title="Monitor de deforestación del Chaco", version="0.1.0",
              description="Detección de pérdida de bosque con U-Net sobre Sentinel-2 (zonas precargadas).")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


@lru_cache(maxsize=1)
def store() -> ZoneStore:
    if not (INPUTS / "manifest.json").exists():
        raise HTTPException(503, f"No se encontró la ingesta en {INPUTS}. Corré scripts/prepare_pilot.py.")
    return ZoneStore(INPUTS, LABELS if LABELS.exists() else None)


@lru_cache(maxsize=1)
def model():
    if not MODEL.exists():
        raise HTTPException(503, f"No se encontró el modelo en {MODEL}. Corré scripts/fase3_train.py.")
    return load_model(MODEL)


def get_zone(zone_id: str):
    zone = store().zones.get(zone_id)
    if zone is None:
        raise HTTPException(404, f"Zona desconocida: {zone_id}. Disponibles: {sorted(store().zones)}")
    return zone


class PredictRequest(BaseModel):
    zone: str = Field(..., examples=["A_boqueron"])
    bbox: list[float] = Field(..., min_length=4, max_length=4,
                              description="[oeste, sur, este, norte] en grados WGS84",
                              examples=[[-60.60, -21.84, -60.585, -21.825]])
    pair: str = Field("historical", description="Par de fechas; por ahora sólo 'historical' (2022→2023)")


@app.get("/health")
def health():
    ok_inputs, ok_model = (INPUTS / "manifest.json").exists(), MODEL.exists()
    return {"status": "ok" if ok_inputs and ok_model else "incompleto",
            "ingesta": ok_inputs, "modelo": ok_model, "etiquetas_mapbiomas": LABELS.exists(),
            "max_area_km2": MAX_AREA_KM2}


@app.get("/zones")
def zones():
    out = []
    for z in store().zones.values():
        h, w = z.shape
        to_wgs = Transformer.from_crs(z.crs, "EPSG:4326", always_xy=True)
        ring = [list(to_wgs.transform(*(z.transform * (c, r)))) for c, r in
                [(0, 0), (w, 0), (w, h), (0, h), (0, 0)]]
        out.append({"id": z.id, "crs": z.crs, "bbox": [round(v, 6) for v in z.bbox_wgs84],
                    "outline": [[round(x, 6), round(y, 6)] for x, y in ring],
                    "shape": list(z.shape), "fechas": z.dates, "pares": list(PAIRS),
                    "max_area_km2": MAX_AREA_KM2})
    return out


@app.get("/zones/{zone_id}/rgb/{role}.png")
def zone_rgb(zone_id: str, role: str):
    """Imagen de fondo en color verdadero (offline). Los límites van en el header X-Bounds."""
    zone = get_zone(zone_id)
    if role not in zone.folders:
        raise HTTPException(404, f"Fecha desconocida: {role}. Disponibles: {sorted(zone.folders)}")
    png, bounds = _rgb_cached(zone_id, role)
    return Response(png, media_type="image/png",
                    headers={"X-Bounds": ",".join(f"{b:.6f}" for b in bounds),
                             "Access-Control-Expose-Headers": "X-Bounds",
                             "Cache-Control": "max-age=3600"})


@lru_cache(maxsize=8)
def _rgb_cached(zone_id: str, role: str):
    return rgb_png(store(), store().zones[zone_id], role)


@app.post("/predict")
def predict(req: PredictRequest):
    zone = get_zone(req.zone)
    if req.pair not in PAIRS:
        raise HTTPException(422, f"Par desconocido: {req.pair}. Disponibles: {list(PAIRS)}")
    try:
        window = store().window_for_bbox(zone, req.bbox)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(422, f"{exc}. Límites de {zone.id}: {[round(v, 5) for v in zone.bbox_wgs84]}") from exc
    area_km2 = window.width * window.height * PIXEL_HA / 100
    if area_km2 > MAX_AREA_KM2:
        raise HTTPException(422, f"Área de {area_km2:.2f} km² supera el máximo de {MAX_AREA_KM2} km²")

    t0 = time.perf_counter()
    net, threshold, info = model()
    prob, valid = predict_window(net, store(), zone, window, req.pair)
    seconds = round(time.perf_counter() - t0, 2)
    if not valid.any():
        raise HTTPException(422, "Sin píxeles válidos en ambas fechas: resultado no evaluable")

    loss = (prob >= threshold) & valid
    win_tr = rasterio.windows.transform(window, zone.transform)
    result = {
        "zone": zone.id, "pair": req.pair,
        "fechas": {"t1": zone.dates[PAIRS[req.pair][0]], "t2": zone.dates[PAIRS[req.pair][1]]},
        "area_km2": round(area_km2, 3),
        "valid_pct": round(100 * valid.mean(), 2),
        "loss_px": int(loss.sum()), "loss_ha": round(float(loss.sum()) * PIXEL_HA, 2),
        "threshold": threshold, "model": info, "inference_seconds": seconds,
        "loss_geojson": mask_to_geojson(loss, win_tr, zone.crs),
        "no_observable_geojson": mask_to_geojson(~valid, win_tr, zone.crs),
        "mapbiomas": None,
    }
    ref = store().reference_loss(zone, window, valid)
    if ref is not None:
        known = ref != IGNORE
        result["mapbiomas"] = {
            "loss_ha": round(float((ref == 1).sum()) * PIXEL_HA, 2),
            "acuerdo_pct": round(100 * float((loss[known] == (ref[known] == 1)).mean()), 2) if known.any() else None,
            "nota": "Referencia MapBiomas Chaco Col. 5 (pseudoetiqueta, no verdad de terreno)",
        }
    return result


@app.get("/zones/{zone_id}/splits")
def zone_splits(zone_id: str):
    """Bloques espaciales del dataset con su split (train/val/test) como polígonos WGS84.

    Sirve para que la demo use áreas de test, que el modelo no vio al entrenar.
    """
    zone = get_zone(zone_id)
    index, config = DATASET / "index.csv", DATASET / "config.json"
    if not index.exists() or not config.exists():
        return {"type": "FeatureCollection", "features": [], "nota": f"No hay dataset en {DATASET}"}
    block = int(json.loads(config.read_text(encoding="utf-8"))["block_px"])
    with index.open(encoding="utf-8", newline="") as f:
        blocks = {r["block"]: r["split"] for r in csv.DictReader(f) if r["zone"] == zone.id}
    to_wgs = Transformer.from_crs(zone.crs, "EPSG:4326", always_xy=True)
    feats = []
    for key, split in sorted(blocks.items()):
        br, bc = (int(v) for v in key.split("_"))
        corners = [(bc, br), (bc + 1, br), (bc + 1, br + 1), (bc, br + 1), (bc, br)]
        ring = [list(to_wgs.transform(*(zone.transform * (c * block, r * block)))) for c, r in corners]
        feats.append({"type": "Feature", "properties": {"block": key, "split": split},
                      "geometry": {"type": "Polygon", "coordinates": [[[round(x, 6), round(y, 6)] for x, y in ring]]}})
    return {"type": "FeatureCollection", "features": feats}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/visor/")


if (ROOT / "web" / "index.html").exists():
    app.mount("/visor", StaticFiles(directory=ROOT / "web", html=True), name="visor")
