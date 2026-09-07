"""Reproject the Copernicus GLO-30 mosaic to Web Mercator, block by block."""

import os

# PostgreSQL/PostGIS sets PROJ_LIB globally to its own older PROJ database,
# which rasterio's bundled PROJ 9.x refuses to read. Clear it for this process.
os.environ.pop("PROJ_LIB", None)

import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling

SRC = "data/dem_raw.vrt"
DST = "data/dem_3857.tif"
CRS = "EPSG:3857"
NODATA = -9999.0          # source has none; we introduce one explicitly

with rasterio.open(SRC) as src:
    transform, width, height = calculate_default_transform(
        src.crs, CRS, src.width, src.height, *src.bounds
    )

    profile = src.profile | {
        "driver": "GTiff",        # src is a VRT — must override
        "crs": CRS,
        "transform": transform,
        "width": width,
        "height": height,
        "dtype": "float32",
        "nodata": NODATA,
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
        "compress": "deflate",
        "predictor": 3,           # float-aware compression
        "BIGTIFF": "IF_SAFER",
    }

    with rasterio.open(DST, "w", **profile) as dst:
        for i in range(1, src.count + 1):
            reproject(
                source=rasterio.band(src, i),
                destination=rasterio.band(dst, i),
                src_transform=src.transform,
                src_crs=src.crs,
                src_nodata=None,
                dst_transform=transform,
                dst_crs=CRS,
                dst_nodata=NODATA,
                resampling=Resampling.bilinear,
            )

print(f"{width} x {height} written to {DST}")