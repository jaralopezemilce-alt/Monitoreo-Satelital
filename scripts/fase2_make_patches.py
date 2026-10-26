"""Fase 2b: parte el área en bloques train/val/test y corta parches de 128 x 128.

Lee los GeoTIFF de fase2_export_gee.py (una zona, dos años) y guarda un .npz por
parche con:
    x_t1, x_t2   float32 (5, 128, 128)  B2, B3, B4, B8, NDVI (reflectancia 0-1)
    y_t1, y_t2   uint8   (128, 128)     0 no bosque, 1 bosque, 255 ignorar
    change       uint8   (128, 128)     1 pérdida T1->T2, 0 sin pérdida, 255 ignorar

y un índice CSV con el split de cada parche. No requiere internet.

Uso:
    .\\.venv\\Scripts\\python.exe scripts/fase2_make_patches.py --zones A_boqueron B_alto_paraguay C_presidente_hayes
"""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from chaco_monitor.labels import IGNORE, change_label, remap_mapbiomas  # noqa: E402
from chaco_monitor.patches import assign_blocks, iter_patches, normalize_features  # noqa: E402


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--zones", nargs="+", required=True)
    p.add_argument("--t1", type=int, default=2022)
    p.add_argument("--t2", type=int, default=2023)
    p.add_argument("--src", type=Path, default=Path("data/interim/gee"))
    p.add_argument("--out", type=Path, default=Path("data/processed/patches"))
    p.add_argument("--patch-px", type=int, default=128)
    p.add_argument("--block-px", type=int, default=256, help="bloque espacial = 2 x 2 parches")
    p.add_argument("--min-valid", type=float, default=0.80, help="fracción mínima de píxeles útiles")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def read_year(path: Path):
    with rasterio.open(path) as src:
        data = src.read()
        meta = {"crs": str(src.crs), "transform": tuple(src.transform)[:6], "shape": data.shape[1:]}
    x, valid_px = normalize_features(data[:5])
    valid = valid_px & (data[5] == 1)
    y = remap_mapbiomas(data[6], valid)
    return x, y, meta


def main():
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rows, summary = [], Counter()
    for zone in args.zones:
        x1, y1, m1 = read_year(args.src / f"{zone}_{args.t1}.tif")
        x2, y2, m2 = read_year(args.src / f"{zone}_{args.t2}.tif")
        if m1 != m2:
            raise SystemExit(f"{zone}: las dos fechas no comparten grilla ({m1} vs {m2})")
        change = change_label(y1, y2)
        height, width = m1["shape"]
        splits = assign_blocks(height // args.block_px, width // args.block_px, seed=args.seed)

        for br, bc, r, c in iter_patches(height, width, args.block_px, args.patch_px):
            win = np.s_[r:r + args.patch_px, c:c + args.patch_px]
            p_y1, p_y2, p_ch = y1[win], y2[win], change[win]
            useful = float(np.mean(p_ch != IGNORE))
            if useful < args.min_valid:
                summary["descartados_por_nubes_o_ignorados"] += 1
                continue
            split = splits[(br, bc)]
            patch_id = f"{zone}_{args.t1}_{args.t2}_r{r:04d}_c{c:04d}"
            rel = Path(split) / f"{patch_id}.npz"
            (args.out / split).mkdir(exist_ok=True)
            np.savez_compressed(args.out / rel, x_t1=x1[(slice(None),) + win], x_t2=x2[(slice(None),) + win],
                                y_t1=p_y1, y_t2=p_y2, change=p_ch)
            rows.append({
                "patch_id": patch_id, "zone": zone, "split": split, "block": f"{br}_{bc}",
                "row": r, "col": c, "useful_frac": round(useful, 3),
                "forest_frac_t1": round(float(np.mean(p_y1 == 1)), 3),
                "forest_frac_t2": round(float(np.mean(p_y2 == 1)), 3),
                "loss_px": int(np.sum(p_ch == 1)), "path": rel.as_posix(),
            })
            summary[f"{split}_parches"] += 1
            summary[f"{split}_px_perdida"] += int(np.sum(p_ch == 1))

    with (args.out / "index.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["patch_id"])
        writer.writeheader()
        writer.writerows(rows)
    config = vars(args) | {"src": str(args.src), "out": str(args.out), "summary": dict(summary)}
    (args.out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Resumen del dataset:")
    for key in sorted(summary):
        print(f"  {key:36s} {summary[key]:>8,}")
    print(f"Índice: {args.out / 'index.csv'}")


if __name__ == "__main__":
    main()
