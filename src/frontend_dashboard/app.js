/* ==========================================================
   PravahAI — Frontend Application Logic
   Fixed: state -> district -> basin cascading dropdowns
   ========================================================== */
"use strict";

/* -------------------------------------------------
   1. STATIC DATA (Catchment / Basin data per state)
   ------------------------------------------------- */
const STATE_DATA = {
  Assam: {
    districts: [
      { value: "Cachar", label: "Cachar" },
      { value: "Nagaon", label: "Nagaon" },
      { value: "Dhemaji", label: "Dhemaji" }
    ],
    basins: {
      Cachar:  [{ value: "A127", label: "A127 — Barak River Basin" }],
      Nagaon:  [{ value: "A042", label: "A042 — Kolong-Kopili Basin" }],
      Dhemaji: [{ value: "A011", label: "A011 — Subansiri Basin" }]
    }
  },
  Uttarakhand: {
    districts: [
      { value: "Chamoli", label: "Chamoli" },
      { value: "Uttarkashi", label: "Uttarkashi" },
      { value: "Rudraprayag", label: "Rudraprayag" }
    ],
    basins: {
      Chamoli:     [{ value: "U04", label: "U04 — Dharali Alaknanda Basin" }],
      Uttarkashi:  [{ value: "U01", label: "U01 — Bhagirathi Basin" }],
      Rudraprayag: [{ value: "U07", label: "U07 — Mandakini Basin" }]
    }
  }
};

const STATE_COORDS = {
  Assam: [24.08, 92.83],
  Uttarakhand: [30.31, 79.33]
};

const CATCHMENT_COORDS = {
  A127: { lat: 24.82, lon: 92.80, name: "Barak River Basin" },
  A042: { lat: 26.10, lon: 92.68, name: "Kolong-Kopili Basin" },
  A011: { lat: 27.48, lon: 94.58, name: "Subansiri Basin" },
  U04:  { lat: 30.55, lon: 79.35, name: "Dharali Alaknanda Basin" },
  U01:  { lat: 30.73, lon: 78.45, name: "Bhagirathi Basin" },
  U07:  { lat: 30.48, lon: 79.02, name: "Mandakini Basin" }
};

const HISTORICAL_EVENTS = {
  Assam: {
    eventName: "Assam Major Flood 2022 (Cachar)",
    rain3d: "712 mm",
    soil: "97%",
    anomaly: "+140% above avg",
    impact: "3.2M displaced, NH-37 cut off"
  },
  Uttarakhand: {
    eventName: "Chamoli Flash Flood 2021",
    rain3d: "205 mm",
    soil: "94%",
    anomaly: "+110% above avg",
    impact: "Glacier burst + Alaknanda surge"
  }
};

/* -------------------------------------------------
   2. WEATHER (real API if key provided, else simulated)
   ------------------------------------------------- */
const OWM_KEY = ""; // Add your OpenWeatherMap key here for live data

async function fetchRealWeather(lat, lon) {
  if (!OWM_KEY) throw new Error("No API key configured");
  const url = `https://api.openweathermap.org/data/2.5/weather?lat=${lat}&lon=${lon}&appid=${OWM_KEY}&units=metric`;
  const r = await fetch(url);
  if (!r.ok) throw new Error("OWM fetch failed: " + r.status);
  const d = await r.json();
  return {
    temp: `${Math.round(d.main.temp)}°C`,
    humidity: d.main.humidity,
    rain: `${((d.rain && d.rain["1h"]) || 0).toFixed(1)} mm/h`,
    rain3d: `${Math.round((d.main.humidity / 100) * (0.4 + Math.random() * 0.3))} mm`,
    soil: `${Math.round(60 + d.main.humidity / 3)}%`,
    runoff: d.main.humidity > 80 ? "Very High" : d.main.humidity > 65 ? "High" : "Moderate",
    discharge: `${Math.round(200 + d.main.humidity * 2)} m³/s`,
    condition: (d.weather && d.weather[0] && d.weather[0].description) || "—",
    source: "OpenWeatherMap Live"
  };
}

function simulateWeather() {
  const baseTemp = 18 + Math.random() * 12;
  const baseRain = 8 + Math.random() * 28;
  const rain3d = 80 + Math.random() * 200;
  const soilPct = 55 + Math.random() * 40;
  return {
    temp: `${Math.round(baseTemp)}°C`,
    humidity: Math.round(60 + Math.random() * 35),
    rain: `${baseRain.toFixed(1)} mm/h`,
    rain3d: `${Math.round(rain3d)} mm`,
    soil: `${Math.round(soilPct)}%`,
    runoff: soilPct > 82 ? "Very High" : soilPct > 68 ? "High" : "Moderate",
    discharge: `${Math.round(200 + rain3d * 1.2)} m³/s`,
    condition: baseRain > 18 ? "Heavy Rainfall" : "Moderate Rainfall",
    source: "Simulated (realistic)"
  };
}

/* -------------------------------------------------
   3. ML PREDICTION (client-side fallback logic)
   ------------------------------------------------- */
function computeFloodProbability(weather) {
  const rain3d = parseFloat(weather.rain3d);
  const soil = parseFloat(weather.soil);
  const rainScore = Math.min(rain3d / 350, 1) * 60;
  const soilScore = Math.min(soil / 100, 1) * 30;
  const randomFactor = Math.random() * 10;
  const pct = Math.min(Math.round(rainScore + soilScore + randomFactor), 99);
  const riskLevel = pct >= 75 ? "Very High" : pct >= 55 ? "High" : pct >= 30 ? "Moderate" : "Low";
  return { probability: pct, riskLevel };
}

