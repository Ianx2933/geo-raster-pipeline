"""Reproject a DEM with a streamed warp."""

import os

# Clear the conflicting PostGIS PROJ path.
os.environ.pop("PROJ_LIB", None)

import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling

SRC = "data/dem_raw.vrt"
DST = "data/dem_3857.tif"
CRS = "EPSG:3857"
NODATA = -9999.0          # Explicit output sentinel.

def reproject_dem(source=SRC, destination=DST):
    """Preserve source nodata during warping."""
    with rasterio.open(source) as src:
        transform, width, height = calculate_default_transform(
            src.crs, CRS, src.width, src.height, *src.bounds
        )
    
        profile = src.profile | {
            "driver": "GTiff",        # Override the VRT driver.
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
            "predictor": 3,           # Float compression.
            "BIGTIFF": "IF_SAFER",
        }
    
        with rasterio.open(destination, "w", **profile) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    src_nodata=src.nodata,
                    dst_transform=transform,
                    dst_crs=CRS,
                    dst_nodata=NODATA,
                    resampling=Resampling.bilinear,
                )
    return width, height


def main():
    """Run the default pipeline step."""
    width, height = reproject_dem()
    print(f"{width} x {height} written to {DST}")


if __name__ == "__main__":
    main()
