"""Write DEM contours to GeoPackage."""

import os

# Clear the conflicting PostGIS PROJ path.
os.environ.pop("PROJ_LIB", None)

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")  # Run without a display.
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from shapely.geometry import LineString

SRC = "data/dem_3857.tif"
DST = "data/contours.gpkg"
INTERVAL = 50  # Elevation spacing in metres.
MIN_ELEV = 50  # Exclude sea-level contours.


def generate_contours(source=SRC, destination=DST, interval=INTERVAL, min_elev=MIN_ELEV):
    """Use pixel centres and respect masks."""
    if not np.isfinite(interval) or interval <= 0 or not np.isfinite(min_elev):
        raise ValueError("Contour interval must be positive and levels must be finite")
    with rasterio.open(source) as src:
        arr = src.read(1, masked=True)
        transform, crs = src.transform, src.crs
    if arr.count() == 0 or float(arr.max()) <= min_elev:
        raise ValueError("DEM has no elevations above the contour floor")
    levels = np.arange(min_elev, float(arr.max()), interval)
    fig, ax = plt.subplots()
    rows = []
    try:
        cs = ax.contour(arr, levels=levels, corner_mask=False)
        for level, path in zip(cs.levels, cs.get_paths()):
            for vertices in path.to_polygons(closed_only=False):
                if len(vertices) < 2:
                    continue
                # Array indices locate centres, not corners.
                coords = [transform @ (x + 0.5, y + 0.5) for x, y in vertices]
                rows.append({"elev_m": float(level), "geometry": LineString(coords)})
    finally:
        plt.close(fig)
    if not rows:
        raise ValueError("DEM produced no contour lines")
    gdf = gpd.GeoDataFrame(rows, crs=crs)
    gdf.to_file(destination, layer="contours", driver="GPKG", mode="w")
    return gdf


def main():
    """Run the default pipeline step."""
    gdf = generate_contours()
    print(f"{len(gdf)} contour lines written to {DST}")
    print(gdf["elev_m"].value_counts().sort_index().head(10))


if __name__ == "__main__":
    main()
