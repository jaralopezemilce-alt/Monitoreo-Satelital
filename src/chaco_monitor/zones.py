"""Zonas de estudio: lectura del GeoJSON y proyección UTM.

Funciones puras (sin internet ni Earth Engine) para poder probarlas en CI.
"""

import json
from pathlib import Path

DEFAULT_ZONES = Path(__file__).resolve().parents[2] / "configs" / "candidate_zones.geojson"


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
