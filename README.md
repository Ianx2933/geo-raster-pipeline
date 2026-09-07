# geo-raster-pipeline

[![CI](https://github.com/Ianx2933/geo-raster-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/Ianx2933/geo-raster-pipeline/actions/workflows/ci.yml)

A raster–vector interoperability pipeline over a Copernicus GLO-30 DEM covering
Seoul: reprojects to Web Mercator with a block-streamed warp, publishes a
validated Cloud Optimized GeoTIFF, derives elevation isolines to GeoPackage,
generates XYZ terrain tiles, and joins slope statistics against 11,480 transit
stop geometries held in PostGIS.

The output is not a one-off analysis. It is published as an immutable, versioned
snapshot and served through the
[SeoulTransitPlatform](https://github.com/Ianx2933/SeoulTransitPlatform) API —
see [Publication](#publication) below.

![Bus stops over terrain](docs/stops_over_dem.png)

*Seoul bus stops (white) over the reprojected DEM. Stops trace the road network
and visibly avoid the mountain masses — Bukhansan to the north, Gwanaksan to the
south-west.*

---

## Result

Of **11,480 Seoul bus stops**, **4,536 (39.5%)** sit on terrain at or above an
8% grade. Median grade across all stops is 6.51%.

The same calculation **without correcting for Web Mercator scale distortion
returns 3,279 stops (28.6%)** — an undercount of 28%. That gap is the whole
argument for understanding the projection you are working in, and it is
discussed under [Web Mercator scale correction](#web-mercator-scale-correction)
below.

Aggregated by administrative dong, the distribution is far from uniform. The
most affected dong is **Seonghyeon-dong (성현동), where 27 of 29 stops (93.1%)
are at or above 8%** — a small sample, but one that matches the terrain: the
dong sits on hillside. City-wide the figure is 39.5%; per-dong it ranges from
near zero on the Han River floodplain to over ninety percent on the slopes.

![Slope classified stops over hillshade](docs/slope_vs_stops.png)

*Stops at or above 8% grade in red, below in white, over a hillshade of the same
DEM. The steep stops are not confined to the mountain fringes: central districts
carry them throughout.*

**What this figure is and is not.** It measures terrain gradient across the 30 m
DEM cell containing each stop. It is not a measurement of footway gradient, and
it is not an accessibility assessment. Read it as a screening indicator that
narrows down where to survey, not as a verdict on any individual stop. The
[limitations](#known-limitation-dsm-not-dtm) below are part of the result, not a
footnote to it.

---

## Pipeline

| Step | Implementation | Output |
|---|---|---|
| 1. Mosaic two GLO-30 tiles | `gdalbuildvrt` | 7200 × 3600, EPSG:4326 |
| 2. Reproject to Web Mercator | `src/01_reproject.py` | 6810 × 4292, EPSG:3857 |
| 3. Cloud Optimized GeoTIFF | `rio cogeo` | 6144 × 4096, zoom-12 aligned |
| 4. Contours to GeoPackage | `src/02_contours.py` | 19,653 lines, 50–1500 m |
| 5. Slope rasters and XYZ terrain tiles | `src/05_slope.py`, `gdaldem`, `gdal2tiles` | corrected/raw slope rasters; 1,934 tiles, zoom 8–13 |
| 6. Slope stats joined to stops | `src/03_slope_stats.py` | 11,480 stops, GPKG + CSV |
| 7. Publish as a versioned snapshot | SeoulTransitPlatform | `glo30-20260907` |

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

## Publication

Step 6 produces a GeoPackage and a CSV. Those are analysis artefacts; they are
not what the API serves.

The results are published into SeoulTransitPlatform as a **versioned, immutable
snapshot** rather than written onto the stop master table. Three reasons:

- `bus_stop_location` is periodically reloaded from the source CSV. A derived
  column stored there is destroyed by the next reload, and nothing raises an
  error — the API keeps returning 200 while the values quietly empty out.
- Assigning stops to administrative dongs at query time multiplies rows: a stop
  on a shared boundary edge matches both polygons. The assignment is resolved
  once at publication and stored one row per stop.
- Without a version, there is no way to tell which DEM and which boundary
  vintage produced a given number.

The snapshot records its provenance — source DEM, slope method including the
scale factor, boundary base date, and per-category stop counts — and the API
echoes it on every response. Dataset `glo30-20260907` was published from the
`gdaldem slope -p -s 0.7934` output against the `20250630` boundary release.

Publication, schema and the serving API live in the SeoulTransitPlatform
repository under `pipelines/terrain/`, `database/terrain/` and
`services/api-server/.../terrain/`.

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
gdaldem slope dem_3857.tif slope.tif -p -s 0.7934    # cos(37.5°) (위도에 따른 거리 보정)
```

Both the corrected and uncorrected rasters are sampled, and the pipeline reports
both figures. The difference is not marginal: 4,536 stops against 3,279.

The correction uses a single latitude constant for the whole extent. Across the
one-degree band covered here the scale factor varies by roughly 2%, which is
small next to the 26% distortion being corrected, but it is an approximation
rather than a per-pixel correction.

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
All ten sit on genuine hillside roads. The steepest, at 60.2%, is on the
approach to Bukhansan, directly below a cliff face, with contour lines visibly
bunched around it. One that reads as flat commercial district on a basemap —
the Posco intersection — turned out to have substantial rising ground directly
behind it. No building artefacts were found among them.

Ten stops out of 11,480 is not a sample that settles the question, and the
concern remains structurally valid: a surface model can register a building
edge as terrain. But the check gives no evidence that it is happening at the
top of the distribution, which is where it would matter most.

Resolution, by contrast, does bias in one direction: at 30 m a short,
steep pitch between two flatter stretches is averaged away, which pushes the
figure down. On the evidence here, 39.5% is more likely an undercount than an
overcount — though that rests on ten checks, not a systematic validation. A
bare-earth DTM — Korea's national 5 m 수치표고모델 is the obvious candidate —
would settle both questions.

A second, separate limitation: at 30 m resolution, slope describes the terrain
gradient across the pixel containing a stop, not the gradient a passenger stands
on. A stop on level pavement beside a steep drop registers as steep. For a
screening indicator this is arguably the more useful reading — reaching the stop
still means crossing the slope — but it is not the same measurement, and it is
not what an accessibility standard specifies.

### Environment

Three separate GDAL/PROJ installations coexist on the development machine
(PostgreSQL/PostGIS, QGIS via OSGeo4W, and pip-installed rasterio). PostgreSQL
exports `PROJ_LIB` globally, pointing at a PROJ database older than the one
rasterio's bundled PROJ 9.x will accept, which surfaces as
`CRSError: The EPSG code is unknown` on any CRS lookup.

Each script clears the variable for its own process rather than unsetting it
system-wide, which would break PostGIS:

```python
os.environ.pop("PROJ_LIB", None)   # Before importing rasterio. (rasterio를 불러오기 전에 실행합니다.)
```

CLI tools need the same treatment per shell session (`$env:PROJ_LIB=""`).

Contour extraction uses `ContourSet.get_paths()`; `allsegs` was removed in
matplotlib 3.10. Vertices are mapped through pixel centres. The CI update
corrects a half-pixel offset in the original implementation; previously
generated contour files must be regenerated. Historical full-dataset counts
above have not been revalidated by these tests.

The CI workflow runs Ruff and ten tests on pushes and pull requests, including
actual reprojection and GeoPackage contouring of a committed synthetic DEM.
It checks nodata masks, valid zero elevations, pixel-centre coordinates and the
Mercator scale passed to the slope command; the GDAL slope subprocess is mocked,
and actual slope calculation, COG/tiles, PostGIS sampling and publication are
outside this CI suite. A successful hosted run and runner duration must be
confirmed in GitHub Actions after pushing this update.

---

## Running it

```bash
pip install -r requirements.txt
```

For local CI checks:

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check src/ tests/
python -m pytest -v
```

Python 3.14 is the CI target. `requirements.txt` pins tested direct dependencies;
`requirements-original.txt` retains the supplied development-machine freeze for
reference and is not the CI install input. SQLAlchemy and the PostgreSQL driver,
used by the database scripts, are now explicit dependencies. GDAL CLI tools are
not required for this test suite.

GDAL command-line tools (`gdalbuildvrt`, `gdaldem`, `gdal2tiles`) are not
installed by pip and come with QGIS via the OSGeo4W Shell.

```bash
# 1. Mosaic. (모자이크 생성)
gdalbuildvrt data/dem_raw.vrt data/Copernicus_DSM_COG_10_N37_00_E12*.tif

# 2. Reproject. (재투영)
python src/01_reproject.py

# 3. Cloud Optimized GeoTIFF. (클라우드 최적화 GeoTIFF 생성)
rio cogeo create data/dem_3857.tif data/dem_cog.tif --web-optimized
rio cogeo validate data/dem_cog.tif

# 4. Contours. (등고선 생성)
python src/02_contours.py

# 5. Terrain derivatives and tiles. (지형 파생 자료와 타일 생성)
python src/05_slope.py
gdaldem hillshade data/dem_3857.tif data/hillshade.tif
gdal2tiles -z 8-13 --xyz -x --processes 4 data/hillshade.tif tiles/

# 6. Join to PostGIS. (PostGIS 정류장과 결합)
export SEOUL_TRANSIT_DB="postgresql+psycopg2://user:pass@localhost:5432/Seoul_Transit"
python src/03_slope_stats.py
```

`src/05_slope.py` wraps the two slope commands in step 5; its filename does not
change pipeline order. It preserves the published rounded correction `0.7934`
and explicitly uses `1.0` for the uncorrected baseline. The legacy
`src/04_write_to_postgis.py` updates the stop master table and is not part of the
versioned publication path described here.

Step 7 (publication) runs from the SeoulTransitPlatform repository:

```bash
python pipelines/terrain/publish_terrain.py --csv <step 6 output> --dry-run \
    --dataset-id glo30-20260907 --source-id copernicus-glo30 \
    --slope-method "gdaldem slope -p -s 0.7934" --boundary-date 20250630 \
    --expected-stops 11480 --expected-at-least 4536
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
