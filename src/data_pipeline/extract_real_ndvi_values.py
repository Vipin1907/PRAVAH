"""
extract_real_ndvi_values.py — extracts real NDVI values from the
downloaded ISRO OCM2 rasters, for each grid cell in our rainfall data,
for the specific dates we have real coverage for (2019-2021).
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
            # OCM2 NDVI is often scaled (e.g. stored as int, actual range -1 to 1)
            # divide by 100 or 10000 depending on product scaling -- check the
            # readme.txt inside the extracted folder for the exact scale factor
            return float(val)
        except IndexError:
            return np.nan


# find all extracted NDVI tif files, keyed by approximate date
ndvi_files = {
    "2019-01": glob.glob("data/raw/ndvi_data/**/ocm2_ndvi_01to15_Jan2019*.tif", recursive=True),
    "2020-01": glob.glob("data/raw/ndvi_data/**/*Jan2020*.tif", recursive=True) or
               glob.glob("data/raw/ndvi_data/ocm2_ndvi_jan01to152020_v02_01/*.tif"),
    "2020-10": glob.glob("data/raw/ndvi_data/ocm2_ndvi_oct16to312020_v02_01/*.tif"),
    "2021-10": glob.glob("data/raw/ndvi_data/ocm2_ndvi_oct01to152021_v02_01/*.tif"),
}

print("Found files per period:")
for period, files in ndvi_files.items():
    print(f"  {period}: {files}")

# load rainfall data to get grid cells
df = pd.read_csv("data/processed/uttarakhand_rainfall_with_proxies.csv")
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
result_df.to_csv("data/processed/uttarakhand_ndvi_real_values.csv", index=False)
print(f"\nSaved: data/processed/uttarakhand_ndvi_real_values.csv")
print(result_df.head(20).to_string())
print(f"\nNon-null NDVI values: {result_df['ndvi_real'].notna().sum()} out of {len(result_df)}")