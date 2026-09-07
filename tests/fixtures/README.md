# Synthetic DEM fixture

`tiny_dem.tif` is generated, not a Copernicus extract. No external data or network
access is required. It is 32 × 32 Float32 pixels in EPSG:4326 with an upper-left
corner of (127, 37.5) and a 0.001-degree pixel size. Each column rises 10 metres,
from 0 to 310 metres. Rows and columns 12 through 20 are nodata (-32768).
The output warp contract uses a different sentinel (-9999), allowing tests to
check that missing cells are translated correctly while sea-level zero remains
valid. This deliberately coarse artificial ramp is a test oracle, not a
30-metre Seoul terrain sample.

Regenerate with `python tests/fixtures/generate_dem.py` from the repository root.
The tiny GeoTIFF is committed; generated test outputs live in pytest temporary
directories. A separate temporary projected plane provides exact expected
contour coordinates for the half-pixel regression test.
