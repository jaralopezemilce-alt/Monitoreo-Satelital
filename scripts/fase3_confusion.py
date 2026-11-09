r"""Recalcula la matriz de confusión de PRUEBA (TP, FP, FN, TN) por píxel.

Clase positiva: pérdida de bosque. Excluye píxeles 255 (no observables).
Usa las mismas funciones que scripts/fase3_train.py (load_split, predict, confusion).

Uso (desde la carpeta del repo):
    .\.venv\Scripts\python.exe scripts\fase3_confusion.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from chaco_monitor.model import UNet, confusion, scores  # noqa: E402
from fase3_train import load_split, predict  # noqa: E402

DATASET = ROOT / "data/processed/dataset-v1"
MODELOS = {"U-Net semilla 42": "models/unet-v1.pt",
           "U-Net semilla 1": "models/unet-seed1.pt",
           "U-Net semilla 2": "models/unet-seed2.pt"}
DNDVI_UMBRAL = -0.125   # elegido en validación (ver outputs/fase3/metrics.json)


def fila(nombre, umbral, c):
    s = scores(c)
    total = c["tp"] + c["fp"] + c["fn"] + c["tn"]
    return {"metodo": nombre, "umbral": umbral, **c, "total_evaluados": total,
            "iou": s["iou"], "f1": s["f1"], "precision": s["precision"], "recall": s["recall"],
            "accuracy": s["accuracy"]}


x_te, y_te, ids = load_split(DATASET, "test")
print(f"Parches de prueba: {len(ids)}")
print(f"Píxeles excluidos (255): {int((y_te == 255).sum())}\n")

out = []
for nombre, ruta in MODELOS.items():
    p = ROOT / ruta
    if not p.exists():
        print(f"{nombre}: no encontré {ruta}, se omite\n")
        continue
    ck = torch.load(p, map_location="cpu")
    m = UNet(in_channels=ck["in_channels"], base=ck["base"])
    m.load_state_dict(ck["state_dict"])
    thr = float(ck["threshold"])
    out.append(fila(nombre, thr, confusion(predict(m, x_te, "cpu") >= thr, y_te)))

dndvi = x_te[:, 9] - x_te[:, 4]
out.append(fila("Línea base dNDVI", DNDVI_UMBRAL, confusion(dndvi < DNDVI_UMBRAL, y_te)))

for r in out:
    print(f"{r['metodo']}  (umbral {r['umbral']})")
    for k in ("tp", "fp", "fn", "tn"):
        print(f"  {k.upper()}: {r[k]}")
    print(f"  Total de píxeles evaluados: {r['total_evaluados']}")
    print(f"  IoU {r['iou']}  F1 {r['f1']}  Precisión {r['precision']}  Recall {r['recall']}\n")

dest = ROOT / "outputs/fase3_confusion_test.json"
dest.write_text(json.dumps({"parches_test": ids, "resultados": out}, indent=2, ensure_ascii=False),
                encoding="utf-8")
print(f"Guardado en {dest}")
