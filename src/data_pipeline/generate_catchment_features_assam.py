"""
generate_catchment_features_assam.py — extracts real terrain features
from the merged Assam DEM.
"""

import whitebox
import os

wbt = whitebox.WhiteboxTools()
wbt.set_working_dir(os.path.abspath("data/raw/elevation_data_assam"))
wbt.verbose = True

DEM_IN = "assam_dem_merged.tif"

print("Step 1: filling depressions...")
wbt.fill_depressions(DEM_IN, "assam_dem_filled.tif")

print("Step 2: computing D8 flow direction...")
wbt.d8_pointer("assam_dem_filled.tif", "assam_flow_dir.tif")

print("Step 3: computing flow accumulation...")
wbt.d8_flow_accumulation("assam_dem_filled.tif", "assam_flow_accum.tif", out_type="cells")

print("Step 4: computing slope...")
wbt.slope(DEM_IN, "assam_slope.tif")

print("\nDone. Outputs in data/raw/elevation_data_assam/:")
print("  assam_slope.tif")
print("  assam_flow_accum.tif")