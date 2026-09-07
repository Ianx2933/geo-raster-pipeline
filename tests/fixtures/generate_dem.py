"""Build a small known-answer DEM."""

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin


def main():
    """Write a ramp with a central nodata hole."""
    data = np.tile(np.arange(32, dtype="float32") * 10, (32, 1))
    data[12:21, 12:21] = -32768
    with rasterio.open(Path(__file__).with_name("tiny_dem.tif"), "w", driver="GTiff",
                       width=32, height=32, count=1, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(127, 37.5, 0.001, 0.001),
                       nodata=-32768, compress="deflate") as ds:
        ds.write(data, 1)


if __name__ == "__main__":
    main()
