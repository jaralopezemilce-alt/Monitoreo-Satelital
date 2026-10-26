"""Conversión de clases MapBiomas Chaco (Colección 5) a bosque / no bosque.

Códigos oficiales de la leyenda 'mapbiomas-chaco' del toolkit de MapBiomas
(https://github.com/mapbiomas/user-toolkit/blob/master/data/legends.js).

Regla de seguridad: sólo se asigna "no bosque" a códigos EXPLÍCITAMENTE listados.
Cualquier otro valor (nodata 255 de la exportación, códigos desconocidos,
no observado) se IGNORA. Así un píxel sin dato nunca se cuenta como no bosque.

DECISIÓN DEL EQUIPO (pendiente de aprobación, ver docs/fase2-dataset.md):
- Bosque (1): leñosas cerradas (3, >= 65 %), abiertas (4, 20-65 %), inundables (6).
- Ignorar (255): leñosas dispersas (45), no observado (0, 27), nodata (255),
  códigos no listados.
- No bosque (0): códigos de NON_FOREST_CODES.
"""

import numpy as np

FOREST = 1
NON_FOREST = 0
IGNORE = 255
LABEL_NODATA = 255  # nodata de export_mapbiomas_pilot.js y fase2_export_mapbiomas.py

MAPBIOMAS_ASSET = (
    "projects/mapbiomas-public/assets/chaco/lulc/collection5/"
    "mapbiomas_chaco_collection5_integration_v2"
)
MAPBIOMAS_YEARS = range(1985, 2024)  # Colección 5: 1985-2023

FOREST_CODES = (3, 4, 6)
NON_FOREST_CODES = (
    9,              # plantación forestal (no es bosque nativo)
    10, 11, 12, 13, 42, 43, 44,   # vegetación herbácea / pastizales
    14, 15, 18, 19, 20, 21, 36, 39, 40, 41, 57, 58, 62,  # agropecuario
    22, 23, 24, 25, 29, 30, 61,   # sin vegetación, urbano, salares
    26, 31, 33,     # agua
)

CLASS_NAMES = {
    0: "No observado", 3: "Leñosas cerradas", 4: "Leñosas abiertas",
    6: "Leñosas inundables", 9: "Plantación forestal", 11: "Pastizal inundable",
    12: "Pastizal", 15: "Pastura", 18: "Agricultura", 19: "Cultivos anuales",
    21: "Mosaico de usos", 22: "Área sin vegetación", 24: "Área urbana",
    25: "Otras áreas sin vegetación", 26: "Cuerpo de agua", 27: "No observado",
    33: "Río, lago", 42: "Pastizal abierto", 43: "Pastizal cerrado",
    44: "Pastizal disperso", 45: "Leñosas dispersas", 57: "Cultivo simple",
    58: "Cultivo múltiple", 61: "Salar", 255: "Sin dato (nodata)",
}


def remap_mapbiomas(codes: np.ndarray, valid: np.ndarray | None = None) -> np.ndarray:
    """Convierte códigos MapBiomas a {0: no bosque, 1: bosque, 255: ignorar}.

    Por defecto todo es IGNORE; sólo las listas explícitas producen 0 o 1.
    """
    codes = np.asarray(codes)
    out = np.full(codes.shape, IGNORE, dtype=np.uint8)
    out[np.isin(codes, NON_FOREST_CODES)] = NON_FOREST
    out[np.isin(codes, FOREST_CODES)] = FOREST
    if valid is not None:
        out[~np.asarray(valid, dtype=bool)] = IGNORE
    return out


def unknown_codes(codes: np.ndarray) -> dict[int, int]:
    """Códigos presentes que no están en ninguna lista (para auditar la leyenda)."""
    known = set(FOREST_CODES) | set(NON_FOREST_CODES) | {0, 27, 45, LABEL_NODATA}
    values, counts = np.unique(np.asarray(codes), return_counts=True)
    return {int(v): int(c) for v, c in zip(values, counts) if int(v) not in known}


def change_label(y_t1: np.ndarray, y_t2: np.ndarray) -> np.ndarray:
    """Pérdida de bosque: 1 si era bosque en T1 y no bosque en T2.

    0 si no hubo pérdida (incluye no bosque estable y regeneración);
    255 si cualquiera de las dos fechas es ignorada.
    """
    out = np.zeros(y_t1.shape, dtype=np.uint8)
    out[(y_t1 == FOREST) & (y_t2 == NON_FOREST)] = 1
    out[(y_t1 == IGNORE) | (y_t2 == IGNORE)] = IGNORE
    return out
