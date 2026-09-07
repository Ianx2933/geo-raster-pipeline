\# geo-raster-pipeline



Raster processing pipeline over a Copernicus GLO-30 DEM covering Seoul.



Reprojects to Web Mercator with a block-streamed warp, publishes a validated

Cloud Optimized GeoTIFF, derives elevation contours to GeoPackage, and joins

slope statistics against transit stop geometries in PostGIS.



\*\*Status:\*\* in progress — reprojection and COG complete.



\## Pipeline



| Step | Script | Status |

|---|---|---|

| 1. Mosaic two GLO-30 tiles | `gdalbuildvrt` | done |

| 2. Reproject EPSG:4326 → 3857 | `src/01\_reproject.py` | done |

| 3. Cloud Optimized GeoTIFF | `rio cogeo` | done |

| 4. Contours → GeoPackage | `src/02\_contours.py` | pending |

| 5. Hillshade tiles | `gdal2tiles` | pending |

| 6. Slope stats → PostGIS stops | `src/03\_slope\_stats.py` | pending |

