"""
merge_dem_tiles_assam.py — merges the Assam DEM tiles downloaded so far.
"""

import glob
import rasterio
from rasterio.merge import merge

tile_files = glob.glob("data/raw/elevation_data_assam/**/*.tif", recursive=True)

print(f"Found {len(tile_files)} Assam DEM tiles:")
for f in tile_files:
    print(f"  {f}")

if len(tile_files) == 0:
    print("No tiles found -- check folder path/naming")
else:
    srcs = [rasterio.open(f) for f in tile_files]
    mosaic, out_transform = merge(srcs)

    out_meta = srcs[0].meta.copy()
    out_meta.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_transform,
    })

    out_path = "data/raw/elevation_data_assam/assam_dem_merged.tif"
    with rasterio.open(out_path, "w", **out_meta) as dest:
        dest.write(mosaic)

    print(f"\nSaved merged DEM: {out_path}")
    print(f"Merged shape: {mosaic.shape}")

    for s in srcs:
        s.close()