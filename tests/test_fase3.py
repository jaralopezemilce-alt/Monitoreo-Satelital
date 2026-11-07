"""Pruebas de fase 3 con datos sintéticos. Se saltan si torch no está instalado."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from chaco_monitor.model import UNet, confusion, masked_loss, scores  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_unet_shape():
    out = UNet(base=4)(torch.zeros(2, 10, 64, 64))
    assert out.shape == (2, 1, 64, 64)


def test_metrics_ignore_255():
    pred = np.array([1, 1, 0, 0, 1])
    target = np.array([1, 0, 1, 0, 255])
    c = confusion(pred, target)
    assert c == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}
    assert scores(c)["iou"] == pytest.approx(1 / 3, abs=1e-4)


def test_loss_ignores_255():
    logits = torch.tensor([[5.0, -5.0, 100.0]])
    a = masked_loss(logits, torch.tensor([[1, 0, 255]]))
    b = masked_loss(logits[:, :2], torch.tensor([[1, 0]]))
    assert torch.isclose(a, b)


def _dataset(tmp_path, n=6, size=32):
    rng = np.random.default_rng(0)
    (tmp_path / "patches").mkdir()
    rows = []
    for i in range(n):
        change = np.zeros((size, size), np.uint8)
        change[: size // 2] = 1
        change[0, 0] = 255
        x1 = rng.random((5, size, size), dtype=np.float32)
        x2 = x1.copy()
        x2[4][change == 1] -= 0.5           # baja el NDVI donde hay pérdida
        pid = f"p{i}"
        np.savez_compressed(tmp_path / "patches" / f"{pid}.npz", x_t1=x1, x_t2=x2, change=change)
        rows.append({"patch_id": pid, "split": ["train", "train", "train", "train", "val", "test"][i],
                     "path": f"patches/{pid}.npz"})
    with (tmp_path / "index.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return tmp_path


def test_train_end_to_end(tmp_path):
    (tmp_path / "ds").mkdir()
    ds = _dataset(tmp_path / "ds")
    out, model = tmp_path / "out", tmp_path / "m.pt"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "fase3_train.py"), "--dataset", str(ds),
                    "--out", str(out), "--model-out", str(model), "--epochs", "2", "--base", "4"],
                   check=True, capture_output=True, text=True)
    m = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert set(m["test"]) == {"unet", "dndvi"}
    assert m["test"]["dndvi"]["f1"] > 0.9          # la señal sintética es obvia para dNDVI
    assert "threshold" in torch.load(model, map_location="cpu")
