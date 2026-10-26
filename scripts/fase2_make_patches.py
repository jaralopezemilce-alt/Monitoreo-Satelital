"""Fase 2b: une ingesta histórica + etiquetas MapBiomas y corta parches 128 x 128.

Entradas (fuera de Git):
    data/interim/historical-inputs-v1/   paquete de prepare_pilot.py (manifest.json,
                                         <zona>/<fecha>/stack.tif y valid.tif)
    data/interim/labels-mapbiomas-v1/    TIFF de fase2_export_mapbiomas.py o de
                                         export_mapbiomas_pilot.js (30 m, nodata 255)

Las etiquetas de 30 m se llevan a la grilla de 10 m de stack.tif por vecino más
cercano (fuera de cobertura = 255 = ignorar). Cada parche se guarda UNA vez en
<out>/patches/<id>.npz con:
    x_t1, x_t2   float32 (5, 128, 128)  B02, B03, B04, B08, NDVI
    y_t1, y_t2   uint8   (128, 128)     0 no bosque, 1 bosque, 255 ignorar
    change       uint8   (128, 128)     1 pérdida T1->T2, 0 sin pérdida, 255 ignorar
El split (train/val/test) vive sólo en <out>/index.csv.

Uso:
    .\\.venv\\Scripts\\python.exe scripts/fase2_make_patches.py
    .\\.venv\\Scripts\\python.exe scripts/fase2_make_patches.py --seed 7 --overwrite
"""

import argparse
import csv
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from chaco_monitor.labels import IGNORE, LABEL_NODATA, change_label, remap_mapbiomas, unknown_codes  # noqa: E402
from chaco_monitor.patches import assign_blocks, iter_patches, prepare_features  # noqa: E402

ROLES = ("historical_2022_0", "historical_2023_1")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--inputs", type=Path, default=Path("data/interim/historical-inputs-v1"))
    p.add_argument("--labels", type=Path, default=Path("data/interim/labels-mapbiomas-v1"))
    p.add_argument("--out", type=Path, default=Path("data/processed/dataset-v1"))
    p.add_argument("--zones", nargs="+", default=None, help="por defecto, todas las del manifiesto")
    p.add_argument("--patch-px", type=int, default=128)
    p.add_argument("--block-px", type=int, default=256, help="bloque espacial = 2 x 2 parches")
    p.add_argument("--min-useful", type=float, default=0.80,
                   help="fracción mínima de píxeles con etiqueta de cambio no ignorada")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--overwrite", action="store_true",
                   help="borra <out> antes de escribir (necesario para regenerar)")
    return p.parse_args()


def prepare_output(out: Path, overwrite: bool) -> Path:
    """Evita mezclar corridas: <out> debe estar vacío o se borra con --overwrite."""
    if out.exists() and any(out.iterdir()):
        if not overwrite:
            raise SystemExit(f"{out} ya contiene un dataset. Usá --overwrite para regenerarlo "
                             "(se borra entero) u otra carpeta con --out.")
        shutil.rmtree(out)
    (out / "patches").mkdir(parents=True)
    return out / "patches"


def read_labels(path: Path, crs, transform, shape) -> np.ndarray:
    """Remuestrea códigos MapBiomas a la grilla Sentinel; lo no cubierto queda 255."""
    target = np.full(shape, LABEL_NODATA, dtype=np.uint8)
    with rasterio.open(path) as src:
        reproject(source=rasterio.band(src, 1), destination=target,
                  src_nodata=src.nodata if src.nodata is not None else LABEL_NODATA,
                  dst_transform=transform, dst_crs=crs, dst_nodata=LABEL_NODATA,
                  resampling=Resampling.nearest)
    return target


def load_date(inputs: Path, labels: Path, record: dict):
    folder = inputs / record["zone"] / record["datetime"][:10]
    with rasterio.open(folder / "stack.tif") as src:
        stack, crs, transform, shape = src.read(), src.crs, src.transform, (src.height, src.width)
    with rasterio.open(folder / "valid.tif") as src:
        valid_raw = src.read(1)
    x, valid = prepare_features(stack, valid_raw)
    year = int(record["datetime"][:4])
    codes = read_labels(labels / f"{record['zone']}_mapbiomas_c5_v2_{year}.tif", crs, transform, shape)
    return x, remap_mapbiomas(codes, valid), codes, (str(crs), tuple(transform)[:6], shape), year


