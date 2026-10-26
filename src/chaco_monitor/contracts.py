"""Validaciones independientes del modelo para controlar el alcance de la demo."""

import math
from collections.abc import Sequence

from pyproj import Geod


def bbox_area_km2(bbox: Sequence[float]) -> float:
    """Valida [oeste, sur, este, norte] WGS84 y calcula área geodésica.

    No comprueba pertenencia al Chaco: esa verificación necesitará el polígono
    de cobertura definitivo. No admite cruce del antimeridiano.
    """
    if len(bbox) != 4 or not all(math.isfinite(v) for v in bbox):
        raise ValueError("bbox requiere cuatro coordenadas finitas")
    west, south, east, north = bbox
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Orden o rango incorrecto: [oeste, sur, este, norte]")
    area, _ = Geod(ellps="WGS84").polygon_area_perimeter(
        [west, east, east, west], [south, south, north, north]
    )
    return abs(area) / 1_000_000


def require_area_limit(bbox: Sequence[float], max_km2: float = 4.0) -> float:
    """Rechaza áreas demasiado grandes antes de descargar o inferir."""
    if not math.isfinite(max_km2) or max_km2 <= 0:
        raise ValueError("El límite debe ser positivo y finito")
    area = bbox_area_km2(bbox)
    if area > max_km2:
        raise ValueError(f"Área {area:.2f} km² supera el límite {max_km2:.2f} km²")
    return area
