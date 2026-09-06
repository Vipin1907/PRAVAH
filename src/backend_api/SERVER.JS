/* ==========================================================
   PravahAI — Backend API Gateway (Express)
   ========================================================== */
const axios = require("axios");
const cors = require("cors");
const express = require("express");
const path = require("path");

// 1. Initialize app
const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// 2. Static frontend folder
//    NOTE: this MUST point to the actual frontend_dashboard folder.
const FRONTEND_DIR = path.join(__dirname, "../frontend_dashboard");
app.use("/static", express.static(FRONTEND_DIR));
app.use(express.static(FRONTEND_DIR));

// 3. Gateway status check route
app.get("/status", (req, res) => {
  res.send("API Gateway is running perfectly!");
});

// 4. Simple direct prediction endpoint (used for quick testing)
app.get("/predict", (req, res) => {
  res.json({
    status: "success",
    risk_level: "HIGH",
    probability: 78,
    hydrological_status: {
      runoff_potential: "High",
      soil_wetness: "High"
    }
  });
});

app.get("/alert", (req, res) => {
  res.json({
    status: "success",
    alert_status: "Pending Human Review",
    message: "Alert draft generated. Waiting for dashboard approval."
  });
});

/* -----------------------------------------------------------
   5. MAIN DASHBOARD AGGREGATOR
   Calls your ML/routing/AI microservices and merges the result.
   If any downstream service is unreachable, we DO NOT crash —
   we return a safe fallback so the frontend keeps working.
----------------------------------------------------------- */
const ML_PREDICT_URL = process.env.ML_PREDICT_URL || "http://localhost:5000/predict";
const ROUTE_API_URL = process.env.ROUTE_API_URL || "http://localhost:5002/route";
const EXPLAIN_API_URL = process.env.EXPLAIN_API_URL || "http://localhost:5001/explain";

app.post("/api/get-dashboard-data", async (req, res) => {
  const userLocationData = req.body;

  try {
    const [mlResponse, routeResponse, explainResponse] = await Promise.allSettled([
      axios.post(ML_PREDICT_URL, userLocationData, { timeout: 4000 }),
      axios.post(ROUTE_API_URL, userLocationData, { timeout: 4000 }),
      axios.post(EXPLAIN_API_URL, userLocationData, { timeout: 4000 })
    ]);

    const ml = mlResponse.status === "fulfilled" ? mlResponse.value.data : null;
    const routes = routeResponse.status === "fulfilled" ? routeResponse.value.data : null;
    const explain = explainResponse.status === "fulfilled" ? explainResponse.value.data : null;

    if (mlResponse.status === "rejected") console.warn("ML service unreachable:", mlResponse.reason.message);
    if (routeResponse.status === "rejected") console.warn("Routing service unreachable:", routeResponse.reason.message);
    if (explainResponse.status === "rejected") console.warn("Explainability service unreachable:", explainResponse.reason.message);

    res.json({
      status: "success",
      risk_summary: ml ? ml.risk_summary : null,
      routes_and_safety: routes ? routes.routes_and_safety : null,
      safe_shelters: routes ? routes.safe_shelters : null,
      explainable_ai: explain ? explain.explainable_ai : null,
      historical_comparison: ml ? ml.historical_comparison : null,
      note: "Any null field above means that microservice was unreachable — the frontend will use simulated data for it."
    });
  } catch (error) {
    console.error("Aggregation error:", error.message);
    res.status(500).json({ error: "Backend aggregation failed", details: error.message });
  }
});

app.listen(PORT, () => {
  console.log(`✅ PravahAI server running at http://localhost:${PORT}`);
  console.log(`   Frontend served from: ${FRONTEND_DIR}`);
});