def main():
    args = parse_args()
    manifest = json.loads((args.inputs / "manifest.json").read_text(encoding="utf-8"))
    by_zone = {}
    for record in manifest["records"]:
        if record["role"] in ROLES:
            by_zone.setdefault(record["zone"], {})[record["role"]] = record
    zones = args.zones or sorted(by_zone)
    patch_dir = prepare_output(args.out, args.overwrite)

    rows, summary, audit = [], Counter(), {}
    for zone in zones:
        if set(by_zone.get(zone, {})) != set(ROLES):
            raise SystemExit(f"{zone}: faltan fechas históricas en el manifiesto")
        x1, y1, c1, g1, year1 = load_date(args.inputs, args.labels, by_zone[zone][ROLES[0]])
        x2, y2, c2, g2, year2 = load_date(args.inputs, args.labels, by_zone[zone][ROLES[1]])
        if g1 != g2:
            raise SystemExit(f"{zone}: las dos fechas no comparten grilla")
        change = change_label(y1, y2)
        audit[zone] = {"unknown_codes_t1": unknown_codes(c1), "unknown_codes_t2": unknown_codes(c2),
                       "forest_pct_t1": round(float(np.mean(y1 == 1)) * 100, 2),
                       "forest_pct_t2": round(float(np.mean(y2 == 1)) * 100, 2),
                       "ignored_pct_change": round(float(np.mean(change == IGNORE)) * 100, 2),
                       "loss_ha": round(float(np.sum(change == 1)) * 100 / 1e4, 2)}
        height, width = g1[2]
        splits = assign_blocks(height // args.block_px, width // args.block_px, seed=args.seed)

        for br, bc, r, c in iter_patches(height, width, args.block_px, args.patch_px):
            win = np.s_[r:r + args.patch_px, c:c + args.patch_px]
            p_ch = change[win]
            useful = float(np.mean(p_ch != IGNORE))
            if useful < args.min_useful:
                summary["descartados_por_nodata_o_ignorados"] += 1
                continue
            split = splits[(br, bc)]
            patch_id = f"{zone}_{year1}_{year2}_r{r:04d}_c{c:04d}"
            np.savez_compressed(patch_dir / f"{patch_id}.npz",
                                x_t1=x1[(slice(None),) + win], x_t2=x2[(slice(None),) + win],
                                y_t1=y1[win], y_t2=y2[win], change=p_ch)
            rows.append({
                "patch_id": patch_id, "zone": zone, "split": split, "block": f"{br}_{bc}",
                "row": r, "col": c, "useful_frac": round(useful, 3),
                "forest_frac_t1": round(float(np.mean(y1[win] == 1)), 3),
                "forest_frac_t2": round(float(np.mean(y2[win] == 1)), 3),
                "loss_px": int(np.sum(p_ch == 1)), "path": f"patches/{patch_id}.npz",
            })
            summary[f"{split}_parches"] += 1
            summary[f"{split}_px_perdida"] += int(np.sum(p_ch == 1))

    with (args.out / "index.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["patch_id"])
        writer.writeheader()
        writer.writerows(rows)
    config = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()}
    config.update({"zones": zones, "summary": dict(summary), "audit": audit})
    (args.out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Auditoría por zona:")
    for zone, info in audit.items():
        print(f"  {zone}: {info}")
    print("Resumen del dataset:")
    for key in sorted(summary):
        print(f"  {key:36s} {summary[key]:>8,}")
    if summary["test_px_perdida"] == 0:
        print("  ATENCIÓN: test no tiene píxeles de pérdida; probar otra --seed o revisar zonas.")
    print(f"Índice: {args.out / 'index.csv'}")


if __name__ == "__main__":
    main()