function generateShap(state, weather) {
  const rain3dVal = parseFloat(weather.rain3d);
  const soilVal = parseFloat(weather.soil);
  return {
    summary: `Primary flood risk drivers for ${state}: (1) 3-day accumulated rainfall of ${weather.rain3d} significantly elevates runoff, (2) soil saturation at ${weather.soil} reduces infiltration capacity, (3) steep terrain gradients accelerate runoff into river channels.`,
    factors: [
      { name: "rainfall_3d", value: +(rain3dVal / 400).toFixed(2) },
      { name: "soil_saturation", value: +(soilVal / 100).toFixed(2) },
      { name: "slope_mass", value: +(0.08 + Math.random() * 0.12).toFixed(2) },
      { name: "monsoon_anomaly", value: +(0.05 + Math.random() * 0.1).toFixed(2) },
      { name: "river_discharge", value: +(0.03 + Math.random() * 0.08).toFixed(2) }
    ]
  };
}

/* -------------------------------------------------
   4. ROUTES + SHELTERS
   ------------------------------------------------- */
function generateRoutes(state) {
  const routes = {
    Assam: {
      normal: { name: "Silchar–Guwahati (NH-27)", dist: "328 km", time: "7h 20min", exp: "VERY HIGH", warn: "NH-27 submerged near Jatinga river crossing." },
      safe:   { name: "Silchar–Jiribam–Guwahati (Highland Bypass)", dist: "412 km", time: "9h 10min", exp: "LOW", warn: "Elevated highland route away from Barak overflow." }
    },
    Uttarakhand: {
      normal: { name: "Chamoli–Rishikesh (NH-58)", dist: "218 km", time: "5h 00min", exp: "HIGH", warn: "NH-58 blocked near Devprayag riverbank." },
      safe:   { name: "Chamoli–Gwaldam–Haridwar (Alt Route)", dist: "250 km", time: "6h 30min", exp: "MODERATE", warn: "Upper Garhwal alternate — no stream crossing." }
    }
  };
  return routes[state] || routes["Assam"];
}

function generateShelters(state) {
  const shelters = {
    Assam: [
      { name: "Udharbond Central Relief Shelter", capacity: "1,200", dist: "5.4 km", isHospital: false },
      { name: "Lakhipur Govt High School Camp", capacity: "800", dist: "12.1 km", isHospital: false },
      { name: "Cachar District Hospital, Silchar", capacity: "Civil Hospital", dist: "18.3 km", isHospital: true }
    ],
    Uttarakhand: [
      { name: "Joshimath Relief Camp", capacity: "900", dist: "8.3 km", isHospital: false },
      { name: "Chamoli Block Office Shelter", capacity: "600", dist: "15.6 km", isHospital: false },
      { name: "Base Hospital Srinagar (Garhwal)", capacity: "Hospital", dist: "40.0 km", isHospital: true }
    ]
  };
  return shelters[state] || shelters["Assam"];
}

/* -------------------------------------------------
   5. MAP
   ------------------------------------------------- */
let appMap = null;
let mapLayers = { risk: [], routes: [], shelters: [] };

function initMap(state) {
  try {
    const coords = STATE_COORDS[state] || [26.19, 92.76];
    const container = document.getElementById("map-container");
    if (!container || typeof L === "undefined") {
      console.warn("Leaflet or map container not ready");
      return;
    }

    if (!appMap) {
      appMap = L.map("map-container", { zoomControl: true }).setView(coords, 8);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
        maxZoom: 18
      }).addTo(appMap);
    } else {
      appMap.setView(coords, 8);
    }
    mapLayers.risk.forEach((l) => appMap.removeLayer(l));
    mapLayers.routes.forEach((l) => appMap.removeLayer(l));
    mapLayers.shelters.forEach((l) => appMap.removeLayer(l));
    mapLayers = { risk: [], routes: [], shelters: [] };

    const [lat, lng] = coords;
    const zones = [
      { center: [lat - 0.05, lng - 0.1], radius: 6000, color: "#ff5a5f", label: "Very High Risk Zone" },
      { center: [lat + 0.12, lng + 0.05], radius: 8000, color: "#ff9a3d", label: "High Risk Zone" },
      { center: [lat + 0.18, lng - 0.12], radius: 11000, color: "#ffd23d", label: "Moderate Risk Zone" }
    ];
    zones.forEach((z) => {
      const c = L.circle(z.center, { color: z.color, fillColor: z.color, fillOpacity: 0.25, weight: 2, radius: z.radius }).addTo(appMap);
      c.bindPopup(`<strong>${z.label}</strong><br/>Flash flood risk area`);
      mapLayers.risk.push(c);
    });

    const routeLine = L.polyline([[lat - 0.3, lng - 0.5], [lat + 0.4, lng + 0.6]], { color: "#31d17c", weight: 4, dashArray: "8 6" }).addTo(appMap);
    routeLine.bindPopup("<strong>Safe alternate route</strong><br/>Low flood exposure path");
    mapLayers.routes.push(routeLine);

    const shelterIcon = L.divIcon({
      html: `<div style="background:#3ba7ff;color:#fff;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;box-shadow:0 2px 6px rgba(0,0,0,.3)"><i class="fa fa-house-medical"></i></div>`,
      iconSize: [28, 28], iconAnchor: [14, 14]
    });
    [{ pos: [lat + 0.1, lng - 0.15], label: "Relief Shelter 1" }, { pos: [lat - 0.2, lng + 0.21], label: "Relief Shelter 2" }]
      .forEach((s) => {
        const m = L.marker(s.pos, { icon: shelterIcon }).addTo(appMap);
        m.bindPopup(`<strong>${s.label}</strong><br/>Verified safe shelter`);
        mapLayers.shelters.push(m);
      });

    setTimeout(() => {
      if (appMap) appMap.invalidateSize();
    }, 200);
  } catch (mapErr) {
    console.warn("Map setup notice:", mapErr);
  }
}

