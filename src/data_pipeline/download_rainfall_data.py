"""
download_rainfall_data.py — IMD gridded rainfall pull
Run LOCALLY (needs internet access to IMD's servers).
"""

import imdlib as imd
import os

OUT_DIR = "data/raw/rainfall_data"
os.makedirs(OUT_DIR, exist_ok=True)

print("Downloading IMD gridded rainfall 2019-2025 ...")
data = imd.get_data('rain', 2019, 2025, fn_format='yearwise')
ds = data.get_xarray()

regions = {
    "uttarakhand": dict(lat=slice(28.5, 31.5), lon=slice(77.5, 81.5)),
    "assam":       dict(lat=slice(24.0, 28.0), lon=slice(89.5, 96.5)),
}

for name, bbox in regions.items():
    ds_clip = ds.sel(**bbox)
    out_nc = f"{OUT_DIR}/{name}_rain_2019_2025.nc"
    ds_clip.to_netcdf(out_nc)
    print(f"Saved: {out_nc}  shape={dict(ds_clip.dims)}")
    df = ds_clip['rain'].mean(dim=['lat', 'lon']).to_dataframe().reset_index()
    df.to_csv(f"{OUT_DIR}/{name}_daily_mean_rain.csv", index=False)

print("Done. Check for NaN/missing days before gap-filling next.")