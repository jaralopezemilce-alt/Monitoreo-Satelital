"""Zonas de estudio: lectura del GeoJSON, ventanas métricas y proyección UTM.

Funciones puras (sin internet ni Earth Engine) para poder probarlas en CI.
"""

import json
import math
from pathlib import Path

DEFAULT_ZONES = Path(__file__).resolve().parents[2] / "configs" / "candidate_zones.geojson"
KM_PER_DEG_LAT = 111.32


def load_zones(path: Path = DEFAULT_ZONES) -> dict[str, list[float]]:
    """Devuelve {id: [oeste, sur, este, norte]} a partir de polígonos rectangulares."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    zones = {}
    for feature in data["features"]:
        ring = feature["geometry"]["coordinates"][0]
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        zones[feature["properties"]["id"]] = [min(lons), min(lats), max(lons), max(lats)]
    return zones


def bbox_center(bbox: list[float]) -> tuple[float, float]:
    """Centro (lon, lat) de [oeste, sur, este, norte]."""
    west, south, east, north = bbox
    return (west + east) / 2, (south + north) / 2


def utm_epsg(lon: float, lat: float) -> int:
    """EPSG UTM WGS84 del punto. En el Chaco: 32720 (oeste de -60°) o 32721 (este).

    Importa para calcular hectáreas: A_boqueron cae en la zona 20S, mientras que
    B_alto_paraguay y C_presidente_hayes caen en la 21S.
    """
    if not (-180 <= lon <= 180 and -80 <= lat <= 84):
        raise ValueError("Coordenadas fuera del rango UTM")
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


def window_around(bbox: list[float], size_km: float) -> list[float]:
    """Ventana cuadrada de size_km de lado centrada en la zona (para entrenamiento).

    Aproximación esférica suficiente para ventanas de ~10 km; la grilla final se
    define en UTM al exportar, por lo que el área real se mide en metros.
    """
    if not math.isfinite(size_km) or size_km <= 0:
        raise ValueError("size_km debe ser positivo")
    lon, lat = bbox_center(bbox)
    half_lat = (size_km / 2) / KM_PER_DEG_LAT
    half_lon = (size_km / 2) / (KM_PER_DEG_LAT * math.cos(math.radians(lat)))
    return [lon - half_lon, lat - half_lat, lon + half_lon, lat + half_lat]