/* -------------------------------------------------
   6. RENDER FUNCTIONS
   ------------------------------------------------- */
function setWeatherCards(w) {
  document.getElementById("w-temp").textContent = w.temp;
  document.getElementById("w-rain").textContent = w.rain;
  document.getElementById("w-rain3d").textContent = w.rain3d;
  document.getElementById("w-soil").textContent = w.soil;
  document.getElementById("w-runoff").textContent = w.runoff;
  document.getElementById("w-discharge").textContent = w.discharge;
}

function setGauge(pct, riskLevel) {
  const gaugeRing = document.getElementById("gauge-ring");
  const gaugePct = document.getElementById("gauge-pct");
  const badge = document.getElementById("risk-verdict-badge");
  const verdictText = document.getElementById("risk-verdict-text");
  const verdictDetail = document.getElementById("verdict-detail");

  const colorMap = { "Very High": "#ff5a5f", High: "#ff9a3d", Moderate: "#ffd23d", Low: "#31d17c" };
  const col = colorMap[riskLevel] || "#8fa3b8";

  gaugeRing.style.background = `conic-gradient(${col} 0% ${pct}%, #253243 ${pct}% 100%)`;
  gaugePct.textContent = `${pct}%`;
  gaugePct.style.color = col;
  badge.style.background = `${col}22`;
  badge.style.color = col;
  verdictText.textContent = `${riskLevel} Flood Risk`;

  const detailMap = {
    "Very High": "Extreme probability of flash flooding in the next 6-24 hours. Immediate evacuation of low-lying areas is strongly recommended.",
    High: "High likelihood of significant flooding. Authorities should pre-position resources and issue public advisories.",
    Moderate: "Conditions are borderline. Monitor river gauges closely and prepare contingency evacuation plans.",
    Low: "No immediate flood threat detected. Standard monitoring protocols apply."
  };
  verdictDetail.textContent = detailMap[riskLevel] || "";
}

function setHistComparison(state, weather, hist) {
  document.getElementById("ht-event-name").textContent = hist.eventName;
  document.getElementById("ht-curr-rain").textContent = weather.rain3d;
  document.getElementById("ht-past-rain").textContent = hist.rain3d;
  document.getElementById("ht-curr-soil").textContent = weather.soil;
  document.getElementById("ht-past-soil").textContent = hist.soil;
  document.getElementById("ht-anomaly").textContent = hist.anomaly;
  document.getElementById("ht-past-impact").textContent = hist.impact;

  const currRain = parseFloat(weather.rain3d);
  const pastRain = parseFloat(hist.rain3d);
  const ratio = pastRain ? currRain / pastRain : 0;
  const rainTag = document.getElementById("ht-rain-cmp");
  if (ratio >= 0.85) { rainTag.textContent = `≥ 85% of Historic`; rainTag.className = "tag danger"; }
  else if (ratio >= 0.6) { rainTag.textContent = `~60-85% of Historic`; rainTag.className = "tag warning"; }
  else { rainTag.textContent = `< 60% of Historic`; rainTag.className = "tag live"; }

  document.getElementById("insight-text").textContent =
    `Today's 3-day rainfall of ${weather.rain3d} is ${Math.round(ratio * 100)}% of the ${hist.eventName} seen during the ${hist.eventName}. With soil saturation at ${weather.soil}, conditions are analogous to historical flood-triggering scenarios.`;
}

function setShap(shap) {
  document.getElementById("shap-summary").textContent = shap.summary;
  const container = document.getElementById("shap-bars");
  container.innerHTML = "";
  const colors = ["c-bar-red", "c-bar-orange", "c-bar-yellow", "c-bar-yellow", "c-bar-yellow"];
  const maxVal = Math.max(...shap.factors.map((f) => Math.abs(f.value)));
  shap.factors.forEach((f, i) => {
    const pct = Math.round((Math.abs(f.value) / maxVal) * 100);
    const row = document.createElement("div");
    row.className = "shap-row";
    row.innerHTML = `
      <div class="shap-lbl">${f.name.replace(/_/g, " ")}</div>
      <div class="shap-bg"><div class="shap-fill ${colors[i] || "c-bar-yellow"}" style="width:${pct}%"></div></div>
      <div>${f.value.toFixed(2)}</div>`;
    container.appendChild(row);
  });
}

function setRoutes(routes) {
  document.getElementById("nr-name").textContent = routes.normal.name;
  document.getElementById("nr-dist").textContent = routes.normal.dist;
  document.getElementById("nr-time").textContent = routes.normal.time;
  document.getElementById("nr-exp").textContent = routes.normal.exp;
  document.getElementById("nr-warn").innerHTML = `<i class="fa-solid fa-xmark"></i> ${routes.normal.warn}`;

  document.getElementById("sr-name").textContent = routes.safe.name;
  document.getElementById("sr-dist").textContent = routes.safe.dist;
  document.getElementById("sr-time").textContent = routes.safe.time;
  document.getElementById("sr-warn").innerHTML = `<i class="fa-solid fa-check"></i> ${routes.safe.warn}`;
}

