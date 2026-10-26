"""Amplía A/B a cuadrados métricos de 10 km, sin activar C ni definir splits."""

import json
from pathlib import Path

import numpy as np
from pyproj import Transformer


def main() -> None:
    """Genera geometría y grilla exacta de 1000×1000 celdas de 10 m por zona."""
    repo = Path(__file__).resolve().parents[1]
    zones = json.loads((repo / "configs/candidate_zones.geojson").read_text())
    features = []
    for zone in zones["features"]:
        if zone["properties"]["status"] != "approved":
            continue
        crs = zone["properties"]["target_crs"]
        points = np.array(zone["geometry"]["coordinates"][0][:-1])
        lon, lat = points.mean(axis=0)
        x, y = Transformer.from_crs(4326, crs, always_xy=True).transform(lon, lat)
        x, y = round(x/10)*10, round(y/10)*10
        left, bottom, right, top = x-5000, y-5000, x+5000, y+5000
        reverse = Transformer.from_crs(crs, 4326, always_xy=True)
        ring = [list(reverse.transform(e,n)) for e,n in [
            (left,bottom),(right,bottom),(right,top),(left,top),(left,bottom)
        ]]
        properties = dict(zone["properties"])
        properties.update({
            "purpose":"historical_training_inputs_no_labels_yet",
            "grid":{"transform":[10,0,left,0,-10,top], "shape":[1000,1000]},
            "area_km2_projected":100,
        })
        features.append({"type":"Feature","properties":properties,
                         "geometry":{"type":"Polygon","coordinates":[ring]}})
    (repo / "configs/training_zones.geojson").write_text(
        json.dumps({"type":"FeatureCollection","features":features},indent=2),encoding="utf-8")


if __name__ == "__main__":
    main()
