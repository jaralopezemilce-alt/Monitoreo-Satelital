"""Modelo de fase 3: U-Net chica para detectar pérdida de bosque entre dos fechas.

Entrada: 10 canales = [B02, B03, B04, B08, NDVI] de 2022 + los mismos 5 de 2023.
Salida: 1 canal (logit). Probabilidad de pérdida = sigmoid(logit).
Se escribe a mano, sin librerías extra, para que el equipo pueda leerla completa.
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from chaco_monitor.labels import IGNORE

IN_CHANNELS = 10


class DoubleConv(nn.Sequential):
    """Dos convoluciones 3x3 + BatchNorm + ReLU: el bloque básico de la U-Net."""

    def __init__(self, cin: int, cout: int):
        super().__init__(
            nn.Conv2d(cin, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
            nn.Conv2d(cout, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
        )


class UNet(nn.Module):
    """U-Net de 4 niveles. Con base=16 tiene ~0,5 M parámetros: entrena en CPU."""

    def __init__(self, in_channels: int = IN_CHANNELS, base: int = 16):
        super().__init__()
        c = [base, base * 2, base * 4, base * 8]
        self.enc = nn.ModuleList([DoubleConv(in_channels, c[0]), DoubleConv(c[0], c[1]),
                                  DoubleConv(c[1], c[2]), DoubleConv(c[2], c[3])])
        self.up = nn.ModuleList([nn.ConvTranspose2d(c[i], c[i - 1], 2, stride=2) for i in (3, 2, 1)])
        self.dec = nn.ModuleList([DoubleConv(c[i], c[i - 1]) for i in (3, 2, 1)])
        self.head = nn.Conv2d(c[0], 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        skips = []
        for i, block in enumerate(self.enc):          # bajada: 128 -> 64 -> 32 -> 16
            x = block(x if i == 0 else F.max_pool2d(x, 2))
            skips.append(x)
        x = skips.pop()
        for up, dec in zip(self.up, self.dec):         # subida con conexiones de salto
            x = dec(torch.cat([up(x), skips.pop()], dim=1))
        return self.head(x)


def masked_loss(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """BCE + Dice sólo sobre píxeles con etiqueta (target != 255)."""
    mask = target != IGNORE
    if not mask.any():
        return logits.sum() * 0
    y = target[mask].float()
    z = logits[mask]
    bce = F.binary_cross_entropy_with_logits(z, y)
    p = torch.sigmoid(z)
    dice = 1 - (2 * (p * y).sum() + 1) / (p.sum() + y.sum() + 1)
    return bce + dice


def confusion(pred: np.ndarray, target: np.ndarray) -> dict[str, int]:
    """Matriz de confusión binaria ignorando 255. pred y target: arrays 0/1(/255)."""
    m = target != IGNORE
    p, t = pred[m].astype(bool), target[m] == 1
    return {"tp": int(np.sum(p & t)), "fp": int(np.sum(p & ~t)),
            "fn": int(np.sum(~p & t)), "tn": int(np.sum(~p & ~t))}


def scores(c: dict[str, int]) -> dict[str, float]:
    """Precisión, recall, F1 e IoU de la clase pérdida, más exactitud global."""
    tp, fp, fn, tn = c["tp"], c["fp"], c["fn"], c["tn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    total = tp + fp + fn + tn
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "iou": round(iou, 4), "accuracy": round((tp + tn) / total, 4) if total else 0.0,
            "loss_ha_pred": round((tp + fp) * 100 / 1e4, 2),
            "loss_ha_ref": round((tp + fn) * 100 / 1e4, 2)}