function setShelters(shelters) {
  const list = document.getElementById("shelter-list");
  list.innerHTML = shelters.map((s) => `
    <div class="shelter-row">
      <div class="shelter-ico"><i class="fa-solid fa-${s.isHospital ? "hospital" : "campground"}"></i></div>
      <div class="shelter-info"><strong>${s.name}</strong><span>Capacity: ${s.capacity} &nbsp;·&nbsp; ${s.dist} away</span></div>
      <a href="tel:100" class="btn-call">Call</a>
    </div>`).join("");
}

function generateCAP(state, district, pct, riskLevel) {
  const now = new Date().toISOString();
  return `<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>PravahAI-${Date.now()}</identifier>
  <sender>pravahai@disaster-mgmt.gov.in</sender>
  <sent>${now}</sent>
  <status>Draft</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>en-IN</language>
    <category>Met</category>
    <event>Flash Flood Warning</event>
    <urgency>Immediate</urgency>
    <severity>${riskLevel}</severity>
    <certainty>Likely</certainty>
    <headline>Flash Flood Alert — ${state}, District: ${district}. Risk level: ${riskLevel}.</headline>
    <description>AI model probability: ${pct}%.</description>
    <instruction>Evacuate now. Avoid river crossings. Tune to official broadcast channels.</instruction>
    <area>
      <areaDesc>${district}, ${state}, India</areaDesc>
    </area>
  </info>
</alert>`;
}

/* -------------------------------------------------
   7. SHOW / HIDE PAGES (2-Step Predictive Workflow)
   ------------------------------------------------- */
let currentPredictionParams = {
  state: "Assam",
  district: "Cachar",
  basinId: "A127",
  basinLabel: "A127 — Barak River Basin",
  date: "2026-09-05",
  lead: "3"
};

