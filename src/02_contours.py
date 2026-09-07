"""Derive elevation contours from the DEM and write them to a GeoPackage."""

import os

os.environ.pop("PROJ_LIB", None)

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")          # no GUI needed
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from shapely.geometry import LineString

SRC = "data/dem_3857.tif"
DST = "data/contours.gpkg"
INTERVAL = 50                  # metres between contour lines
MIN_ELEV = 50                  # skip sea level: ocean is stored as 0, not nodata

with rasterio.open(SRC) as src:
    arr = src.read(1, masked=True)
    transform = src.transform
    crs = src.crs

levels = np.arange(MIN_ELEV, int(arr.max()) + INTERVAL, INTERVAL)
print(f"contouring {len(levels)} levels: {levels[0]}–{levels[-1]} m")

fig, ax = plt.subplots()
cs = ax.contour(arr, levels=levels)

rows = []
for level, path in zip(cs.levels, cs.get_paths()):
    for vertices in path.to_polygons(closed_only=False):
        if len(vertices) < 2:
            continue
        coords = [transform * (x, y) for x, y in vertices]
        rows.append({"elev_m": float(level),
                     "geometry": LineString(coords)})

plt.close(fig)

gdf = gpd.GeoDataFrame(rows, crs=crs)
gdf.to_file(DST, layer="contours", driver="GPKG")

print(f"{len(gdf)} contour lines written to {DST}")
print(gdf["elev_m"].value_counts().sort_index().head(10))