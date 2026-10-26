"""Copia sólo evidencia ligera y genera manifiesto SHA-256 de datos de prospección."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil


def digest(path: Path) -> str:
    """Calcula hash en bloques para no cargar un raster completo en RAM."""
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            result.update(block)
    return result.hexdigest()


def main() -> None:
    """Empaqueta metadatos/miniaturas y nunca copia los rasters a Git."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    target = args.repo / "docs/evidence"
    target.mkdir(parents=True, exist_ok=True)
    for source in (args.research / "review").iterdir():
        if source.name.endswith(("_overview.jpg", "_audit.jpg", "_audit_samples.json")) \
                or source.name in {"selected_scenes.csv", "selected_items.json"}:
            shutil.copy2(source, target / source.name)
    candidates = json.loads((args.research / "evidence/candidates.json").read_text())
    shutil.copy2(args.research / "evidence/candidates.json", target / "candidates.json")
    # GeoJSON importable en QGIS, con el orden lon/lat explícito.
    features = []
    for candidate in candidates:
        west, south, east, north = candidate["bbox"]
        features.append({
            "type":"Feature",
            "properties":{"id":candidate["id"], "status":"candidate_not_approved"},
            "geometry":{"type":"Polygon", "coordinates":[[
                [west,south], [east,south], [east,north], [west,north], [west,south]
            ]]},
        })
    config = args.repo / "configs"
    config.mkdir(exist_ok=True)
    (config / "candidate_zones.geojson").write_text(
        json.dumps({"type":"FeatureCollection", "features":features}, indent=2),
        encoding="utf-8",
    )
    # URL verificada por la prospección, sin fabricar enlaces de almacenamiento.
    files = []
    for tile in sorted((args.research / "raw").glob("lossyear_*.tif")):
        suffix = tile.stem.replace("lossyear_", "")
        url = next(c["gfc_url"] for c in candidates if c["gfc_url"].endswith(suffix+".tif"))
        files.append({
            "filename":tile.name, "bytes":tile.stat().st_size, "sha256":digest(tile),
            "source_url":url, "dataset":"Hansen GFC 2025 v1.13", "license":"CC-BY-4.0",
            "purpose":"prospection_not_training_labels",
        })
    (args.repo / "manifests/source_files.json").write_text(
        json.dumps({"inspection_date":"2026-10-26", "files":files}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
