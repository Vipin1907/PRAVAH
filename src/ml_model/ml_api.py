from flask import Flask, request, jsonify
import joblib
import json
import pandas as pd

app = Flask(__name__)


model = joblib.load("model_real_v2.pkl")
with open("model_v2_features.json") as f:
    feature_cols = json.load(f)


@app.route('/predict', methods=['POST'])
def predict_flood_risk():
    try:
        input_data = request.json
        
      
        X_row = pd.DataFrame([input_data])[feature_cols]
        proba = model.predict_proba(X_row)[0, 1]
        confidence = abs(proba - 0.5) * 2
        
        return jsonify({
            'probability': round(float(proba), 4),
            'confidence': round(float(confidence), 4),
            'lead_time_hrs': 3,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
  
    app.run(port=5000)