#!/usr/bin/env python3
"""Fase 3: entrenar la U-Net de pérdida de bosque y medirla contra una línea base dNDVI.

Uso (desde la raíz del repo):
    .venv\\Scripts\\python.exe scripts/fase3_train.py

Lee data/processed/dataset-v1 (index.csv + patches/*.npz) y escribe:
    models/unet-v1.pt                  pesos del mejor epoch según validación (no va a Git)
    outputs/fase3/training_log.csv     pérdida y métricas por epoch
    outputs/fase3/metrics.json         métricas finales en test: U-Net vs dNDVI

Reglas para no hacer trampa:
- El epoch y el umbral se eligen SOLO con validación; test se mide una única vez al final.
- La línea base dNDVI usa el mismo protocolo (umbral elegido en validación).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import torch  # noqa: E402

from chaco_monitor.model import UNet, confusion, masked_loss, scores  # noqa: E402

THRESHOLDS = [round(float(t), 2) for t in np.arange(0.10, 0.91, 0.05)]
NDVI_THRESHOLDS = [round(float(t), 3) for t in np.arange(-0.60, 0.01, 0.025)]


def load_split(dataset: Path, split: str) -> tuple[np.ndarray, np.ndarray, list[str]]:
    with (dataset / "index.csv").open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["split"] == split]
    if not rows:
        raise SystemExit(f"El split '{split}' está vacío en {dataset / 'index.csv'}")
    xs, ys = [], []
    for r in rows:
        d = np.load(dataset / r["path"])
        xs.append(np.concatenate([d["x_t1"], d["x_t2"]]).astype(np.float32))
        ys.append(d["change"].astype(np.uint8))
    return np.stack(xs), np.stack(ys), [r["patch_id"] for r in rows]


def augment(x: torch.Tensor, y: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Rotaciones de 90° y espejado: el bosque no tiene 'arriba'."""
    k = random.randint(0, 3)
    x, y = torch.rot90(x, k, (-2, -1)), torch.rot90(y, k, (-2, -1))
    if random.random() < 0.5:
        x, y = torch.flip(x, (-1,)), torch.flip(y, (-1,))
    return x, y


@torch.no_grad()
def predict(model: UNet, x: np.ndarray, device: str, batch: int = 8) -> np.ndarray:
    model.eval()
    out = [torch.sigmoid(model(torch.from_numpy(x[i:i + batch]).to(device))).cpu().numpy()[:, 0]
           for i in range(0, len(x), batch)]
    return np.concatenate(out)


def best_threshold(prob: np.ndarray, y: np.ndarray, thresholds, below: bool = False):
    """Umbral con mejor F1. below=True: predice pérdida si valor < umbral (para dNDVI)."""
    best = None
    for t in thresholds:
        s = scores(confusion(prob < t if below else prob >= t, y))
        if best is None or s["f1"] > best[1]["f1"]:
            best = (t, s)
    return best


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", type=Path, default=Path("data/processed/dataset-v1"))
    p.add_argument("--model-out", type=Path, default=Path("models/unet-v1.pt"))
    p.add_argument("--out", type=Path, default=Path("outputs/fase3"))
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--base", type=int, default=16, help="ancho de la U-Net (16 = ~0,5 M parámetros)")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    x_tr, y_tr, _ = load_split(args.dataset, "train")
    x_va, y_va, _ = load_split(args.dataset, "val")
    print(f"train {len(x_tr)} parches, val {len(x_va)} parches, dispositivo {device}")

    model = UNet(in_channels=x_tr.shape[1], base=args.base).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    xt, yt = torch.from_numpy(x_tr), torch.from_numpy(y_tr).long()

    args.out.mkdir(parents=True, exist_ok=True)
    args.model_out.parent.mkdir(parents=True, exist_ok=True)
    log, best_iou, best_epoch, start = [], -1.0, 0, time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        order, total = torch.randperm(len(xt)), 0.0
        for i in range(0, len(xt), args.batch):
            idx = order[i:i + args.batch]
            pairs = [augment(xt[j], yt[j]) for j in idx]
            xb = torch.stack([a for a, _ in pairs]).to(device)
            yb = torch.stack([b for _, b in pairs]).to(device)
            loss = masked_loss(model(xb)[:, 0], yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * len(idx)
        sched.step()
        val = scores(confusion(predict(model, x_va, device) >= 0.5, y_va))
        log.append({"epoch": epoch, "train_loss": round(total / len(xt), 4), **{f"val_{k}": v for k, v in val.items()}})
        if val["iou"] > best_iou:
            best_iou, best_epoch = val["iou"], epoch
            torch.save({"state_dict": model.state_dict(), "in_channels": x_tr.shape[1], "base": args.base,
                        "epoch": epoch, "band_order": ["B02", "B03", "B04", "B08", "NDVI"] * 2}, args.model_out)
        print(f"epoch {epoch:3d}  loss {log[-1]['train_loss']:.4f}  val IoU {val['iou']:.3f}  F1 {val['f1']:.3f}")

    with (args.out / "training_log.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(log[0]))
        w.writeheader()
        w.writerows(log)

    # Elegir umbral con validación usando el mejor modelo; recién después tocar test.
    ckpt = torch.load(args.model_out, map_location=device)
    model.load_state_dict(ckpt["state_dict"])
    thr, val_best = best_threshold(predict(model, x_va, device), y_va, THRESHOLDS)
    dndvi_va = x_va[:, 9] - x_va[:, 4]
    ndvi_thr, ndvi_val = best_threshold(dndvi_va, y_va, NDVI_THRESHOLDS, below=True)
    ckpt["threshold"] = thr
    torch.save(ckpt, args.model_out)

    x_te, y_te, ids_te = load_split(args.dataset, "test")
    test_unet = scores(confusion(predict(model, x_te, device) >= thr, y_te))
    test_ndvi = scores(confusion((x_te[:, 9] - x_te[:, 4]) < ndvi_thr, y_te))

    metrics = {
        "dataset": str(args.dataset), "device": device, "seed": args.seed, "epochs": args.epochs,
        "params": n_params, "train_seconds": round(time.time() - start, 1),
        "best_epoch": best_epoch, "unet_threshold": thr, "dndvi_threshold": ndvi_thr,
        "n_patches": {"train": len(x_tr), "val": len(x_va), "test": len(x_te)},
        "val": {"unet": val_best, "dndvi": ndvi_val},
        "test": {"unet": test_unet, "dndvi": test_ndvi},
        "test_patches": ids_te,
        "note": "Etiquetas = pseudoetiquetas MapBiomas Chaco Col. 5 (30 m remuestreado a 10 m).",
    }
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nMejor epoch {best_epoch} (val IoU {best_iou:.3f}); umbral U-Net {thr}, umbral dNDVI {ndvi_thr}")
    print("TEST           IoU     F1  precisión  recall   ha pred / ha ref")
    for name, s in (("U-Net", test_unet), ("dNDVI", test_ndvi)):
        print(f"{name:10s}  {s['iou']:.3f}  {s['f1']:.3f}     {s['precision']:.3f}   {s['recall']:.3f}"
              f"   {s['loss_ha_pred']:.1f} / {s['loss_ha_ref']:.1f}")
    print(f"\nModelo: {args.model_out}\nMétricas: {args.out / 'metrics.json'}")


if __name__ == "__main__":
    main()
