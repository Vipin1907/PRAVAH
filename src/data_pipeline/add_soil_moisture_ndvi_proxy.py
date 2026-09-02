import pandas as pd

for region in ["uttarakhand", "assam"]:
    path = f"data/processed/{region}_rainfall_clean.csv"
    df = pd.read_csv(path)

    df["soil_saturation_proxy"] = df.groupby("grid_cell_id")["rainfall_30d"].transform(
        lambda s: s / s.max() if s.max() > 0 else 0
    )

    ndvi_static_value = 0.65 if region == "uttarakhand" else 0.72
    df["ndvi"] = ndvi_static_value
    df["ndvi_source"] = "placeholder_static"

    out_path = f"data/processed/{region}_rainfall_with_proxies.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved: {out_path}, shape={df.shape}")
    print(df[["date", "grid_cell_id", "rainfall_mm", "soil_saturation_proxy", "ndvi"]].head(3).to_string())
    print()

print("soil_saturation_proxy: derived from rainfall_30d (Antecedent Precipitation Index method)")
print("ndvi: STATIC PLACEHOLDER -- flag this clearly to Vipin and in documentation")