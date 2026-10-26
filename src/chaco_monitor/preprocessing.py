"""Transformaciones espectrales y espaciales; no genera etiquetas de bosque."""

import math

import numpy as np
from rasterio import Affine
from rasterio.warp import transform_bounds


BANDS = ("blue", "green", "red", "nir")
CHANNELS = ("B02", "B03", "B04", "B08", "NDVI")

def effective_radiometry(item: dict, band: str) -> dict:
    """Resuelve el offset ya aplicado en Earth Search sin aplicarlo dos veces.

    https://github.com/Element84/earth-search/issues/41
    Sólo cubre las colecciones verificadas; casos desconocidos requieren revisión.
    """
    metadata = dict(item["assets"][band]["raster:bands"][0])
    collection = item.get("collection")
    if collection == "sentinel-2-l2a":
        applied = item["properties"].get("earthsearch:boa_offset_applied")
        if applied is True:
            metadata["offset"] = 0.0
        elif applied is not False:
            raise ValueError("La colección antigua requiere boa_offset_applied explícito")
    elif collection != "sentinel-2-c1-l2a":
        raise ValueError(f"Colección sin regla radiométrica verificada: {collection}")
    return metadata


def metric_grid(bbox: list, crs: str, resolution: float = 10.0):
    """Construye grilla UTM ajustada a múltiplos de resolución, compartida por fechas."""
    if resolution <= 0 or not math.isfinite(resolution):
        raise ValueError("La resolución debe ser positiva y finita")
    west, south, east, north = transform_bounds("EPSG:4326", crs, *bbox, densify_pts=21)
    left = math.floor(west / resolution) * resolution
    bottom = math.floor(south / resolution) * resolution
    right = math.ceil(east / resolution) * resolution
    top = math.ceil(north / resolution) * resolution
    return Affine(resolution, 0, left, 0, -resolution, top), (
        round((top-bottom)/resolution), round((right-left)/resolution)
    )


def to_reflectance(dn: np.ndarray, metadata: dict) -> np.ndarray:
    """Aplica escala/offset STAC y conserva nodata como NaN, sin recortar valores."""
    if not all(key in metadata for key in ("scale", "offset", "nodata")):
        raise ValueError("Faltan scale, offset o nodata explícitos en STAC")
    scale, offset = metadata["scale"], metadata["offset"]
    if not np.isfinite(scale) or scale <= 0 or not np.isfinite(offset):
        raise ValueError("Escala/offset inválidos")
    result = dn.astype("float32") * scale + offset
    result[dn == metadata["nodata"]] = np.nan
    return result


def ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDVI sobre reflectancia: excluye nodata, negativos y denominadores casi nulos."""
    if red.shape != nir.shape:
        raise ValueError("Las bandas deben compartir dimensiones")
    denominator = nir + red
    valid = np.isfinite(red) & np.isfinite(nir) & (red >= 0) & (nir >= 0)
    valid &= denominator > 1e-6
    output = np.full(red.shape, np.nan, dtype="float32")
    np.divide(nir-red, denominator, out=output, where=valid)
    return output


def dilate(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    """Dilata una máscara binaria con vecindad cuadrada; no necesita SciPy."""
    if radius < 0 or int(radius) != radius:
        raise ValueError("Radio entero no negativo requerido")
    padded = np.pad(mask.astype(bool), radius, constant_values=False)
    output = np.zeros(mask.shape, dtype=bool)
    for dy in range(2*radius+1):
        for dx in range(2*radius+1):
            output |= padded[dy:dy+mask.shape[0], dx:dx+mask.shape[1]]
    return output


def quality_mask(scl: np.ndarray, reflectance: np.ndarray, footprint: np.ndarray,
                 cloud_radius: int = 2) -> np.ndarray:
    """Acepta SCL 4/5/6; excluye nubes/sombra con margen y reflectancias fuera de [0,1].

    Es una máscara de observabilidad, NO una etiqueta de bosque. Agua es observable
    y no se convierte aquí en bosque ni no bosque.
    """
    if reflectance.shape != (4, *scl.shape) or footprint.shape != scl.shape:
        raise ValueError("Las capas deben compartir la misma grilla")
    obscured = dilate(np.isin(scl, [3, 8, 9, 10]), cloud_radius)
    spectral = np.all(np.isfinite(reflectance), axis=0)
    spectral &= np.all((reflectance >= 0) & (reflectance <= 1), axis=0)
    return footprint.astype(bool) & np.isin(scl, [4, 5, 6]) & ~obscured & spectral