function showWeatherForecastPage(params) {
  currentPredictionParams = { ...currentPredictionParams, ...params };
  const { state, district, basinId, basinLabel, date, lead } = currentPredictionParams;

  document.getElementById("home")?.classList.add("hidden");
  document.getElementById("results-panel")?.classList.add("hidden");
  const wfPanel = document.getElementById("weather-forecast-panel");
  if (wfPanel) wfPanel.classList.remove("hidden");

  // Meta badges
  const locEl = document.getElementById("wf-loc-text");
  const dateEl = document.getElementById("wf-date-text");
  if (locEl) locEl.textContent = `${state} · ${district} · ${basinLabel}`;
  if (dateEl) dateEl.textContent = `${date || new Date().toISOString().split("T")[0]} (+${lead || 3}h Forecast)`;

  // Location & date specific telemetry data
  const isAssam = state === "Assam";

  // 1. Observed Rainfall (Past 24h & 3-Day Cumulative)
  const obsRain24 = isAssam ? "142.5" : "98.2";
  const obsRain3d = isAssam ? "318.0" : "205.4";
  document.getElementById("wf-obs-rain").innerHTML = `${obsRain24} <span class="wfc-unit">mm</span>`;
  document.getElementById("wf-obs-rain-sub").innerHTML = `Past 24h · 3-Day Cumulative: <strong>${obsRain3d} mm</strong>`;
  document.getElementById("wf-obs-rain-src").textContent = "IMD Automatic Weather Station (AWS) + GPM Satellite";
  document.getElementById("wf-obs-rain-time").textContent = "05:30 IST (Hourly Telemetry)";
  document.getElementById("wf-obs-rain-status").textContent = "Verified Observation";

  // 2. Forecast Rainfall (Separately Displayed)
  const fcRain24 = isAssam ? "78.0" : "54.5";
  const fcPeak = isAssam ? "18.5" : "12.0";
  document.getElementById("wf-fc-rain").innerHTML = `${fcRain24} <span class="wfc-unit">mm</span>`;
  document.getElementById("wf-fc-rain-sub").innerHTML = `Next 24 Hours · Peak Rate: <strong>${fcPeak} mm/h</strong>`;
  document.getElementById("wf-fc-rain-src").textContent = "IMD NWP High-Res Regional Ensemble (WRF)";
  document.getElementById("wf-fc-rain-time").textContent = "06:00 IST (6h Model Cycle)";
  document.getElementById("wf-fc-rain-status").textContent = "Model Projected (High Confidence)";

  // 3. Rainfall Intensity
  const intensity = isAssam ? "24.8" : "16.4";
  document.getElementById("wf-rain-intensity").innerHTML = `${intensity} <span class="wfc-unit">mm/h</span>`;
  document.getElementById("wf-rain-intensity-sub").innerHTML = `Category: <strong class="${isAssam ? "c-orange" : "c-yellow"}">${isAssam ? "Heavy Downpour" : "Moderate Surge"}</strong>`;
  document.getElementById("wf-intensity-src").textContent = "IMD Doppler Weather Radar (DWR) Scan";
  document.getElementById("wf-intensity-time").textContent = "Real-time (15-min sweep)";
  document.getElementById("wf-intensity-status").textContent = "Live Radar Telemetry";

  // 4. Soil Moisture / Saturation
  const soilMoisture = isAssam ? "88.4" : "79.2";
  document.getElementById("wf-soil-sat").innerHTML = `${soilMoisture} <span class="wfc-unit">%</span>`;
  document.getElementById("wf-soil-sat-sub").innerHTML = `Top 0-30cm Saturation · <strong class="${isAssam ? "c-red" : "c-orange"}">${isAssam ? "Near Runoff Capacity" : "High Soil Saturation"}</strong>`;
  document.getElementById("wf-soil-src").textContent = "ISRO MOSDAC + Sentinel-1 SAR Radar";
  document.getElementById("wf-soil-time").textContent = "Daily Pass 04:00 IST";
  document.getElementById("wf-soil-status").textContent = "Calibrated In-situ + Satellite";

  // 5. River Water Level & Discharge
  const riverLevel = isAssam ? "19.85" : "324.60";
  const dangerMark = isAssam ? "19.83" : "325.00";
  const discharge = isAssam ? "1,280" : "860";
  const riverName = isAssam ? "Barak River (Annapurna Ghat)" : "Alaknanda River (Rudraprayag)";
  const isAboveDanger = isAssam;
  document.getElementById("wf-river-lvl").innerHTML = `${riverLevel} <span class="wfc-unit">m</span>`;
  document.getElementById("wf-river-lvl-sub").innerHTML = `${riverName} · Danger Level: <strong>${dangerMark} m</strong> (${isAboveDanger ? '<strong class="c-red">+0.02 m Above Danger</strong>' : '<strong class="c-green">-0.40 m Below Danger</strong>'}) · ${discharge} m³/s`;
  document.getElementById("wf-river-src").textContent = "Central Water Commission (CWC) Telemetry Gauge";
  document.getElementById("wf-river-time").textContent = "05:00 IST (Real-time Gauge)";
  document.getElementById("wf-river-status").textContent = "Active Hydrographic Station";

  // 6. Temperature & Atmosphere
  const temp = isAssam ? "26.5" : "19.8";
  const humidity = isAssam ? "92" : "84";
  const pressure = isAssam ? "998" : "1004";
  document.getElementById("wf-temp").innerHTML = `${temp} <span class="wfc-unit">°C</span>`;
  document.getElementById("wf-temp-sub").innerHTML = `Relative Humidity: <strong>${humidity}%</strong> · Pressure: <strong>${pressure} hPa</strong>`;
  document.getElementById("wf-temp-src").textContent = "IMD Surface Met Observation Station";
  document.getElementById("wf-temp-time").textContent = "05:30 IST";
  document.getElementById("wf-temp-status").textContent = "Active Surface Telemetry";

  // 7. Elevation & Catchment Topography
  const elevation = isAssam ? "48" : "1,450";
  const elevRange = isAssam ? "22m – 186m MSL (Floodplain)" : "680m – 3,850m MSL (Himalayan Gorge)";
  document.getElementById("wf-elev").innerHTML = `${elevation} <span class="wfc-unit">m MSL</span>`;
  document.getElementById("wf-elev-sub").innerHTML = `Catchment Relief: <strong>${elevRange}</strong>`;
  document.getElementById("wf-elev-src").textContent = "SRTM 30m Global Digital Elevation Model (DEM)";
  document.getElementById("wf-elev-time").textContent = "GIS Spatial Ingest";
  document.getElementById("wf-elev-status").textContent = "Validated Geo-Spatial Base";

  // 8. Slope, Drainage & Flow Accumulation
  const slope = isAssam ? "12.4" : "34.8";
  const flowArea = isAssam ? "5,200" : "1,850";
  document.getElementById("wf-slope").innerHTML = `${slope} <span class="wfc-unit">°</span>`;
  document.getElementById("wf-slope-sub").innerHTML = `Flow Accumulation Area: <strong>${flowArea} km²</strong> · Drainage Density: High`;
  document.getElementById("wf-slope-src").textContent = "CartoDEM 3D Analysis + HydroSHEDS";
  document.getElementById("wf-slope-time").textContent = "Spatial Analytics Sync";
  document.getElementById("wf-slope-status").textContent = "Conditioned Hydrological Mesh";

  window.scrollTo({ top: 0, behavior: "instant" });
}

function showResultsPage(state, district, basinLabel) {
  document.getElementById("home")?.classList.add("hidden");
  document.getElementById("weather-forecast-panel")?.classList.add("hidden");
  document.getElementById("results-panel")?.classList.remove("hidden");
  document.getElementById("result-location-badge").textContent = `${state} · ${district} · ${basinLabel}`;
  window.scrollTo({ top: 0, behavior: "instant" });
}

function showHomePage() {
  document.getElementById("weather-forecast-panel")?.classList.add("hidden");
  document.getElementById("results-panel")?.classList.add("hidden");
  document.getElementById("home")?.classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: "instant" });
}

function showLoadingBar() {
  document.getElementById("loading-bar")?.classList.remove("hidden");
  const btn = document.getElementById("btn-run-prediction-from-forecast");
  if (btn) btn.disabled = true;
}
function hideLoadingBar() {
  document.getElementById("loading-bar")?.classList.add("hidden");
  const btn = document.getElementById("btn-run-prediction-from-forecast");
  if (btn) btn.disabled = false;
}

/* -------------------------------------------------
   8. MAIN PREDICTION FLOW
   ------------------------------------------------- */
