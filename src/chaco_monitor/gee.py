"""Utilidades de Google Earth Engine compartidas por los scripts de las fases 1 y 2.

Requiere `requirements-gee.txt` y una cuenta autenticada (`earthengine authenticate`).
El Project ID se lee de la variable de entorno GEE_PROJECT: las dos integrantes
usan el mismo proyecto de Google Cloud.
"""

import io
import os
import zipfile
from pathlib import Path

import requests

S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
CLOUD_SCORE = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
SPECTRAL_BANDS = ["B2", "B3", "B4", "B8"]          # Azul, Verde, Rojo, NIR (10 m)
EXTRA_BANDS = ["B11", "B12"]                        # SWIR (20 m), sólo fase 1
NODATA = -9999


def init_ee():
    """Inicializa Earth Engine con el proyecto compartido del equipo."""
    import ee

    project = os.environ.get("GEE_PROJECT", "").strip()
    if not project:
        raise SystemExit(
            "Falta GEE_PROJECT. En PowerShell:  $env:GEE_PROJECT=\"id-del-proyecto\"\n"
            "(permanente: setx GEE_PROJECT \"id-del-proyecto\" y reabrir la terminal)"
        )
    try:
        ee.Initialize(project=project)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=project)
    return ee


def s2_composite(ee, region, start: str, end: str, bands: list[str],
                 clear_threshold: float = 0.60, max_scene_cloud: float = 60):
    """Mediana Sentinel-2 L2A sin nubes (Cloud Score+), en reflectancia 0-1.

    Devuelve (imagen, cantidad_de_escenas).
    """
    col = (ee.ImageCollection(S2_COLLECTION)
           .filterBounds(region)
           .filterDate(start, end)
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_scene_cloud))
           .linkCollection(ee.ImageCollection(CLOUD_SCORE), ["cs_cdf"])
           .map(lambda img: img.updateMask(img.select("cs_cdf").gte(clear_threshold))))
    n = col.size().getInfo()
    if n == 0:
        raise ValueError(f"Sin escenas Sentinel-2 entre {start} y {end}: ampliá la ventana.")
    return col.select(bands).median().divide(10000).clip(region), n


def download_geotiff(image, region, path: Path, scale: int, crs: str) -> Path:
    """Descarga directa (límite de GEE ~48 MB por petición). Maneja ZIP o TIFF."""
    url = image.getDownloadURL({
        "region": region, "scale": scale, "crs": crs,
        "format": "GEO_TIFF", "filePerBand": False,
    })
    response = requests.get(url, timeout=(15, 600))
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = response.content
    if content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            name = next(n for n in archive.namelist() if n.endswith(".tif"))
            content = archive.read(name)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_bytes(content)
    temporary.replace(path)
    return path
