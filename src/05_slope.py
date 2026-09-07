"""Generate corrected and baseline slope rasters."""

import math
import os
import subprocess

SEOUL_LATITUDE = 37.5


def mercator_scale(latitude=SEOUL_LATITUDE):
    """Return the rounded ground-distance scale."""
    if not math.isfinite(latitude) or abs(latitude) >= 90:
        raise ValueError("Latitude must be finite and strictly between -90 and 90")
    # Keep the published snapshot's four-decimal scale.
    return round(math.cos(math.radians(latitude)), 4)


def generate_slopes(source="data/dem_3857.tif", corrected="data/slope.tif",
                    baseline="data/slope_uncorrected.tif"):
    """Run GDAL with explicit scale for both outputs."""
    env = os.environ.copy()
    env.pop("PROJ_LIB", None)
    for destination, scale in ((corrected, mercator_scale()), (baseline, 1.0)):
        subprocess.run(
            ["gdaldem", "slope", str(source), str(destination), "-p", "-s", str(scale)],
            check=True, env=env,
        )


if __name__ == "__main__":
    generate_slopes()