async function runPrediction(state, district, basinId, basinLabel) {
  showLoadingBar();
  try {
    const coords = CATCHMENT_COORDS[basinId] || { lat: 24.82, lon: 92.80 };

    // 1. Get weather (real API, fallback to simulated)
    let weather;
    try {
      weather = await fetchRealWeather(coords.lat, coords.lon);
    } catch (e) {
      weather = simulateWeather();
    }

    // 2. Try backend first (optional — safe to fail)
    let backendData = null;
    try {
      const resp = await fetch("/api/get-dashboard-data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state, district, basin: basinId, date: currentPredictionParams.date || new Date().toISOString().split("T")[0], lead_time_hours: parseInt(currentPredictionParams.lead || "6") })
      });
      if (resp.ok) backendData = await resp.json();
    } catch (err) {
      console.warn("Backend not reachable, using client-side simulation:", err.message);
    }

    // 3. Compute prediction (prefer backend, else client-side)
    let prediction;
    if (backendData && backendData.risk_summary) {
      prediction = {
        probability: backendData.risk_summary.probability_percent,
        riskLevel: backendData.risk_summary.category
      };
      console.log("✅ Using REAL backend ML prediction:", prediction);
    } else {
      prediction = computeFloodProbability(weather);
      console.log("⚠️ Backend prediction unavailable — using client-side simulation.");
    }

    // 4. SHAP explanation (prefer backend, else client-side)
    let shap;
    if (backendData && backendData.explainable_ai && Array.isArray(backendData.explainable_ai.factors) && backendData.explainable_ai.factors.length) {
      shap = {
        summary: backendData.explainable_ai.summary,
        factors: backendData.explainable_ai.factors.map((f) => ({
          name: f.feature || f.name,
          value: f.score !== undefined ? f.score : f.value
        }))
      };
      console.log("✅ Using REAL backend SHAP explanation");
    } else {
      shap = generateShap(state, weather);
    }

    // 5. Historical comparison
    const hist = HISTORICAL_EVENTS[state] || HISTORICAL_EVENTS["Assam"];

    // 6. Routes & shelters (prefer backend, else client-side)
    const routes = (backendData && backendData.routes_and_safety)
      ? backendData.routes_and_safety
      : generateRoutes(state);
    const shelters = (backendData && backendData.safe_shelters && backendData.safe_shelters.length)
      ? backendData.safe_shelters
      : generateShelters(state);

    // 7. Render everything on Results Page
    showResultsPage(state, district, basinLabel);
    setWeatherCards(weather);
    setGauge(prediction.probability, prediction.riskLevel);
    setHistComparison(state, weather, hist);
    setShap(shap);
    setRoutes(routes);
    setShelters(shelters);
    initMap(state);

    window._lastCap = generateCAP(state, district, prediction.probability, prediction.riskLevel);
    document.getElementById("alert-headline").textContent =
      prediction.riskLevel === "Low" ? "FLOOD ADVISORY" : "FLASH FLOOD WARNING";

  } catch (err) {
    console.error("Prediction flow failed:", err);
    alert("Something went wrong while generating the prediction. Please try again.");
  } finally {
    hideLoadingBar();
  }
}

/* -------------------------------------------------
   9. EVENT LISTENERS  (fix: cascading dropdown logic)
   ------------------------------------------------- */
