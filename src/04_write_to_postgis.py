"""Write sampled slope and elevation back into the transit stop table."""

import os

os.environ.pop("PROJ_LIB", None)

import geopandas as gpd
from sqlalchemy import create_engine, text

DB_URL = os.environ["SEOUL_TRANSIT_DB"]
SRC = "data/stops_slope.gpkg"

gdf = gpd.read_file(SRC, layer="stops")
print(f"{len(gdf)} rows read from {SRC}")

engine = create_engine(DB_URL)

# staging table, then a single UPDATE join — avoids row-by-row writes
gdf[["node_id", "elev_m", "slope_pct"]].to_sql(
    "stop_terrain_staging", engine, if_exists="replace", index=False
)

with engine.begin() as conn:
    conn.execute(text('''
        ALTER TABLE public.bus_stop_location
            ADD COLUMN IF NOT EXISTS elev_m    REAL,
            ADD COLUMN IF NOT EXISTS slope_pct REAL
    '''))
    result = conn.execute(text('''
        UPDATE public.bus_stop_location AS b
        SET elev_m    = s.elev_m,
            slope_pct = s.slope_pct
        FROM stop_terrain_staging AS s
        WHERE b."노드id" = s.node_id
    '''))
    print(f"{result.rowcount} rows updated")
    conn.execute(text("DROP TABLE stop_terrain_staging"))