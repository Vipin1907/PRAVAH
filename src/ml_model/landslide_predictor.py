"""
landslide_predictor.py — Landslide Risk Prediction Model for TriNetra AI

Based on real geophysical research:
  - Shallow landslides in Himalayan terrain (Uttarakhand) triggered by:
    1. Steep slopes (>25°) + prolonged rainfall (10-day > 200mm)
    2. Soil saturation (>80%) weakens shear strength
    3. Sudden rainfall spike (1-day > 80mm) acts as final trigger
    4. Low vegetation (NDVI < 0.4) = no root anchoring
    5. Mid-altitude zones (500-3000m) most vulnerable

  - Flat terrain (Assam, slope <18°) → Landslide risk negligible
    (floods dominate in plains, not landslides)

References:
  - GSI (Geological Survey of India) Landslide Susceptibility Mapping
  - NDMA Guidelines on Landslide Hazard Management (2019)
  - Uttarakhand 2013 Kedarnath disaster analysis
  - Himachal Pradesh 2023 landslide patterns
"""

from typing import Dict, Tuple


class LandslidePredictor:
    """
    Physics-based Landslide Risk Classifier.
    
    Computes landslide probability from terrain + weather features using
    geophysically grounded weight functions (not random numbers).
    """

    def __init__(self):
        # Feature weights derived from GSI landslide susceptibility studies
        self.weights = {
            "slope":          0.30,   # Most critical — steep slope = high risk
            "rainfall_10d":   0.25,   # Antecedent moisture weakens soil
            "rainfall_1d":    0.15,   # Final trigger — sudden spike
            "soil_saturation": 0.15,  # Saturated soil = no shear strength
            "elevation":      0.08,   # Mid-altitude most vulnerable
            "ndvi":           0.07,   # Low vegetation = no root anchoring
        }
        self.fitted = True

    def predict_landslide_risk(self, features: Dict[str, float]) -> Tuple[float, float, str, Dict[str, float]]:
        """
        Predict landslide risk from terrain and weather features.
        
        Args:
            features: Dict with keys:
                - slope_degrees: Terrain slope in degrees
                - rainfall_1d: Last 24h rainfall in mm
                - rainfall_10d: Last 10-day cumulative rainfall in mm
                - soil_saturation: Soil saturation as fraction (0.0 - 1.0)
                - elevation_m: Mean elevation in meters
                - ndvi: Vegetation index (0.0 - 1.0)
        
        Returns:
            Tuple of (probability, confidence, status_label, feature_contributions)
        """
        slope = features.get("slope_degrees", 15.0)
        r1d = features.get("rainfall_1d", 0.0)
        r10d = features.get("rainfall_10d", 0.0)
        soil = features.get("soil_saturation", 0.5)
        elev = features.get("elevation_m", 100.0)
        ndvi = features.get("ndvi", 0.65)

        # ============================================================
        # 1. SLOPE FACTOR (Most important — landslides need steep slopes)
        # ============================================================
        # < 15° → Almost no landslide risk (flat terrain like Assam)
        # 15-25° → Low risk
        # 25-35° → Moderate to High risk
        # 35-45° → Very High risk (Uttarakhand Himalayan gorges)
        # > 45° → Rock faces, different failure mechanism
        if slope < 15.0:
            s_slope = slope / 60.0          # Very low contribution (max ~0.25)
        elif slope < 25.0:
            s_slope = 0.25 + (slope - 15.0) / 40.0  # Gradual increase
        elif slope < 35.0:
            s_slope = 0.50 + (slope - 25.0) / 20.0  # Steep increase
        else:
            s_slope = min(0.95, 0.70 + (slope - 35.0) / 33.0)  # Very high

        # ============================================================
        # 2. RAINFALL 10-DAY FACTOR (Antecedent moisture)
        # ============================================================
        # < 50mm → Dry, soil strong, no risk
        # 50-150mm → Some weakening
        # 150-250mm → Significant weakening (Uttarakhand threshold)
        # > 300mm → Critical soil failure zone
        if r10d < 50.0:
            s_rain10 = r10d / 500.0       # Minimal (max 0.1)
        elif r10d < 150.0:
            s_rain10 = 0.10 + (r10d - 50.0) / 250.0  # Gradual
        elif r10d < 300.0:
            s_rain10 = 0.50 + (r10d - 150.0) / 300.0  # Steep
        else:
            s_rain10 = min(1.0, 0.80 + (r10d - 300.0) / 500.0)

        # ============================================================
        # 3. RAINFALL 1-DAY FACTOR (Trigger event)
        # ============================================================
        # < 20mm → No trigger
        # 20-50mm → Mild trigger
        # 50-100mm → Strong trigger
        # > 100mm → Cloudburst — immediate landslide danger
        if r1d < 20.0:
            s_rain1 = r1d / 200.0
        elif r1d < 50.0:
            s_rain1 = 0.10 + (r1d - 20.0) / 75.0
        elif r1d < 100.0:
            s_rain1 = 0.50 + (r1d - 50.0) / 100.0
        else:
            s_rain1 = min(1.0, 0.85 + (r1d - 100.0) / 200.0)

        # ============================================================
        # 4. SOIL SATURATION FACTOR
        # ============================================================
        # < 0.5 → Dry, stable
        # 0.5-0.75 → Moderate, some pore pressure
        # 0.75-0.90 → High pore pressure, reduced shear strength
        # > 0.90 → Critical — soil behaves like liquid
        if soil < 0.5:
            s_soil = soil * 0.4             # Low contribution
        elif soil < 0.75:
            s_soil = 0.20 + (soil - 0.5) * 1.6
        elif soil < 0.90:
            s_soil = 0.60 + (soil - 0.75) * 2.67
        else:
            s_soil = min(1.0, 0.85 + (soil - 0.90) * 1.5)

        # ============================================================
        # 5. ELEVATION FACTOR (Mid-altitude most vulnerable)
        # ============================================================
        # < 200m → Flat plains (Assam), no landslide terrain
        # 200-800m → Foothills, some risk
        # 800-2500m → Maximum vulnerability zone (Uttarakhand valleys)
        # 2500-4000m → High altitude, rocky, less soil
        # > 4000m → Snow/ice, different hazard
        if elev < 200:
            s_elev = elev / 2000.0          # Very low (plains)
        elif elev < 800:
            s_elev = 0.10 + (elev - 200) / 1500.0
        elif elev < 2500:
            s_elev = 0.50 + (elev - 800) / 3400.0  # Peak zone
        elif elev < 4000:
            s_elev = 0.60 - (elev - 2500) / 5000.0  # Decreasing
        else:
            s_elev = 0.30

        # ============================================================
        # 6. VEGETATION (NDVI) FACTOR
        # ============================================================
        # High NDVI (>0.6) → Dense vegetation, roots hold soil → LOW risk
        # Low NDVI (<0.3) → Barren/deforested → HIGH risk
        s_ndvi = max(0.0, min(1.0, (0.7 - ndvi) / 0.5))

        # ============================================================
        # COMPOUND INTERACTION: Slope × Rain synergy
        # ============================================================
        # Landslides happen when BOTH slope is steep AND rain is heavy
        # If slope < 15°, even heavy rain won't cause landslide (just flood)
        # This is the key differentiator from flood model
        if slope < 15.0:
            terrain_rain_synergy = 0.3     # Flat terrain — suppress landslide risk
        elif slope >= 30.0 and r10d >= 200.0:
            terrain_rain_synergy = 1.5     # Steep + wet = exponential danger
        elif slope >= 25.0 and r10d >= 150.0:
            terrain_rain_synergy = 1.3     # Moderately dangerous combo
        else:
            terrain_rain_synergy = 1.0     # Normal

        # Trigger boost: If 1-day rain > 80mm on already saturated steep slope
        trigger_boost = 0.0
        if r1d > 80.0 and soil > 0.75 and slope > 25.0:
            trigger_boost = 0.15  # Cloudburst on saturated steep slope = critical

        # ============================================================
        # FINAL PROBABILITY CALCULATION
        # ============================================================
        raw_score = (
            s_slope * self.weights["slope"] +
            s_rain10 * self.weights["rainfall_10d"] +
            s_rain1 * self.weights["rainfall_1d"] +
            s_soil * self.weights["soil_saturation"] +
            s_elev * self.weights["elevation"] +
            s_ndvi * self.weights["ndvi"]
        ) * terrain_rain_synergy + trigger_boost

        # Clamp to [0, 0.99]
        probability = float(min(max(round(raw_score, 3), 0.0), 0.99))

        # ============================================================
        # PHYSICAL SANITY CHECKS
        # ============================================================
        # 1. Flat terrain (< 15° slope) → Cap at 12% (landslide impossible on flat land)
        if slope < 15.0:
            probability = min(probability, 0.12)

        # 2. No rain at all → Cap at 8% (dry conditions, no trigger)
        if r10d < 20.0 and r1d < 5.0:
            probability = min(probability, 0.08)

        # 3. Low elevation plains (< 150m) → Cap at 10% (Assam floodplains)
        if elev < 150.0:
            probability = min(probability, 0.10)

        # ============================================================
        # STATUS LABEL
        # ============================================================
        prob_pct = int(round(probability * 100))
        if prob_pct >= 86:
            status = "Critical — Evacuate Immediately"
        elif prob_pct >= 61:
            status = "High Risk — Alert Issued"
        elif prob_pct >= 31:
            status = "Moderate Risk — Monitor Closely"
        else:
            status = "Stable — No Immediate Threat"

        # ============================================================
        # CONFIDENCE
        # ============================================================
        margin = abs(probability - 0.5) * 2.0
        confidence = float(round(0.70 + 0.25 * margin, 2))

        # ============================================================
        # FEATURE CONTRIBUTIONS (for Explainable AI)
        # ============================================================
        contributions = {
            "slope_angle": round(s_slope * self.weights["slope"] * terrain_rain_synergy, 3),
            "rainfall_10d": round(s_rain10 * self.weights["rainfall_10d"] * terrain_rain_synergy, 3),
            "rainfall_1d_trigger": round(s_rain1 * self.weights["rainfall_1d"] * terrain_rain_synergy, 3),
            "soil_saturation": round(s_soil * self.weights["soil_saturation"] * terrain_rain_synergy, 3),
            "elevation_zone": round(s_elev * self.weights["elevation"] * terrain_rain_synergy, 3),
            "vegetation_cover": round(s_ndvi * self.weights["ndvi"] * terrain_rain_synergy, 3),
        }

        return probability, confidence, status, contributions


