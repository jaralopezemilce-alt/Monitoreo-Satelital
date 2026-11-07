"""Pruebas de la API con un paquete sintético. Se saltan si faltan torch o fastapi."""

import importlib
import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

torch = pytest.importorskip("torch")
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from chaco_monitor.model import UNet  # noqa: E402

LEFT, TOP = 744980, 7591690   # esquina de A_boqueron (EPSG:32720)


def _write(path, data, dtype, transform, nodata):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = data if data.ndim == 3 else data[None]
    with rasterio.open(path, "w", driver="GTiff", height=data.shape[1], width=data.shape[2],
                       count=data.shape[0], dtype=dtype, crs="EPSG:32720",
                       transform=transform, nodata=nodata) as dst:
        dst.write(data.astype(dtype))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    inputs, size = tmp_path / "inputs", 400
    records = []
    for role, dt in (("historical_2022_0", "2022-10-21T14:18:51Z"),
                     ("historical_2023_1", "2023-09-21T14:18:52Z")):
        stack = np.full((5, size, size), 0.2, dtype=np.float32)
        folder = inputs / "A_boqueron" / dt[:10]
        _write(folder / "stack.tif", stack, "float32", from_origin(LEFT, TOP, 10, 10), -9999)
        valid = np.ones((size, size))
        valid[:50, :50] = 0                     # una esquina sin dato
        _write(folder / "valid.tif", valid, "uint8", from_origin(LEFT, TOP, 10, 10), None)
        records.append({"zone": "A_boqueron", "role": role, "datetime": dt})
    (inputs / "manifest.json").write_text(json.dumps({"records": records}))
    model_path = tmp_path / "m.pt"
    torch.save({"state_dict": UNet(base=4).state_dict(), "in_channels": 10, "base": 4,
                "epoch": 1, "threshold": 0.5}, model_path)
    monkeypatch.setenv("CHACO_INPUTS", str(inputs))
    monkeypatch.setenv("CHACO_LABELS", str(tmp_path / "no-hay"))
    monkeypatch.setenv("CHACO_MODEL", str(model_path))
    import api.main as main
    main = importlib.reload(main)
    return TestClient(main.app)


def _inner_bbox(client, frac=0.3):
    w, s, e, n = client.get("/zones").json()[0]["bbox"]
    dx, dy = (e - w) * frac, (n - s) * frac
    return [w + dx, s + dy, e - dx, n - dy]


def test_health_and_zones(client):
    assert client.get("/health").json()["status"] == "ok"
    zones = client.get("/zones").json()
    assert zones[0]["id"] == "A_boqueron" and zones[0]["shape"] == [400, 400]


def test_predict_returns_real_model_output(client):
    r = client.post("/predict", json={"zone": "A_boqueron", "bbox": _inner_bbox(client)})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["valid_pct"] == 100.0 and j["loss_ha"] == pytest.approx(j["loss_px"] * 0.01)
    assert j["loss_geojson"]["type"] == "FeatureCollection"
    assert j["mapbiomas"] is None            # sin etiquetas en disco, no se inventa referencia


def test_predict_errors(client):
    bbox = _inner_bbox(client)
    assert client.post("/predict", json={"zone": "Z", "bbox": bbox}).status_code == 404
    assert client.post("/predict", json={"zone": "A_boqueron", "bbox": [-61, -21.9, -60.9, -21.8]}).status_code == 422
    assert client.post("/predict", json={"zone": "A_boqueron", "bbox": bbox[::-1]}).status_code == 422


def test_area_limit(client, monkeypatch):
    import api.main as main
    monkeypatch.setattr(main, "MAX_AREA_KM2", 0.1)
    r = client.post("/predict", json={"zone": "A_boqueron", "bbox": _inner_bbox(client)})
    assert r.status_code == 422 and "supera" in r.json()["detail"]


def test_no_valid_pixels_is_not_zero_hectares(client):
    w, s, e, n = client.get("/zones").json()[0]["bbox"]
    # esquina noroeste: los primeros 50 x 50 px no tienen dato
    r = client.post("/predict", json={"zone": "A_boqueron",
                                      "bbox": [w + 0.0012, n - 0.0035, w + 0.0035, n - 0.0012]})
    assert r.status_code == 422 and "no evaluable" in r.json()["detail"]


def test_rgb_background(client):
    r = client.get("/zones/A_boqueron/rgb/historical_2023_1.png")
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"
    assert len(r.headers["x-bounds"].split(",")) == 4
