"""
generate_catchment_features.py — extracts real terrain features
(slope, flow_accumulation, drainage patterns) from the merged DEM.
"""

import whitebox
import os

wbt = whitebox.WhiteboxTools()
wbt.set_working_dir(os.path.abspath("data/raw/elevation_data"))
wbt.verbose = True

DEM_IN = "uttarakhand_dem_merged.tif"

print("Step 1: filling depressions (removes noise that breaks flow routing)...")
wbt.fill_depressions(DEM_IN, "uk_dem_filled.tif")

print("Step 2: computing D8 flow direction...")
wbt.d8_pointer("uk_dem_filled.tif", "uk_flow_dir.tif")

print("Step 3: computing flow accumulation...")
wbt.d8_flow_accumulation("uk_dem_filled.tif", "uk_flow_accum.tif", out_type="cells")

print("Step 4: computing slope...")
wbt.slope(DEM_IN, "uk_slope.tif")

print("Step 5: extracting stream network (threshold=500 cells)...")
wbt.extract_streams("uk_flow_accum.tif", "uk_streams.tif", threshold=500)

print("\nDone. Outputs in data/raw/elevation_data/:")
print("  uk_slope.tif        -- slope in degrees per pixel")
print("  uk_flow_accum.tif   -- flow accumulation per pixel")
print("  uk_streams.tif      -- extracted stream network")