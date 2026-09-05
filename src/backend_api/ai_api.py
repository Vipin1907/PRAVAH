from langgraph.types import Command

from flask import Flask, request, jsonify
import sys
import os

pipeline_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data_pipeline"))
if pipeline_path not in sys.path:
    sys.path.insert(0, pipeline_path)

from flood_alert_agent import app as agent_app

app = Flask(__name__)

@app.route('/explain', methods=['POST'])
def get_ai_explanation():
    try:
        input_data = request.json
        
        thread_id = f"api-run-{input_data.get('catchment_id', 'unknown')}"
        config = {"configurable": {"thread_id": thread_id}}
    
        result = agent_app.invoke(input_data, config=config)
        
       
        if result.get("final_status") is None:
             result = agent_app.invoke(Command(resume="approve"), config=config)
             
     
        return jsonify({
            "status": "success",
            "alert_level": result.get("alert_level"),
            "explanation": result.get("explanation", "No explanation generated"),
            "probability": result.get("probability"),
            "confidence": result.get("confidence")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':

    app.run(port=5001)