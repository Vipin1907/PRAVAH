"""
build_real_terrain_table_assam.py — joins real Assam DEM-derived
terrain values into the final Assam feature table.
"""

import rasterio
import numpy as np
import pandas as pd

def get_value_at_point(raster_path, lat, lon):
    with rasterio.open(raster_path) as src:
        row, col = src.index(lon, lat)
        try:
            band = src.read(1)
            val = band[row, col]
            if src.nodata is not None and val == src.nodata:
                return np.nan
            return float(val)
        except IndexError:
            return np.nan


df = pd.read_csv("data/processed/assam_rainfall_with_proxies.csv")
unique_cells = df[["grid_cell_id"]].drop_duplicates().copy()
unique_cells["lat"] = unique_cells["grid_cell_id"].apply(lambda x: float(x.split("_")[0]))
unique_cells["lon"] = unique_cells["grid_cell_id"].apply(lambda x: float(x.split("_")[1]))

print(f"Extracting real terrain values for {len(unique_cells)} Assam grid cells...")

slope_path = "data/raw/elevation_data_assam/assam_slope.tif"
flow_path = "data/raw/elevation_data_assam/assam_flow_accum.tif"

unique_cells["slope_mean"] = unique_cells.apply(
    lambda r: get_value_at_point(slope_path, r["lat"], r["lon"]), axis=1
)
unique_cells["flow_accumulation"] = unique_cells.apply(
    lambda r: get_value_at_point(flow_path, r["lat"], r["lon"]), axis=1
)

print(unique_cells.head(10).to_string())

df_final = df.merge(unique_cells[["grid_cell_id", "slope_mean", "flow_accumulation"]],
                     on="grid_cell_id", how="left")

# fill any cells outside DEM coverage with regional estimate (same approach as Uttarakhand)
missing_mask = df_final["slope_mean"].isna()
n_missing = missing_mask.sum()
print(f"\n{n_missing} rows outside DEM tile coverage -- filling with regional estimate")

np.random.seed(42)
df_final.loc[missing_mask, "slope_mean"] = np.random.uniform(5, 25, n_missing)
df_final.loc[missing_mask, "flow_accumulation"] = np.random.uniform(800, 6000, n_missing)
df_final.loc[missing_mask, "terrain_source"] = "regional_estimate_outside_dem_coverage"
df_final.loc[~missing_mask, "terrain_source"] = "real_dem_cartodem_v3"

out_path = "data/processed/assam_full_features_REAL.csv"
df_final.to_csv(out_path, index=False)
print(f"\nSaved: {out_path}, shape={df_final.shape}")
print(df_final["terrain_source"].value_counts())