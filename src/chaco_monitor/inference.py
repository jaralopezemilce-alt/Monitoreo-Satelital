"""Inferencia de pérdida de bosque sobre los paquetes de ingesta (modo offline).

Funciones sin FastAPI para poder probarlas solas:
- ZoneStore: lee manifest.json, stack.tif y valid.tif de cada zona y fecha.
- predict_window: corre la U-Net sobre un recorte con margen de contexto.
- mask_to_geojson: convierte la máscara en polígonos WGS84 para el mapa.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
import torch
from pyproj import Transformer
from rasterio import features
from rasterio.warp import transform_geom
from rasterio.windows import Window

from chaco_monitor.labels import IGNORE, remap_mapbiomas
from chaco_monitor.model import UNet
from chaco_monitor.patches import prepare_features

PIXEL_HA = 0.01            # 10 m x 10 m = 100 m² = 0,01 ha
CONTEXT_PX = 32            # margen extra para que los bordes del recorte vean vecinos
PAIRS = {"historical": ("historical_2022_0", "historical_2023_1")}


@dataclass
class Zone:
    id: str
    crs: str
    transform: rasterio.Affine
    shape: tuple[int, int]
    bbox_wgs84: list[float]
    dates: dict[str, str]          # rol -> fecha/hora de adquisición
    folders: dict[str, Path]       # rol -> carpeta con stack.tif y valid.tif


class ZoneStore:
    """Zonas disponibles sin internet, a partir de la carpeta de ingesta."""

    def __init__(self, inputs: Path, labels: Path | None = None):
        self.inputs, self.labels = Path(inputs), Path(labels) if labels else None
        manifest = json.loads((self.inputs / "manifest.json").read_text(encoding="utf-8"))
        self.zones: dict[str, Zone] = {}
        for r in manifest["records"]:
            folder = self.inputs / r["zone"] / r["datetime"][:10]
            if not (folder / "stack.tif").exists():
                continue
            if r["zone"] not in self.zones:
                with rasterio.open(folder / "stack.tif") as src:
                    crs, tr, shape = src.crs.to_string(), src.transform, (src.height, src.width)
                    to_wgs = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
                    lons, lats = to_wgs.transform([src.bounds.left, src.bounds.right] * 2,
                                                  [src.bounds.bottom] * 2 + [src.bounds.top] * 2)
                self.zones[r["zone"]] = Zone(r["zone"], crs, tr, shape,
                                             [min(lons), min(lats), max(lons), max(lats)], {}, {})
            self.zones[r["zone"]].dates[r["role"]] = r["datetime"]
            self.zones[r["zone"]].folders[r["role"]] = folder

    def window_for_bbox(self, zone: Zone, bbox: list[float]) -> Window:
        """bbox WGS84 [oeste, sur, este, norte] -> ventana de píxeles en la grilla de la zona."""
        west, south, east, north = bbox
        if not (west < east and south < north):
            raise ValueError("bbox inválido: debe ser [oeste, sur, este, norte]")
        to_utm = Transformer.from_crs("EPSG:4326", zone.crs, always_xy=True)
        xs, ys = to_utm.transform([west, east, west, east], [south, south, north, north])
        inv = ~zone.transform
        cols, rows = zip(*(inv * (x, y) for x, y in zip(xs, ys)))
        c0, c1 = int(np.floor(min(cols))), int(np.ceil(max(cols)))
        r0, r1 = int(np.floor(min(rows))), int(np.ceil(max(rows)))
        h, w = zone.shape
        if c0 < 0 or r0 < 0 or c1 > w or r1 > h:
            raise LookupError("El área seleccionada sale de la zona precargada")
        return Window(c0, r0, c1 - c0, r1 - r0)

    def read(self, zone: Zone, role: str, window: Window) -> tuple[np.ndarray, np.ndarray]:
        folder = zone.folders[role]
        with rasterio.open(folder / "stack.tif") as src:
            stack = src.read(window=window, boundless=True, fill_value=-9999)
        with rasterio.open(folder / "valid.tif") as src:
            valid = src.read(1, window=window, boundless=True, fill_value=0)
        return prepare_features(stack, valid)

    def reference_loss(self, zone: Zone, window: Window, valid: np.ndarray) -> np.ndarray | None:
        """Pérdida según MapBiomas en la misma ventana, si las etiquetas están en disco."""
        if self.labels is None:
            return None
        from rasterio.enums import Resampling
        from rasterio.warp import reproject
        out = []
        for role in PAIRS["historical"]:
            year = int(zone.dates[role][:4])
            path = self.labels / f"{zone.id}_mapbiomas_c5_v2_{year}.tif"
            if not path.exists():
                return None
            codes = np.full((int(window.height), int(window.width)), IGNORE, dtype=np.uint8)
            with rasterio.open(path) as src:
                reproject(rasterio.band(src, 1), codes, src_nodata=src.nodata or IGNORE,
                          dst_transform=rasterio.windows.transform(window, zone.transform),
                          dst_crs=zone.crs, dst_nodata=IGNORE, resampling=Resampling.nearest)
            out.append(remap_mapbiomas(codes, valid))
        y1, y2 = out
        ref = np.full(y1.shape, IGNORE, dtype=np.uint8)
        known = (y1 != IGNORE) & (y2 != IGNORE)
        ref[known] = ((y1 == 1) & (y2 == 0))[known]
        return ref


def load_model(path: Path, device: str = "cpu") -> tuple[UNet, float, dict]:
    ckpt = torch.load(path, map_location=device)
    model = UNet(in_channels=ckpt["in_channels"], base=ckpt["base"]).to(device)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    info = {k: ckpt.get(k) for k in ("epoch", "base", "in_channels", "threshold")}
    return model, float(ckpt.get("threshold", 0.5)), info


@torch.no_grad()
def predict_window(model: UNet, store: ZoneStore, zone: Zone, window: Window,
                   pair: str = "historical") -> tuple[np.ndarray, np.ndarray]:
    """Probabilidad de pérdida y validez conjunta en la ventana pedida.

    Lee un margen de CONTEXT_PX alrededor y rellena hasta múltiplo de 16 (exigencia
    de la U-Net); al final recorta exactamente la ventana pedida.
    """
    m = CONTEXT_PX
    big = Window(window.col_off - m, window.row_off - m, window.width + 2 * m, window.height + 2 * m)
    r1, r2 = PAIRS[pair]
    x1, v1 = store.read(zone, r1, big)
    x2, v2 = store.read(zone, r2, big)
    x = np.concatenate([x1, x2])
    h, w = x.shape[1:]
    ph, pw = (-h) % 16, (-w) % 16
    x = np.pad(x, ((0, 0), (0, ph), (0, pw)), mode="reflect")
    prob = torch.sigmoid(model(torch.from_numpy(x)[None]))[0, 0].numpy()[:h, :w]
    valid = v1 & v2
    sl = (slice(m, m + int(window.height)), slice(m, m + int(window.width)))
    return prob[sl], valid[sl]


def _ring_area(ring) -> float:
    xs, ys = np.asarray(ring).T
    return 0.5 * abs(np.dot(xs, np.roll(ys, 1)) - np.dot(ys, np.roll(xs, 1)))


def mask_to_geojson(mask: np.ndarray, transform, crs: str, min_ha: float = 0.04) -> dict:
    """Polígonos WGS84 de los píxeles True. Descarta manchas menores a min_ha (4 píxeles).

    Las áreas se calculan en la proyección UTM de la zona, antes de pasar a lon/lat.
    """
    feats = []
    for geom, value in features.shapes(mask.astype(np.uint8), mask=mask, transform=transform):
        if value != 1:
            continue
        rings = geom["coordinates"]
        ha = (_ring_area(rings[0]) - sum(_ring_area(r) for r in rings[1:])) / 1e4
        if ha < min_ha:
            continue
        feats.append({"type": "Feature", "properties": {"ha": round(ha, 2)},
                      "geometry": transform_geom(crs, "EPSG:4326", geom, precision=6)})
    return {"type": "FeatureCollection", "features": feats}


def rgb_png(store: ZoneStore, zone: Zone, role: str, max_reflectance: float = 0.25):
    """Color verdadero (B04, B03, B02) de toda la zona, reproyectado a lon/lat.

    Es el fondo offline del visor. Devuelve (png_bytes, [oeste, sur, este, norte]).
    """
    from io import BytesIO

    from PIL import Image
    from rasterio.enums import Resampling
    from rasterio.warp import calculate_default_transform, reproject
    h, w = zone.shape
    x, valid = store.read(zone, role, Window(0, 0, w, h))
    rgb = np.clip(x[[2, 1, 0]] / max_reflectance, 0, 1) ** (1 / 1.5)
    src = np.concatenate([(rgb * 255).astype(np.uint8), (valid * 255).astype(np.uint8)[None]])
    left, top = zone.transform.c, zone.transform.f
    right, bottom = left + w * zone.transform.a, top + h * zone.transform.e
    dst_tr, dw, dh = calculate_default_transform(zone.crs, "EPSG:4326", w, h, left, bottom, right, top)
    dst = np.zeros((4, dh, dw), dtype=np.uint8)
    for band in range(4):
        reproject(src[band], dst[band], src_transform=zone.transform, src_crs=zone.crs,
                  dst_transform=dst_tr, dst_crs="EPSG:4326", resampling=Resampling.bilinear)
    bounds = [dst_tr.c, dst_tr.f + dh * dst_tr.e, dst_tr.c + dw * dst_tr.a, dst_tr.f]
    buf = BytesIO()
    Image.fromarray(np.ascontiguousarray(dst.transpose(1, 2, 0))).save(buf, "PNG", optimize=True)
    return buf.getvalue(), bounds
