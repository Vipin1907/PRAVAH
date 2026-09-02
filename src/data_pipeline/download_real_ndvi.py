"""
download_real_ndvi.py — Real NDVI from Sentinel-2 satellite via Google Earth Engine.
"""

import ee
import pandas as pd

ee.Initialize()

regions = {
    "uttarakhand": ee.Geometry.Rectangle([77.5, 28.5, 81.5, 31.5]),
}

def get_ndvi_timeseries(geom, start_date, end_date):
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start_date, end_date)
        .filterBounds(geom)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
    )

    def add_ndvi(img):
        ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
        return img.addBands(ndvi)

    with_ndvi = collection.map(add_ndvi)

    months = pd.date_range(start_date, end_date, freq="MS")
    rows = []
    for m in months:
        m_end = (m + pd.DateOffset(months=1))
        monthly = with_ndvi.filterDate(str(m.date()), str(m_end.date())).select("NDVI").mean()
        mean_dict = monthly.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geom, scale=500, maxPixels=1e9
        )
        val = mean_dict.getInfo().get("NDVI")
        rows.append({"month": str(m.date()), "ndvi_mean": val})
        print(f"  {m.date()}: NDVI={val}")
    return pd.DataFrame(rows)

for region, geom in regions.items():
    print(f"Fetching real NDVI for {region} (this will take a few minutes)...")
    df = get_ndvi_timeseries(geom, "2019-01-01", "2025-12-31")
    out_path = f"data/processed/{region}_ndvi_real.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved: {out_path}\n")