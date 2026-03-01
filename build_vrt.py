"""
Build Virtual Raster (VRT) from NDVI GeoTIFF files.

This script creates a multi-band VRT file from individual NDVI rasters,
with each band labeled by its date. Useful for time series visualization
in QGIS or other GIS software.

Usage:
    python build_vrt.py

Configuration is read from config.yaml in the same directory.
"""

import sys
import yaml
from pathlib import Path
from osgeo import gdal  # type: ignore

# -- Load Configuration -------------------------------------------------------
CONFIG_PATH = Path(__file__).parent / "config.yaml"

if not CONFIG_PATH.exists():
    print(f"Error: Configuration file not found: {CONFIG_PATH}")
    print("Please copy 'config.example.yaml' to 'config.yaml' and edit it.")
    sys.exit(1)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# -- Settings -----------------------------------------------------------------
PROCESSED_DIR = Path(config["processed_dir"])
PROJECT_NAME = config.get("project_name", "NDVI")

if not PROCESSED_DIR.exists():
    print(f"Error: Processed directory not found: {PROCESSED_DIR}")
    print("Please run the data exploration notebook first to generate NDVI files.")
    sys.exit(1)

# -- Build VRT ----------------------------------------------------------------
ndvi_files_paths = sorted(PROCESSED_DIR.glob("NDVI_*.tif"))

if not ndvi_files_paths:
    print(f"Error: No NDVI_*.tif files found in {PROCESSED_DIR}")
    sys.exit(1)

# Create VRT filename based on date range
dates = [f.stem.replace("NDVI_", "") for f in ndvi_files_paths]
ndvi_files = [str(f) for f in ndvi_files_paths]
vrt_name = f"NDVI_{dates[0]}_to_{dates[-1]}.vrt"
vrt_path = PROCESSED_DIR / vrt_name

print(f"Creating VRT from {len(ndvi_files)} NDVI files...")
print(f"Date range: {dates[0]} to {dates[-1]}")

vrt = gdal.BuildVRT(str(vrt_path), ndvi_files, separate=True)

if vrt is None:
    print("Error: Failed to create VRT")
    sys.exit(1)

# Label each band with its date
for i, date_str in enumerate(dates):
    band = vrt.GetRasterBand(i + 1)
    band.SetDescription(date_str)

vrt.FlushCache()
vrt = None

print(f"\nSuccess! Created {len(ndvi_files)}-band VRT file:")
print(f"  {vrt_path}")
print("\nYou can now open this file in QGIS to visualize the NDVI time series.")
print("Tip: Use Layer Properties > Symbology > Multiband Color to assign")
print("     different dates to R/G/B channels for change visualization.")