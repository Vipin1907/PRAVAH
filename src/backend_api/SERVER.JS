const axios = require('axios');
const cors = require('cors');
const express = require('express');
const app = express();


const PORT = 3000;

app.use(cors()); 
app.use(express.json());

app.use(express.json()); 
app.get('/', (req, res) => {
    res.send("API Gateway is running perfectly! Go to /predict or /alert");
});


app.get('/predict', (req, res) => {

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


app.get('/alert', (req, res) => {
    res.json({
        status: "success",
        alert_status: "Pending Human Review",
        message: "Alert draft generated. Waiting for Sweta's dashboard approval."
    });
});







app.post('/api/get-dashboard-data', async (req, res) => {
    try {
        const userLocationData = req.body; 

 
       const VIPIN_ML_URL = "http://localhost:5000/predict";
        const AYUSH_ROUTE_URL = "http://dummy-ayush-ip/route";
        const ATUL_AI_URL = "http://dummy-atul-ip/explain";

        console.log("Doston ki APIs call ho rahi hain...");

        const [mlResponse, routeResponse, aiResponse] = await Promise.all([
            axios.post(VIPIN_ML_URL, userLocationData).catch(err => ({ data: { error: "Vipin ka server down hai" } })),
            axios.post(AYUSH_ROUTE_URL, userLocationData).catch(err => ({ data: { error: "Ayush ka server down hai" } })),
            axios.post(ATUL_AI_URL, userLocationData).catch(err => ({ data: { error: "Atul ka server down hai" } }))
        ]);

        res.json({
            status: "success",
            risk_prediction: mlResponse.data,
            safe_routes: routeResponse.data,
            ai_alert: aiResponse.data
        });

    } catch (error) {
        console.error("Aggregation Error:", error.message);
        res.status(500).json({ error: "Backend API me kuch gadbad hai" });
    }
});

app.listen(PORT, () => {
    console.log(`Bhai, server badhiya chal raha hai: http://localhost:${PORT}`);
});

