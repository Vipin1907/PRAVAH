"""
merge_dem_tiles.py — joins the 6 downloaded DEM tiles (each inside its
own extracted folder) into one single merged raster for Uttarakhand.
"""

import glob
import rasterio
from rasterio.merge import merge

# each tile lives inside its own folder like data/raw/elevation_data/cdnh44g_v3r1/cdnh44g.tif
tile_files = glob.glob("data/raw/elevation_data/cdnh44*_v3r1/*.tif")

print(f"Found {len(tile_files)} DEM tiles:")
for f in tile_files:
    print(f"  {f}")

if len(tile_files) == 0:
    print("No tiles found -- check the folder path/naming pattern")
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

    out_path = "data/raw/elevation_data/uttarakhand_dem_merged.tif"
    with rasterio.open(out_path, "w", **out_meta) as dest:
        dest.write(mosaic)

    print(f"\nSaved merged DEM: {out_path}")
    print(f"Merged shape: {mosaic.shape}")

    for s in srcs:
        s.close()