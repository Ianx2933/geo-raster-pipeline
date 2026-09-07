"""Sample slope and elevation at each Seoul bus stop and summarise the result."""

import os

os.environ.pop("PROJ_LIB", None)

import geopandas as gpd
import pandas as pd
import rasterio
from sqlalchemy import create_engine

DB_URL = os.environ["SEOUL_TRANSIT_DB"]      # set this before running
DEM = "data/dem_3857.tif"
SLOPE = "data/slope.tif"
SLOPE_RAW = "data/slope_uncorrected.tif"
GRADE_THRESHOLD = 8.0                         # percent

engine = create_engine(DB_URL)
stops = gpd.read_postgis(
    '''
    SELECT "노드id"    AS node_id,
           "정류장번호" AS stop_no,
           "정류장명"   AS stop_name,
           geom
    FROM public.bus_stop_location
    WHERE geom IS NOT NULL
    ''',
    engine,
    geom_col="geom",
)
print(f"{len(stops)} stops read from PostGIS ({stops.crs})")

stops = stops.to_crs("EPSG:3857")
coords = [(p.x, p.y) for p in stops.geometry]


def sample(path, column):
    with rasterio.open(path) as src:
        values = [v[0] for v in src.sample(coords)]
        nodata = src.nodata
    series = pd.Series(values, index=stops.index, dtype="float32")
    return series.where(series != nodata)


stops["elev_m"] = sample(DEM, "elev_m")
stops["slope_pct"] = sample(SLOPE, "slope_pct")
stops["slope_pct_raw"] = sample(SLOPE_RAW, "slope_pct_raw")

valid = stops["slope_pct"].notna().sum()
steep = (stops["slope_pct"] > GRADE_THRESHOLD).sum()
steep_raw = (stops["slope_pct_raw"] > GRADE_THRESHOLD).sum()

print(f"\nsampled          : {valid} of {len(stops)}")
print(f"elevation        : {stops['elev_m'].min():.0f}–{stops['elev_m'].max():.0f} m "
      f"(median {stops['elev_m'].median():.0f} m)")
print(f"slope            : median {stops['slope_pct'].median():.2f}%, "
      f"max {stops['slope_pct'].max():.1f}%")
print(f"above {GRADE_THRESHOLD:.0f}% grade : {steep} stops "
      f"({steep / valid * 100:.1f}%)")
print(f"  without Mercator scale correction: {steep_raw} stops "
      f"({steep_raw / valid * 100:.1f}%)")

print("\nsteepest stops:")
print(stops.nlargest(10, "slope_pct")[["stop_name", "elev_m", "slope_pct"]]
      .to_string(index=False))

stops.to_file("data/stops_slope.gpkg", layer="stops", driver="GPKG")
stops.drop(columns="geom").to_csv("docs/stop_slope_stats.csv", index=False)
print("\nwritten: data/stops_slope.gpkg, docs/stop_slope_stats.csv")