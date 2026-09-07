"""Check numerical and geospatial contracts."""

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform


def test_mercator_scale(modules):
    assert modules["slope"].mercator_scale() == pytest.approx(0.7934, abs=1e-8)
    assert modules["slope"].mercator_scale(0) == 1.0
    assert modules["slope"].mercator_scale(60) == 0.5


def test_slope_command_applies_scale(modules, monkeypatch):
    calls = []
    monkeypatch.setattr(modules["slope"].subprocess, "run",
                        lambda args, **kwargs: calls.append((args, kwargs)))
    modules["slope"].generate_slopes("input.tif", "corrected.tif", "raw.tif")
    assert [call[0] for call in calls] == [
        ["gdaldem", "slope", "input.tif", "corrected.tif", "-p", "-s", "0.7934"],
        ["gdaldem", "slope", "input.tif", "raw.tif", "-p", "-s", "1.0"],
    ]
    assert all(options["check"] for _, options in calls)
    assert all("PROJ_LIB" not in options["env"] for _, options in calls)


def test_reprojection_metadata_and_extent(modules, dem, tmp_path):
    output = tmp_path / "warped.tif"
    modules["warp"].reproject_dem(dem, output)
    with rasterio.open(output) as ds:
        assert ds.crs.to_epsg() == 3857
        assert ds.dtypes == ("float32",)
        assert ds.nodata == -9999.0
        assert ds.profile["tiled"]
        assert ds.width > 0 and ds.height > 0
        xs, ys = transform("EPSG:4326", "EPSG:3857", [127.005], [37.495])
        assert ds.bounds.left < xs[0] < ds.bounds.right
        assert ds.bounds.bottom < ys[0] < ds.bounds.top


def test_nodata_hole_survives_warp(modules, dem, tmp_path):
    output = tmp_path / "warped.tif"
    modules["warp"].reproject_dem(dem, output)
    with rasterio.open(output) as ds:
        values = ds.read(1, masked=True)
        xs, ys = transform("EPSG:4326", "EPSG:3857", [127.0165], [37.4835])
        row, col = ds.index(xs[0], ys[0])
        assert values.mask[row, col]
        assert values.mask.any() and (~values.mask).any()
        assert values.compressed().min() >= 0
        assert values.compressed().max() <= 310


def test_zero_elevation_is_valid(modules, dem, tmp_path):
    source = tmp_path / "zero.tif"
    with rasterio.open(dem) as ds:
        profile = ds.profile.copy()
    profile["nodata"] = None
    with rasterio.open(source, "w", **profile) as ds:
        ds.write(np.zeros((32, 32), dtype="float32"), 1)
    output = tmp_path / "warped.tif"
    modules["warp"].reproject_dem(source, output)
    with rasterio.open(output) as ds:
        values = ds.read(1, masked=True)
        assert values.count() > 900
        assert np.all(values.compressed() == 0)


def test_reprojection_to_contour_geopackage(modules, dem, tmp_path):
    output, gpkg = tmp_path / "warped.tif", tmp_path / "contours.gpkg"
    modules["warp"].reproject_dem(dem, output)
    modules["contours"].generate_contours(output, gpkg)
    lines = gpd.read_file(gpkg, layer="contours")
    assert lines.crs.to_epsg() == 3857
    assert set(lines.elev_m) == {50, 100, 150, 200, 250, 300}
    assert lines.geometry.is_valid.all()
    assert (lines.geometry.geom_type == "LineString").all()
    assert (lines.length > 0).all()


def test_contours_use_pixel_centres(modules, tmp_path):
    source, output = tmp_path / "plane.tif", tmp_path / "plane.gpkg"
    with rasterio.open(source, "w", driver="GTiff", width=8, height=8, count=1,
                       dtype="float32", crs="EPSG:3857",
                       transform=from_origin(1000, 2000, 10, 10)) as ds:
        ds.write(np.tile(np.arange(8, dtype="float32") * 10, (8, 1)), 1)
    lines = modules["contours"].generate_contours(source, output, interval=20, min_elev=20)
    for row in lines.itertuples():
        coords = np.asarray(row.geometry.coords)
        assert np.allclose(coords[:, 0], 1005 + row.elev_m)
        assert coords[:, 1].min() == pytest.approx(1925)
        assert coords[:, 1].max() == pytest.approx(1995)


def test_contours_do_not_bridge_nodata(modules, dem, tmp_path):
    lines = modules["contours"].generate_contours(dem, tmp_path / "masked.gpkg")
    from shapely.geometry import box
    # This box is strictly inside the missing-data hole.
    hole = box(127.014, 37.481, 127.019, 37.486)
    assert not lines.intersects(hole).any()


def test_empty_dem_has_clear_error(modules, dem, tmp_path):
    source = tmp_path / "empty.tif"
    with rasterio.open(dem) as ds:
        profile = ds.profile.copy()
    with rasterio.open(source, "w", **profile) as ds:
        ds.write(np.full((32, 32), -32768, dtype="float32"), 1)
    with pytest.raises(ValueError, match="no elevations"):
        modules["contours"].generate_contours(source, tmp_path / "empty.gpkg")


def test_invalid_parameters_are_rejected(modules, dem, tmp_path):
    for latitude in (90, -90, float("nan")):
        with pytest.raises(ValueError):
            modules["slope"].mercator_scale(latitude)
    with pytest.raises(ValueError, match="interval"):
        modules["contours"].generate_contours(dem, tmp_path / "invalid.gpkg", interval=0)
