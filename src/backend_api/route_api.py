from flask import Flask, request, jsonify
import sys
import os

# Ayush ke routing_engine folder ko Python ke raste mein daalna
routing_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "routing_engine"))
if routing_path not in sys.path:
    sys.path.insert(0, routing_path)

# Ayush ka code import karna (Dhyan rahe ki routing_pipeline me ek main function ho)
try:
    import routing_pipeline
except ImportError as e:
    print(f"Error importing routing_pipeline: {e}")

app = Flask(__name__)

@app.route('/route', methods=['POST'])
def get_safe_route():
    try:
        input_data = request.json
        # Yahan hum Ayush ke function ko call karenge (Tumhe uska exact function name check karna padega, e.g., get_safest_route)
        # Abhi ke liye ek dummy response de rahe hain taaki connection test ho sake
        
        # TODO: Replace with actual call to Ayush's function, e.g.:
        # route_result = routing_pipeline.calculate_route(input_data['start_lat'], input_data['start_lon'])
        
        return jsonify({
            "status": "success",
            "safe_route": "Route via elevated highway",
            "estimated_time_mins": 45,
            "risk_level_on_route": "Low"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Ye python server port 5002 par chalega
    app.run(port=5002)