"""Conversión de clases MapBiomas Chaco (Colección 5) a bosque / no bosque.

Códigos oficiales tomados de la leyenda 'mapbiomas-chaco' del toolkit de MapBiomas
(https://github.com/mapbiomas/user-toolkit/blob/master/data/legends.js).

DECISIÓN DEL EQUIPO (pendiente de aprobación, ver docs/fase2-dataset.md):
- Bosque (1): leñosas cerradas (3, cobertura >= 65 %), leñosas abiertas
  (4, 20-65 %) y leñosas inundables (6).
- Ignorar (255): leñosas dispersas (45, 5-20 %: ambiguas entre bosque y pastura
  con árboles), no observado (0, 27) y píxeles sin dato.
- No bosque (0): todo lo demás (pasturas, agricultura, pastizales, agua, etc.).
"""

import numpy as np

FOREST = 1
NON_FOREST = 0
IGNORE = 255

MAPBIOMAS_ASSET = (
    "projects/mapbiomas-public/assets/chaco/lulc/collection5/"
    "mapbiomas_chaco_collection5_integration_v2"
)
MAPBIOMAS_YEARS = range(1985, 2024)  # Colección 5: 1985-2023

FOREST_CODES = (3, 4, 6)
IGNORE_CODES = (0, 27, 45)

CLASS_NAMES = {
    0: "No observado", 3: "Leñosas cerradas", 4: "Leñosas abiertas",
    6: "Leñosas inundables", 9: "Plantación forestal", 11: "Pastizal inundable",
    12: "Pastizal", 15: "Pastura", 18: "Agricultura", 19: "Cultivos anuales",
    21: "Mosaico de usos", 22: "Área sin vegetación", 24: "Área urbana",
    25: "Otras áreas sin vegetación", 26: "Cuerpo de agua", 27: "No observado",
    33: "Río, lago", 42: "Pastizal abierto", 43: "Pastizal cerrado",
    44: "Pastizal disperso", 45: "Leñosas dispersas", 57: "Cultivo simple",
    58: "Cultivo múltiple", 61: "Salar",
}


def remap_mapbiomas(codes: np.ndarray, valid: np.ndarray | None = None) -> np.ndarray:
    """Convierte códigos MapBiomas a {0: no bosque, 1: bosque, 255: ignorar}."""
    codes = np.asarray(codes)
    out = np.full(codes.shape, NON_FOREST, dtype=np.uint8)
    out[np.isin(codes, FOREST_CODES)] = FOREST
    out[np.isin(codes, IGNORE_CODES)] = IGNORE
    if valid is not None:
        out[~np.asarray(valid, dtype=bool)] = IGNORE
    return out


def change_label(y_t1: np.ndarray, y_t2: np.ndarray) -> np.ndarray:
    """Pérdida de bosque: 1 si era bosque en T1 y no bosque en T2.

    0 si no hubo pérdida (incluye no bosque estable y regeneración);
    255 si cualquiera de las dos fechas es ignorada.
    """
    out = np.zeros(y_t1.shape, dtype=np.uint8)
    out[(y_t1 == FOREST) & (y_t2 == NON_FOREST)] = 1
    out[(y_t1 == IGNORE) | (y_t2 == IGNORE)] = IGNORE
    return out
