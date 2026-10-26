"""Regresiones de escala, nodata, NDVI, nubes y grilla métrica, sin red."""

import numpy as np
import pytest

from chaco_monitor.preprocessing import (
    dilate, effective_radiometry, metric_grid, ndvi, quality_mask, to_reflectance,
)


def test_offset_is_not_forgotten_and_nodata_is_not_negative_reflectance():
    values = to_reflectance(np.array([0, 1000, 3000]), {"scale": 0.0001, "offset": -0.1, "nodata": 0})
    assert np.isnan(values[0])
    np.testing.assert_allclose(values[1:], [0, 0.2], atol=1e-7)


def test_missing_scale_fails_instead_of_silently_assuming():
    with pytest.raises(ValueError):
        to_reflectance(np.array([3000]), {"nodata": 0})

@pytest.mark.parametrize("collection,flag,expected", [
    ("sentinel-2-l2a", True, 0.0),
    ("sentinel-2-l2a", False, -0.1),
    ("sentinel-2-c1-l2a", None, -0.1),
])
def test_effective_offset_depends_on_provider_processing(collection, flag, expected):
    item = {"collection":collection, "properties":{"earthsearch:boa_offset_applied":flag},
            "assets":{"red":{"raster:bands":[{"scale":0.0001,"offset":-0.1,"nodata":0}]}}}
    assert effective_radiometry(item, "red")["offset"] == expected
    assert item["assets"]["red"]["raster:bands"][0]["offset"] == -0.1


def test_ambiguous_old_collection_fails_closed():
    item = {"collection":"sentinel-2-l2a", "properties":{},
            "assets":{"red":{"raster:bands":[{"scale":0.0001,"offset":-0.1,"nodata":0}]}}}
    with pytest.raises(ValueError):
        effective_radiometry(item, "red")


def test_ndvi_matches_known_reflectance():
    np.testing.assert_allclose(ndvi(np.array([0.2]), np.array([0.6])), [0.5])


def test_ndvi_rejects_nodata_negative_and_zero_sum():
    assert np.isnan(ndvi(np.array([0, -0.1, np.nan]), np.array([0, 0.4, 0.4]))).all()


def test_ndvi_shape_mismatch():
    with pytest.raises(ValueError):
        ndvi(np.ones((2, 2)), np.ones((3, 3)))


def test_cloud_buffer_is_five_by_five_at_radius_two():
    mask = np.zeros((7, 7), dtype=bool)
    mask[3, 3] = True
    assert dilate(mask, 2).sum() == 25


def test_quality_is_not_a_forest_mask():
    scl = np.array([[4, 5, 6, 7, 0]], dtype="uint8")
    reflectance = np.full((4, 1, 5), 0.2)
    valid = quality_mask(scl, reflectance, np.ones((1, 5)), cloud_radius=0)
    assert valid.tolist() == [[True, True, True, False, False]]


def test_spectral_nodata_and_footprint_are_excluded():
    reflectance = np.full((4, 2, 2), 0.2)
    reflectance[0, 0, 0] = np.nan
    reflectance[1, 0, 1] = 1.2
    footprint = np.array([[1, 1], [1, 0]], dtype=bool)
    assert quality_mask(np.full((2, 2), 4), reflectance, footprint).sum() == 1


def test_grid_is_metric_and_repeatable():
    bbox = [-60.6, -21.824, -60.564, -21.788]
    transform, shape = metric_grid(bbox, "EPSG:32720")
    assert (transform, shape) == metric_grid(bbox, "EPSG:32720")
    assert transform.a == 10 and transform.e == -10
    assert transform.c % 10 == 0 and transform.f % 10 == 0
    assert 350 < shape[0] < 450 and 350 < shape[1] < 450