# ============================================================
# Standalone test
# ============================================================
if __name__ == "__main__":
    model = LandslidePredictor()

    print("=" * 60)
    print("  TriNetra AI — Landslide Risk Predictor Test")
    print("=" * 60)

    # Test 1: Assam (flat plains) — should be LOW risk
    assam_features = {
        "slope_degrees": 12.4,
        "rainfall_1d": 45.0,
        "rainfall_10d": 300.0,
        "soil_saturation": 0.88,
        "elevation_m": 48,
        "ndvi": 0.58,
    }
    prob, conf, status, contribs = model.predict_landslide_risk(assam_features)
    print(f"\n🟢 ASSAM (Flat Plains, Slope 12.4°):")
    print(f"   Landslide Risk: {prob:.0%} — {status}")
    print(f"   Confidence: {conf:.0%}")
    print(f"   Contributions: {contribs}")

    # Test 2: Uttarakhand (steep Himalayas, heavy rain) — should be HIGH risk
    uk_heavy_rain = {
        "slope_degrees": 36.5,
        "rainfall_1d": 95.0,
        "rainfall_10d": 280.0,
        "soil_saturation": 0.82,
        "elevation_m": 1450,
        "ndvi": 0.42,
    }
    prob, conf, status, contribs = model.predict_landslide_risk(uk_heavy_rain)
    print(f"\n🔴 UTTARAKHAND (Steep Slope 36.5°, Heavy Rain):")
    print(f"   Landslide Risk: {prob:.0%} — {status}")
    print(f"   Confidence: {conf:.0%}")
    print(f"   Contributions: {contribs}")

    # Test 3: Uttarakhand (dry season) — should be LOW risk
    uk_dry = {
        "slope_degrees": 34.8,
        "rainfall_1d": 2.0,
        "rainfall_10d": 15.0,
        "soil_saturation": 0.35,
        "elevation_m": 1450,
        "ndvi": 0.55,
    }
    prob, conf, status, contribs = model.predict_landslide_risk(uk_dry)
    print(f"\n🟢 UTTARAKHAND (Dry Season, No Rain):")
    print(f"   Landslide Risk: {prob:.0%} — {status}")
    print(f"   Confidence: {conf:.0%}")
    print(f"   Contributions: {contribs}")

    # Test 4: Uttarakhand CRITICAL — Kedarnath 2013 type event
    uk_critical = {
        "slope_degrees": 38.0,
        "rainfall_1d": 120.0,
        "rainfall_10d": 400.0,
        "soil_saturation": 0.95,
        "elevation_m": 1200,
        "ndvi": 0.30,
    }
    prob, conf, status, contribs = model.predict_landslide_risk(uk_critical)
    print(f"\n🚨 UTTARAKHAND CRITICAL (Kedarnath 2013 Type):")
    print(f"   Landslide Risk: {prob:.0%} — {status}")
    print(f"   Confidence: {conf:.0%}")
    print(f"   Contributions: {contribs}")
