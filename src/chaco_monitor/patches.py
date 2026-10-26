"""Partición espacial por bloques y extracción de parches (fase 2).

Reglas (README del repositorio):
- La partición se decide por BLOQUES espaciales antes de cortar parches, para que
  parches vecinos (casi idénticos) no queden en train y test a la vez.
- Todas las fechas de un bloque van al mismo conjunto.
- El split vive sólo en index.csv: los .npz se guardan en una única carpeta, así
  regenerar con otra semilla no puede dejar copias en carpetas de otro split.
"""

import random

import numpy as np

SPLITS = ("train", "val", "test")
STACK_NODATA = -9999.0  # nodata de stack.tif en la ingesta (prepare_pilot.py)


def assign_blocks(n_rows: int, n_cols: int, seed: int = 42,
                  fractions: tuple[float, float, float] = (0.70, 0.15, 0.15)
                  ) -> dict[tuple[int, int], str]:
    """Asigna cada bloque (fila, columna) a train/val/test de forma reproducible.

    Garantiza al menos un bloque de val y uno de test si hay 3 bloques o más.
    """
    blocks = [(r, c) for r in range(n_rows) for c in range(n_cols)]
    if not blocks:
        raise ValueError("No hay bloques: la ventana es menor que un bloque")
    random.Random(seed).shuffle(blocks)
    n = len(blocks)
    n_test = max(1, round(n * fractions[2])) if n >= 3 else 0
    n_val = max(1, round(n * fractions[1])) if n >= 3 else 0
    split = {}
    for i, block in enumerate(blocks):
        if i < n_test:
            split[block] = "test"
        elif i < n_test + n_val:
            split[block] = "val"
        else:
            split[block] = "train"
    return split


def iter_patches(height: int, width: int, block_px: int, patch_px: int):
    """Genera (fila_bloque, col_bloque, fila_px, col_px) sin cruzar bordes de bloque."""
    if block_px % patch_px:
        raise ValueError("block_px debe ser múltiplo de patch_px")
    for br in range(height // block_px):
        for bc in range(width // block_px):
            for pr in range(0, block_px, patch_px):
                for pc in range(0, block_px, patch_px):
                    yield br, bc, br * block_px + pr, bc * block_px + pc


def prepare_features(stack: np.ndarray, valid_mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """stack.tif (B02, B03, B04, B08, NDVI en float32, nodata -9999) -> x y validez.

    Un píxel es válido sólo si valid.tif == 1 y ningún canal es nodata/NaN.
    Los inválidos quedan en 0 en x y se ignoran en las etiquetas.
    """
    stack = stack.astype(np.float32)
    valid = (np.asarray(valid_mask) == 1)
    valid &= np.all(np.isfinite(stack) & (stack != STACK_NODATA), axis=0)
    x = np.where(valid[None], stack, 0.0).astype(np.float32)
    return x, valid