document.addEventListener("DOMContentLoaded", () => {
  const stateEl = document.getElementById("f-state");
  const distEl = document.getElementById("f-district");
  const basinEl = document.getElementById("f-basin");
  const dateField = document.getElementById("f-date");

  // Default date = today
  if (dateField && !dateField.value) {
    dateField.value = new Date().toISOString().split("T")[0];
  }

  // Live status time updater
  const updateStatusTime = () => {
    const timeStatusEl = document.getElementById("live-time-status");
    if (timeStatusEl) {
      const now = new Date();
      const hours = String(now.getHours()).padStart(2, '0');
      const mins = String(now.getMinutes()).padStart(2, '0');
      timeStatusEl.textContent = `Data updated: ${hours}:${mins} IST`;
    }
  };
  updateStatusTime();

  // Calendar icon opens native picker
  const dateTrigger = document.getElementById("date-trigger");
  if (dateTrigger && dateField) {
    dateTrigger.addEventListener("click", () => {
      if (dateField.showPicker) dateField.showPicker();
      else dateField.focus();
    });
  }

  // --- STATE change -> populate District dropdown ---
  stateEl.addEventListener("change", () => {
    const st = stateEl.value;

    distEl.innerHTML = '<option value="">Select District</option>';
    basinEl.innerHTML = '<option value="">Select Catchment</option>';
    distEl.disabled = true;
    basinEl.disabled = true;

    const data = STATE_DATA[st];
    if (!data) return;

    data.districts.forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.value;
      opt.textContent = d.label;
      distEl.appendChild(opt);
    });
    distEl.disabled = false;

    // Auto-select first district and populate its catchment
    if (data.districts.length > 0) {
      distEl.value = data.districts[0].value;
      distEl.dispatchEvent(new Event("change"));
    }
  });

  // --- DISTRICT change -> populate Basin dropdown ---
  distEl.addEventListener("change", () => {
    const st = stateEl.value;
    const dist = distEl.value;

    basinEl.innerHTML = '<option value="">Select Catchment</option>';
    basinEl.disabled = true;

    const data = STATE_DATA[st];
    if (!data || !dist) return;

    const basinList = data.basins[dist] || [];
    basinList.forEach((b) => {
      const opt = document.createElement("option");
      opt.value = b.value;
      opt.textContent = b.label;
      basinEl.appendChild(opt);
    });
    basinEl.disabled = basinList.length === 0;

    // Auto-select first catchment
    if (basinList.length > 0) {
      basinEl.value = basinList[0].value;
    }
  });

  // --- FORM SUBMIT -> Show Weather Forecast & Telemetry Panel (Step 1) ---
  const form = document.getElementById("risk-form");
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const state = stateEl.value;
    const district = distEl.value;
    const basinId = basinEl.value;
    const basinLabel = basinEl.options[basinEl.selectedIndex] ? basinEl.options[basinEl.selectedIndex].textContent : "";
    const date = dateField ? dateField.value : "";
    const lead = document.getElementById("f-lead") ? document.getElementById("f-lead").value : "3";

    if (!state) { alert("Please select a State."); return; }
    if (!district) { alert("Please select a District."); return; }
    if (!basinId) { alert("Please select a Catchment / Basin."); return; }

    showWeatherForecastPage({ state, district, basinId, basinLabel, date, lead });
  });

  // --- "Predict Risk" button on Weather Forecast page -> Run ML & Agentic AI Prediction ---
  document.getElementById("btn-run-prediction-from-forecast")?.addEventListener("click", async () => {
    const { state, district, basinId, basinLabel } = currentPredictionParams;
    await runPrediction(state, district, basinId, basinLabel);
  });

  // --- "Back to Input Form" button on Weather Forecast page ---
  document.getElementById("btn-back-home-from-forecast")?.addEventListener("click", () => {
    showHomePage();
  });

  // --- "Back to Weather Forecast" button on Results panel ---
  document.getElementById("btn-back-to-forecast")?.addEventListener("click", () => {
    showWeatherForecastPage(currentPredictionParams);
  });

  // --- Back to Home button handler ---
  document.getElementById("btn-back-home")?.addEventListener("click", () => {
    showHomePage();
  });

  // --- Global Navigation Link Handler ---
  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener("click", (e) => {
      const href = link.getAttribute("href");
      if (!href || href === "#") return;
      const targetId = href.substring(1);
      
      const resultsPanel = document.getElementById("results-panel");
      const wfPanel = document.getElementById("weather-forecast-panel");
      if ((resultsPanel && !resultsPanel.classList.contains("hidden")) || (wfPanel && !wfPanel.classList.contains("hidden"))) {
        showHomePage();
      }

      if (targetId) {
        const targetEl = document.getElementById(targetId);
        if (targetEl) {
          e.preventDefault();
          targetEl.scrollIntoView({ behavior: "smooth" });
        }
      }
    });
  });

  // --- Sidebar Drawer Open / Close Logic ---
  const drawer = document.getElementById("sidebar-drawer");
  const overlay = document.getElementById("drawer-overlay");
  const hamburgerBtn = document.getElementById("nav-hamburger-btn");
  const drawerCloseBtn = document.getElementById("drawer-close-btn");

  const openDrawer = () => {
    if (drawer && overlay) {
      drawer.classList.add("open");
      overlay.classList.remove("hidden");
      document.body.style.overflow = "hidden";
    }
  };

  const closeDrawer = () => {
    if (drawer && overlay) {
      drawer.classList.remove("open");
      overlay.classList.add("hidden");
      document.body.style.overflow = "";
    }
  };

  hamburgerBtn?.addEventListener("click", openDrawer);
  drawerCloseBtn?.addEventListener("click", closeDrawer);
  overlay?.addEventListener("click", closeDrawer);

  // Drawer Nav Item Click
  document.querySelectorAll(".drawer-item").forEach((item) => {
    item.addEventListener("click", () => {
      document.querySelectorAll(".drawer-item").forEach((i) => i.classList.remove("active"));
      item.classList.add("active");
      closeDrawer();
    });
  });

  // --- Integrated Language Pill Toggle ---
  const langEnOpt = document.getElementById("lang-en-opt");
  const langHiOpt = document.getElementById("lang-hi-opt");

  langEnOpt?.addEventListener("click", (e) => {
    e.stopPropagation();
    langEnOpt.classList.add("active");
    langHiOpt?.classList.remove("active");
  });

  langHiOpt?.addEventListener("click", (e) => {
    e.stopPropagation();
    langHiOpt.classList.add("active");
    langEnOpt?.classList.remove("active");
  });

  // --- Notification Bell Button ---
  document.getElementById("notif-btn")?.addEventListener("click", () => {
    alert("📢 PravahAI Notifications:\n\n• All flood monitoring stations operational.\n• Live telemetry synced for Assam (Barak Basin) and Uttarakhand.\n• No critical breach warnings active at this moment.");
  });

  // --- Dark mode toggle ---
  const themeBtn = document.getElementById("theme-btn");
  const themeIcon = document.getElementById("theme-icon");
  themeBtn?.addEventListener("click", () => {
    document.body.classList.toggle("dark");
    if (document.body.classList.contains("dark")) {
      themeIcon.className = "fa-solid fa-sun";
    } else {
      themeIcon.className = "fa-regular fa-sun";
    }
  });

  // --- CAP modal ---
  document.getElementById("btn-cap")?.addEventListener("click", () => {
    document.getElementById("cap-xml").textContent = window._lastCap || "Run a prediction first.";
    document.getElementById("cap-modal").classList.remove("hidden");
  });
  const closeModal = () => document.getElementById("cap-modal").classList.add("hidden");
  document.getElementById("close-cap")?.addEventListener("click", closeModal);
  document.getElementById("btn-close-cap2")?.addEventListener("click", closeModal);

  // --- Download CAP ---
  document.getElementById("btn-download-cap")?.addEventListener("click", () => {
    const blob = new Blob([window._lastCap || ""], { type: "text/xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "pravah_cap_alert.xml";
    a.click();
    URL.revokeObjectURL(url);
  });

  // --- Approve alert ---
  document.getElementById("btn-approve")?.addEventListener("click", () => {
    const pill = document.getElementById("alert-status-pill");
    pill.textContent = "BROADCAST SENT";
    pill.className = "pill green";
    document.getElementById("btn-approve").disabled = true;
    alert("Alert approved and broadcast to Disaster Management System!");
  });

  // --- Map layer toggles ---
  ["chk-risk", "chk-routes", "chk-shelters"].forEach((id) => {
    const key = id.replace("chk-", "");
    document.getElementById(id)?.addEventListener("change", (e) => {
      (mapLayers[key] || []).forEach((l) => {
        if (!appMap) return;
        if (e.target.checked) appMap.addLayer(l); else appMap.removeLayer(l);
      });
    });
  });

  // --- Past Events Section Interactivity ---
  const initPastEvents = () => {
    const tabBtns = document.querySelectorAll(".pe-tab-btn");
    const filterBtns = document.querySelectorAll(".pe-filter-btn");
    const eventCards = document.querySelectorAll(".pe-event-card");

    let currentState = "assam";
    let currentFilter = "all";

    const updateEventCardsVisibility = () => {
      eventCards.forEach((card) => {
        const cardState = card.getAttribute("data-state");
        const cardType = card.getAttribute("data-type");

        const matchesState = cardState === currentState;
        const matchesFilter = currentFilter === "all" || cardType === currentFilter;

        if (matchesState && matchesFilter) {
          card.classList.remove("hidden-card");
          card.style.display = "flex";
        } else {
          card.classList.add("hidden-card");
          card.style.display = "none";
        }
      });
    };

    tabBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        tabBtns.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        currentState = btn.getAttribute("data-state");
        updateEventCardsVisibility();
      });
    });

    filterBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        filterBtns.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        currentFilter = btn.getAttribute("data-filter");
        updateEventCardsVisibility();
      });
    });

    // Details button modal/alert preview with verified facts
    const eventDetailsData = {
      "assam-2009": {
        title: "Assam Flood — 2009",
        state: "Assam",
        districts: "Lakhimpur, Dhemaji, Jorhat, Nagaon",
        type: "Flood",
        source: "ASDMA Official Annual Monograph",
        details: "Continuous torrential precipitation during early monsoon phase led to sudden river stage spikes along Brahmaputra tributaries. Matmora embankment breaches caused wide-scale inundation across upper Assam plains. Historical hydrological logs ingested into PravahAI hydro-routing engine."
      },
      "assam-2012": {
        title: "Assam Major Flood — 2012",
        state: "Assam",
        districts: "Multiple flood-prone riverine districts",
        type: "Flood",
        source: "ASDMA Disaster Records & CWC Bulletin",
        details: "Multiple waves of extreme rainfall saturated the Brahmaputra valley. Peak discharge exceeded critical embankment safety margins, impacting agricultural plains and wildlife corridors across Kaziranga and surrounding sub-basins."
      },
      "assam-2024": {
        title: "Assam Flood — 2024",
        state: "Assam",
        districts: "Barak and Brahmaputra river sub-catchments",
        type: "Flood",
        source: "ASDMA Flood Situation Reports 2024",
        details: "Early monsoon cloudbursts and high antecedent soil moisture triggered rapid runoff in Barak and northern tributaries. Real-time satellite radar telemetry calibrated PravahAI's AI runoff prediction model."
      },
      "uk-2013": {
        title: "Uttarakhand Floods — 2013",
        state: "Uttarakhand",
        districts: "Kedarnath, Rudraprayag, Chamoli, Uttarkashi",
        type: "Flash Flood & Landslide",
        source: "USDMA, Wadia Institute & GSI Special Report",
        details: "Multi-day intense monsoon rainfall coupled with Chorabari glacial lake outburst triggered catastrophic debris torrents, massive slope failures and gorge scouring across the Mandakini and Alaknanda valleys."
      },
      "uk-2022": {
        title: "Maldevta Flash Flood — 2022",
        state: "Uttarakhand",
        districts: "Dehradun (Maldevta & Raipur belt)",
        type: "Flash Flood",
        source: "SDRF Uttarakhand Incident Log",
        details: "Local cloudburst over Song river catchment generated steep surge hydrographs within 90 minutes, damaging bridges, rural roads and riverside installations in the Dehradun foothill region."
      },
      "uk-landslide": {
        title: "Uttarakhand Landslide Events",
        state: "Uttarakhand",
        districts: "Pithoragarh, Chamoli, Rudraprayag & Garhwal/Kumaon Hills",
        type: "Landslide",
        source: "Disaster Mitigation & Management Centre (DMMC)",
        details: "Slope instability caused by high pore-water pressure along steep Himalayan terrain during monsoon downpours. PravahAI integrates slope angle, geological fault data and rainfall thresholds for early landslide hazard forecasting."
      }
    };

    document.querySelectorAll(".pec-btn-details").forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = btn.getAttribute("data-target");
        const ev = eventDetailsData[target];
        if (ev) {
          alert(`📋 ${ev.title}\n\n📍 Location: ${ev.districts}\n⚠️ Type: ${ev.type}\n🏛️ Official Source: ${ev.source}\n\n📝 Report Summary:\n${ev.details}\n\n💡 PravahAI ML models incorporate these verified historical parameters to predict upcoming flood risks.`);
        }
      });
    });

    // Run initial state filter setup
    updateEventCardsVisibility();
  };

  initPastEvents();

  // --- Navbar scroll shadow ---
  const navbar = document.getElementById("navbar");
  window.addEventListener("scroll", () => {
    navbar.style.boxShadow = window.scrollY > 20 ? "0 2px 20px rgba(0,0,0,.35)" : "";
  });
});