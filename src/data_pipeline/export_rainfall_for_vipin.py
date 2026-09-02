import xarray as xr
import pandas as pd

for region in ["uttarakhand", "assam"]:
    ds = xr.open_dataset(f"data/raw/rainfall_data/{region}_rain_2019_2025.nc")
    df = ds.to_dataframe().reset_index()
    df = df.rename(columns={"rain": "rainfall_mm", "time": "date"})
    df = df.dropna(subset=["rainfall_mm"])
    df = df.dropna(subset=["rainfall_mm"])
    df = df[df["rainfall_mm"] >= 0]   # remove -999 nodata sentinel values
    print(f"{region}: rows after removing -999 nodata: {len(df)}")

    df = df.sort_values(["lat", "lon", "date"])
    df["grid_cell_id"] = df["lat"].astype(str) + "_" + df["lon"].astype(str)
    for window, days in [("1d", 1), ("3d", 3), ("7d", 7), ("30d", 30)]:
        df[f"rainfall_{window}"] = (
            df.groupby("grid_cell_id")["rainfall_mm"]
            .transform(lambda s: s.rolling(days, min_periods=1).sum())
        )

    out_path = f"data/processed/{region}_rainfall_clean.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved: {out_path}, shape={df.shape}")
    print(df.head(3).to_string())
    print()

print("Resolution: DAILY (one row per grid cell per day).")
print("Usable now: antecedent moisture / 1d,3d,7d,30d accumulation features.")
print("Still needed: hourly rainfall source for 1h/3h/6h short-lead features.")