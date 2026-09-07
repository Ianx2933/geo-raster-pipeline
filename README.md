# geo-raster-pipeline

A raster–vector interoperability pipeline over a Copernicus GLO-30 DEM covering
Seoul: reprojects to Web Mercator with a block-streamed warp, publishes a
validated Cloud Optimized GeoTIFF, derives elevation isolines to GeoPackage,
generates XYZ terrain tiles, and joins slope statistics against 11,480 transit
stop geometries held in PostGIS.

![Bus stops over terrain](docs/stops_over_dem.png)

*Seoul bus stops (white) over the reprojected DEM. Stops trace the road network
and visibly avoid the mountain masses — Bukhansan to the north, Gwanaksan to the
south-west.*

---

## Result

Of **11,480 Seoul bus stops**, **4,536 (39.5%)** sit on terrain steeper than an
8% grade — the threshold above which a slope stops being wheelchair-accessible
under most accessibility standards. Median grade across all stops is 6.51%.

The same calculation **without correcting for Web Mercator scale distortion
returns 3,279 stops (28.6%)** — an undercount of 28%. That gap is the whole
argument for understanding the projection you are working in, and it is
discussed under [Web Mercator scale correction](#web-mercator-scale-correction)
below.

![Slope classified stops over hillshade](docs/slope_vs_stops.png)

*Stops above 8% grade in red, at or below in white, over a hillshade of the same
DEM. The steep stops are not confined to the mountain fringes: central districts
carry them throughout.*

---

## Pipeline

| Step | Implementation | Output |
|---|---|---|
| 1. Mosaic two GLO-30 tiles | `gdalbuildvrt` | 7200 × 3600, EPSG:4326 |
| 2. Reproject to Web Mercator | `src/01_reproject.py` | 6810 × 4292, EPSG:3857 |
| 3. Cloud Optimized GeoTIFF | `rio cogeo` | 6144 × 4096, zoom-12 aligned |
| 4. Contours to GeoPackage | `src/02_contours.py` | 19,653 lines, 50–1500 m |
| 5. XYZ terrain tiles | `gdal2tiles` | 1,934 tiles, zoom 8–13 |
| 6. Slope stats joined to stops | `src/03_slope_stats.py` | 11,480 stops, GPKG + CSV |

### Data

- **Elevation:** Copernicus GLO-30 Public DEM, tiles `N37_00_E126_00` and
  `N37_00_E127_00`, fetched from the AWS Open Data registry. Seoul straddles the
  127°E tile boundary, so both are required and mosaicked with
  `gdalbuildvrt` before any processing.
- **Transit stops:** `bus_stop_location` from
  [SeoulTransitPlatform](https://github.com/Ianx2933/SeoulTransitPlatform),
  a PostGIS database of Seoul public transport data. 11,480 point geometries,
  EPSG:4326, all populated.

---

## Notes on the implementation

### Memory-bound processing

Step 2 warps the mosaic band by band through `rasterio.band()`, which streams
512 × 512 blocks rather than materialising the array. The reprojected raster is
117 MB uncompressed (6810 × 4292 Float32); peak process memory stays well below
that.

Step 4 deliberately does the opposite and reads the full band into memory.
Contouring needs global continuity — tiled contouring produces lines broken at
every block edge and requires a stitching pass to repair. Reprojection is a
per-pixel operation and parallelises across blocks with no such cost. The choice
of strategy follows the operation, not a blanket rule.

Step 6 samples three rasters at 11,480 point locations through
`rasterio.sample()`, which reads only the blocks containing those points.

### Web Mercator scale correction

Web Mercator measures distance in metres at the equator. At Seoul's latitude of
roughly 37.5°N, a pixel reported as 32.69 m spans about 25.9 m on the ground —
inflated by 1 / cos(37.5°) ≈ 1.26.

Slope is rise over run. Overstating the run by 26% understates every gradient by
the same proportion. `gdaldem` accepts a scale factor for exactly this:

```bash
gdaldem slope dem_3857.tif slope.tif -p -s 0.7934    # cos(37.5°)
```

Both the corrected and uncorrected rasters are sampled, and the pipeline reports
both figures. The difference is not marginal: 4,536 stops against 3,279.

### NoData

Copernicus GLO-30 has no NoData value set — ocean is stored as elevation 0
rather than as missing data, and `gdalinfo -stats` confirms 100% valid pixels.
The pipeline introduces `-9999` explicitly on reprojection.

This also drives the contour floor. Starting levels at 0 m would trace the entire
Yellow Sea coastline as a contour; the pipeline starts at 50 m instead.

### Known limitation: DSM, not DTM

Copernicus GLO-30 is a Digital *Surface* Model. It includes buildings,
infrastructure, and vegetation. In a dense city a stop that falls near a tall
building's edge can inherit that structure's height difference as terrain slope.

The ten steepest stops were checked individually against terrain and imagery.
Most sit on genuine hillside roads — the steepest, at 60.2%, is on the approach
to Bukhansan, directly below a cliff face, with contour lines visibly bunched
around it. At least one, in a flat commercial district, is likely a building
artefact.

The 39.5% figure should therefore be read as an upper bound. A bare-earth DTM —
Korea's national 5 m 수치표고모델 is the obvious candidate — would settle it.

A second, separate limitation: at 30 m resolution, slope describes the terrain
gradient across the pixel containing a stop, not the gradient a passenger stands
on. A stop on level pavement beside a steep drop registers as steep. For
accessibility purposes this is arguably the more useful reading — reaching the
stop still means crossing the slope — but it is not the same measurement.

### Environment

Three separate GDAL/PROJ installations coexist on the development machine
(PostgreSQL/PostGIS, QGIS via OSGeo4W, and pip-installed rasterio). PostgreSQL
exports `PROJ_LIB` globally, pointing at a PROJ database older than the one
rasterio's bundled PROJ 9.x will accept, which surfaces as
`CRSError: The EPSG code is unknown` on any CRS lookup.

Each script clears the variable for its own process rather than unsetting it
system-wide, which would break PostGIS:

```python
os.environ.pop("PROJ_LIB", None)   # before importing rasterio
```

CLI tools need the same treatment per shell session (`$env:PROJ_LIB=""`).

Contour extraction uses `ContourSet.get_paths()`; `allsegs` was removed in
matplotlib 3.10.

---

## Running it

```bash
pip install -r requirements.txt
```

GDAL command-line tools (`gdalbuildvrt`, `gdaldem`, `gdal2tiles`) are not
installed by pip and come with QGIS via the OSGeo4W Shell.

```bash
# 1. mosaic
gdalbuildvrt data/dem_raw.vrt data/Copernicus_DSM_COG_10_N37_00_E12*.tif

# 2. reproject
python src/01_reproject.py

# 3. cloud optimized geotiff
rio cogeo create data/dem_3857.tif data/dem_cog.tif --web-optimized
rio cogeo validate data/dem_cog.tif

# 4. contours
python src/02_contours.py

# 5. terrain derivatives and tiles
gdaldem slope     data/dem_3857.tif data/slope.tif -p -s 0.7934
gdaldem slope     data/dem_3857.tif data/slope_uncorrected.tif -p
gdaldem hillshade data/dem_3857.tif data/hillshade.tif
gdal2tiles -z 8-13 --xyz -x --processes 4 data/hillshade.tif tiles/

# 6. join to PostGIS
export SEOUL_TRANSIT_DB="postgresql+psycopg2://user:pass@localhost:5432/Seoul_Transit"
python src/03_slope_stats.py
```

Raster outputs and the tile pyramid are not committed; the scripts regenerate
them from the two source tiles.

---

## Stack

Python (rasterio, GeoPandas, Shapely, SQLAlchemy), GDAL/OGR, rio-cogeo,
PostgreSQL 18 / PostGIS 3.6, QGIS.

## Licence

Terrain data: Copernicus WorldDEM™-30 © DLR e.V. 2010–2014 and © Airbus Defence
and Space GmbH 2014–2018, provided under COPERNICUS by the European Union and
ESA.
