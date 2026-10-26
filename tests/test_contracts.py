"""Pruebas locales: no requieren internet, imágenes ni GPU."""

import pytest

from chaco_monitor.contracts import bbox_area_km2, require_area_limit


def test_small_bbox_has_plausible_metric_area():
    """0,01 grados de lado a esta latitud equivale aproximadamente a 1,15 km²."""
    assert 1.0 < bbox_area_km2([-60.01, -22.01, -60.0, -22.0]) < 1.3


@pytest.mark.parametrize(
    "bbox",
    [[-60, -22, -61, -21], [-60, -22, -59, -23], [0, 0, 0, 1],
     [float("nan"), 0, 1, 1], [-181, 0, 0, 1], [0, 0, 1]],
)
def test_invalid_bbox_is_rejected(bbox):
    with pytest.raises(ValueError):
        bbox_area_km2(bbox)


def test_limit_is_enforced():
    with pytest.raises(ValueError, match="supera"):
        require_area_limit([-60.1, -22.1, -60.0, -22.0])


def test_small_area_is_accepted():
    assert require_area_limit([-60.01, -22.01, -60.0, -22.0]) < 4.0
