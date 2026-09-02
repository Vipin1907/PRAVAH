import random
import xml.etree.ElementTree as ET
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver


class FloodState(TypedDict):
    catchment_id: str
    probability: float
    confidence: float
    threshold: float
    min_conf: float
    lead_time_hrs: float
    top_drivers: list
    cap_draft: Optional[str]
    final_status: Optional[str]
    _real_data: Optional[bool]


def mock_forecast_call(catchment_id: str) -> dict:
    prob = round(random.uniform(0.3, 0.95), 2)
    conf = round(random.uniform(0.5, 0.9), 2)
    return {
        "probability": prob,
        "confidence": conf,
        "lead_time_hrs": round(random.uniform(2, 6), 1),
        "top_drivers": ["rainfall_6h", "soil_saturation_proxy", "slope_mean"],
    }


def forecast_agent_node(state: FloodState) -> FloodState:
    # if real data was already injected (from historical_replay.py),
    # skip the mock call and use what's already in state
    if state.get("_real_data", False):
        print(f"[forecast_agent] {state['catchment_id']}: "
              f"probability={state['probability']}, confidence={state['confidence']}, "
              f"lead_time={state['lead_time_hrs']}hrs (from REAL data)")
        return state

    result = mock_forecast_call(state["catchment_id"])
    state.update(result)
    print(f"[forecast_agent] {state['catchment_id']}: "
          f"probability={state['probability']}, confidence={state['confidence']}, "
          f"lead_time={state['lead_time_hrs']}hrs")
    return state


def build_cap_draft(state: FloodState) -> str:
    alert = ET.Element("alert")
    ET.SubElement(alert, "identifier").text = f"{state['catchment_id']}-flashflood"
    ET.SubElement(alert, "status").text = "Draft"
    ET.SubElement(alert, "msgType").text = "Alert"
    info = ET.SubElement(alert, "info")
    ET.SubElement(info, "event").text = "Flash Flood Warning"
    ET.SubElement(info, "urgency").text = "Immediate" if state["lead_time_hrs"] < 3 else "Expected"
    ET.SubElement(info, "severity").text = "Severe"
    ET.SubElement(info, "certainty").text = "Likely" if state["confidence"] > 0.7 else "Possible"
    ET.SubElement(info, "description").text = (
        f"Flash flood risk {state['probability']*100:.0f}% in next "
        f"{state['lead_time_hrs']}hrs. Top drivers: {', '.join(state['top_drivers'])}"
    )
    return ET.tostring(alert, encoding="unicode")


def alert_decision_node(state: FloodState):
    if state["probability"] >= state["threshold"] and state["confidence"] >= state["min_conf"]:
        draft = build_cap_draft(state)
        state["cap_draft"] = draft
        print(f"[alert_decision] THRESHOLD CROSSED -- routing to human approval")
        decision = interrupt({"action": "approve_red_alert", "draft": draft, "state": state})
        if decision == "approve":
            state["final_status"] = "APPROVED_SENT"
            return Command(goto="dissemination", update=state)
        else:
            state["final_status"] = "REJECTED"
            return Command(goto="monitoring", update=state)
    print(f"[alert_decision] below threshold, no alert needed")
    state["final_status"] = "NO_ALERT"
    return Command(goto=END, update=state)


def dissemination_node(state: FloodState) -> FloodState:
    print(f"[dissemination] Alert SENT for {state['catchment_id']}")
    print(f"  CAP draft: {state['cap_draft'][:100]}...")
    return state


graph = StateGraph(FloodState)
graph.add_node("forecast_agent", forecast_agent_node)
graph.add_node("alert_decision", alert_decision_node)
graph.add_node("dissemination", dissemination_node)
graph.set_entry_point("forecast_agent")
graph.add_edge("forecast_agent", "alert_decision")
graph.add_edge("dissemination", END)

checkpointer = InMemorySaver()
app = graph.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    config = {"configurable": {"thread_id": "demo-run-1"}}
    initial_state = {
        "catchment_id": "catch_007",
        "threshold": 0.6,
        "min_conf": 0.6,
    }
    print("=== Running agent ===")
    result = app.invoke(initial_state, config=config)
    print("\n=== Result (may be paused for approval) ===")
    print(result)
    if "__interrupt__" in result:
        print("\n=== Simulating human approval ===")
        final = app.invoke(Command(resume="approve"), config=config)
        print(final)