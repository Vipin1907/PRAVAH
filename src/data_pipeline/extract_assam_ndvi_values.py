"""
extract_assam_ndvi_values.py — reuses the SAME all-India NDVI rasters
already downloaded (no new download needed), just extracts values at
Assam's grid-cell coordinates instead of Uttarakhand's.
"""

import rasterio
import numpy as np
import pandas as pd
import glob

def get_value_at_point(raster_path, lat, lon):
    with rasterio.open(raster_path) as src:
        row, col = src.index(lon, lat)
        try:
            band = src.read(1)
            val = band[row, col]
            if src.nodata is not None and val == src.nodata:
                return np.nan
            return (float(val) - 100) / 100  # same DN-to-NDVI scale as before
        except IndexError:
            return np.nan


# same NDVI files as Uttarakhand -- these cover all of India already
ndvi_files = {
    "2019-01": glob.glob("data/raw/ndvi_data/**/ocm2_ndvi_01to15_Jan2019*.tif", recursive=True),
    "2020-01": glob.glob("data/raw/ndvi_data/ocm2_ndvi_jan01to152020_v02_01/*.tif"),
    "2020-10": glob.glob("data/raw/ndvi_data/ocm2_ndvi_oct16to312020_v02_01/*.tif"),
    "2021-10": glob.glob("data/raw/ndvi_data/ocm2_ndvi_oct01to152021_v02_01/*.tif"),
}

# load ASSAM rainfall data to get Assam's grid cells
df = pd.read_csv("data/processed/assam_rainfall_with_proxies.csv")
unique_cells = df[["grid_cell_id"]].drop_duplicates().copy()
unique_cells["lat"] = unique_cells["grid_cell_id"].apply(lambda x: float(x.split("_")[0]))
unique_cells["lon"] = unique_cells["grid_cell_id"].apply(lambda x: float(x.split("_")[1]))

results = []
for period, files in ndvi_files.items():
    if not files:
        print(f"No file found for {period}, skipping")
        continue
    raster_path = files[0]
    for _, row in unique_cells.iterrows():
        val = get_value_at_point(raster_path, row["lat"], row["lon"])
        results.append({
            "period": period,
            "grid_cell_id": row["grid_cell_id"],
            "ndvi_real": val,
        })

result_df = pd.DataFrame(results)
result_df.to_csv("data/processed/assam_ndvi_real_values.csv", index=False)
print(f"Saved: data/processed/assam_ndvi_real_values.csv")
print(result_df.head(20).to_string())
print(f"\nNon-null NDVI values: {result_df['ndvi_real'].notna().sum()} out of {len(result_df)}")