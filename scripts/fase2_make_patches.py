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
import tempfile
import uuid
import warnings
from collections import Counter
from contextlib import contextmanager
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
                   help="reemplaza un dataset anterior solo después de generar la nueva salida")
    return p.parse_args()


def validate_output(out: Path, inputs: Path, labels: Path, overwrite: bool) -> Path:
    """Rechaza rutas sensibles, solapadas, enlazadas o con archivos ajenos.

    Resolver rutas evita que variantes como '../inputs' eludan la comparación.
    No se siguen enlaces simbólicos de salida, ni siquiera con --overwrite.
    """
    absolute = out.absolute()
    if any(p.is_symlink() for p in (absolute, *absolute.parents)):
        raise SystemExit("Salida insegura: no se admiten enlaces simbólicos.")
    out = out.resolve()
    protected = (inputs.resolve(), labels.resolve())
    for source in protected:
        if out == source or out in source.parents or source in out.parents:
            raise SystemExit("Salida insegura: se solapa con las imágenes o las etiquetas.")
    # Se permiten subcarpetas del repositorio, nunca reemplazar su raíz o ancestros.
    for root in (Path(__file__).resolve().parents[1], Path.cwd().resolve(), Path.home().resolve()):
        if out == root or out in root.parents:
            raise SystemExit("Salida insegura: raíz del repositorio, trabajo, hogar o ancestro.")
    if out.exists():
        if not out.is_dir():
            raise SystemExit("La salida debe ser una carpeta, no un archivo.")
        entries = {p.name for p in out.iterdir()}
        if entries and not overwrite:
            raise SystemExit(f"{out} ya contiene datos. Usá --overwrite para regenerar "
                             "un dataset reconocido u otra carpeta con --out.")
        if entries:
            if entries != {"index.csv", "config.json", "patches"}:
                raise SystemExit("Salida no reconocida como dataset: no se borrarán archivos ajenos.")
            if (not (out / "index.csv").is_file() or not (out / "config.json").is_file()
                    or not (out / "patches").is_dir()
                    or any(p.is_symlink() for p in out.rglob("*"))):
                raise SystemExit("Salida no reconocida o con enlaces simbólicos.")
    return out


def publish_dataset(staged: Path, out: Path) -> None:
    """Publica por renombrado en el mismo disco; restaura ante errores ordinarios.

    El respaldo queda fuera del temporal para no borrarlo si falla la restauración.
    No promete atomicidad ante un corte de energía entre los dos renombrados.
    """
    backup = out.parent / f".{out.name}.backup-{uuid.uuid4().hex}"
    had_previous = out.exists()
    if had_previous:
        out.rename(backup)
    try:
        staged.rename(out)
    except BaseException:
        if had_previous:
            try:
                backup.rename(out)
            except OSError as exc:
                raise RuntimeError(f"No se pudo restaurar: respaldo conservado en {backup}") from exc
        raise
    if had_previous:
        try:
            shutil.rmtree(backup)
        except OSError:
            warnings.warn(f"Dataset publicado; quedó un respaldo para revisar en {backup}")


@contextmanager
def output_transaction(args):
    """Aísla generación y errores; un bloqueo evita dos escritores simultáneos."""
    out = validate_output(args.out, args.inputs, args.labels, args.overwrite)
    out.parent.mkdir(parents=True, exist_ok=True)
    lock = out.parent / f".{out.name}.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise SystemExit(f"Salida bloqueada por otra corrida: {lock}. No borrar si sigue activa.")
    try:
        with handle:
            handle.write("Generación en curso; quitar solo tras verificar que terminó el proceso.\n")
        # Validar de nuevo después del bloqueo cierra la carrera entre dos invocaciones.
        validate_output(out, args.inputs, args.labels, args.overwrite)
        with tempfile.TemporaryDirectory(prefix=f".{out.name}.staging-", dir=out.parent) as temp:
            staged = Path(temp) / "dataset"
            staged.mkdir()
            yield staged
            publish_dataset(staged, out)
    finally:
        lock.unlink()


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


def build_dataset(args, work_dir: Path):
    """Genera archivos solamente en el temporal; el llamador controla la publicación."""
    manifest = json.loads((args.inputs / "manifest.json").read_text(encoding="utf-8"))
    by_zone = {}
    for record in manifest["records"]:
        if record["role"] in ROLES:
            by_zone.setdefault(record["zone"], {})[record["role"]] = record
    zones = args.zones or sorted(by_zone)
    patch_dir = work_dir / "patches"
    patch_dir.mkdir()

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

    with (work_dir / "index.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["patch_id"])
        writer.writeheader()
        writer.writerows(rows)
    config = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()}
    config.update({"zones": zones, "summary": dict(summary), "audit": audit})
    (work_dir / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary, audit


def main():
    """No publica resultados parciales si falla una lectura, cálculo o escritura."""
    args = parse_args()
    with output_transaction(args) as work_dir:
        summary, audit = build_dataset(args, work_dir)

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
