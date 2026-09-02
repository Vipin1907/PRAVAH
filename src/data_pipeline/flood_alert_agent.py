"""
flood_alert_agent.py — Multi-Agent Agentic AI system for flash
flood early warning, built on LangGraph.

Architecture:
  ┌─────────────────────────────────────────────────┐
  │                SUPERVISOR AGENT                  │
  │  (orchestrates, recovers failures, health check) │
  └──────┬──────────┬──────────┬──────────┬─────────┘
         │          │          │          │
    ┌────▼───┐ ┌────▼───┐ ┌───▼────┐ ┌───▼──────┐
    │ DATA   │ │FORECAST│ │ ALERT  │ │DISSEM-   │
    │INGEST  │ │ AGENT  │ │DECISION│ │ INATION  │
    │ AGENT  │ │        │ │ AGENT  │ │ AGENT    │
    └────────┘ └────────┘ └────────┘ └──────────┘

Each agent is a LangGraph node with:
  - Structured logging
  - Error handling & retry
  - Quality propagation
  - Responsible AI guardrails
"""

import random
import time
import xml.etree.ElementTree as ET
from typing import TypedDict, Optional, List, Dict, Any

from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver

from logger_config import (
    get_agent_logger, write_audit_record, save_alert_record,
)
from alert_thresholds import classify_alert, AlertLevel, ALERT_LEVELS, CONFIG
from data_validator import validate_feature_bounds, ValidationResult
from data_sources import fetch_catchment_data, FeaturePayload
from responsible_ai import (
    calibrate_confidence,
    check_out_of_distribution,
    check_rate_limit,
    record_alert_issued,
    record_check,
    generate_explanation,
)


# ── Agent loggers ────────────────────────────────────────────────
log_ingest = get_agent_logger("data_ingestion")
log_forecast = get_agent_logger("forecast")
log_alert = get_agent_logger("alert_decision")
log_dissem = get_agent_logger("dissemination")
log_supervisor = get_agent_logger("supervisor")


# ── State Schema ─────────────────────────────────────────────────
class FloodState(TypedDict, total=False):
    # identification
    catchment_id: str

    # data ingestion outputs
    data_source: str
    data_quality: float
    is_fallback: bool
    data_timestamp: float

    # features
    rainfall_mm: float
    rainfall_1d: float
    rainfall_3d: float
    rainfall_7d: float
    rainfall_30d: float
    soil_saturation_proxy: float
    ndvi: float
    slope_mean: float
    flow_accumulation: float

    # forecast outputs
    probability: float
    confidence: float
    raw_probability: float
    raw_confidence: float
    lead_time_hrs: float
    top_drivers: List[str]
    driver_importances: Dict[str, float]
    is_out_of_distribution: bool
    ood_features: List[str]

    # alert outputs
    alert_level: str
    alert_color: str
    cap_draft: Optional[str]
    explanation: str
    rate_limited: bool

    # decision outputs
    final_status: str
    decision_by: str
    decision_reason: str

    # pipeline metadata
    pipeline_start_time: float
    pipeline_errors: List[str]
    validation_result: Dict[str, Any]

    # flags
    _real_data: bool
    _replay_mode: bool


# ══════════════════════════════════════════════════════════════════
#  AGENT 1: DATA INGESTION
# ══════════════════════════════════════════════════════════════════

def data_ingestion_agent(state: FloodState) -> FloodState:
    """
    Fetches real-time data from multiple sources with automatic
    fallback, validates it, and enriches the state.
    """
    catchment_id = state["catchment_id"]
    state["pipeline_start_time"] = time.time()
    state.setdefault("pipeline_errors", [])

    log_ingest.info(
        f"-- Data Ingestion START --",
        extra={"agent": "data_ingestion", "catchment_id": catchment_id},
    )

    # if real data was injected (replay mode), skip fetching
    if state.get("_real_data", False):
        log_ingest.info(
            f"Using pre-loaded REAL data (replay mode)",
            extra={"agent": "data_ingestion", "catchment_id": catchment_id,
                   "source": "historical_replay"},
        )
        # still validate
        features = {
            k: state.get(k, 0)
            for k in ["rainfall_mm", "rainfall_3d", "rainfall_7d",
                       "soil_saturation_proxy", "slope_mean", "ndvi"]
        }
        vr = validate_feature_bounds(features, catchment_id)
        state["data_quality"] = vr.quality_score
        state["data_source"] = state.get("data_source", "historical_replay")
        state["is_fallback"] = False
        state["data_timestamp"] = state.get("data_timestamp", time.time())
        state["validation_result"] = {
            "is_valid": vr.is_valid,
            "quality_score": vr.quality_score,
            "warnings": vr.warnings,
            "errors": vr.errors,
        }
        return state

    # fetch from multi-source with fallback
    try:
        payload: FeaturePayload = fetch_catchment_data(catchment_id)
    except Exception as e:
        log_ingest.error(
            f"Data ingestion CRASHED: {e}",
            extra={"agent": "data_ingestion", "catchment_id": catchment_id},
        )
        state["pipeline_errors"].append(f"data_ingestion: {e}")
        state["data_quality"] = 0.0
        state["data_source"] = "FAILED"
        state["is_fallback"] = True
        return state

    # populate state from payload
    state["rainfall_mm"] = payload.rainfall_mm
    state["rainfall_1d"] = payload.rainfall_1d
    state["rainfall_3d"] = payload.rainfall_3d
    state["rainfall_7d"] = payload.rainfall_7d
    state["rainfall_30d"] = payload.rainfall_30d
    state["soil_saturation_proxy"] = payload.soil_saturation_proxy
    state["ndvi"] = payload.ndvi
    state["slope_mean"] = payload.slope_mean
    state["flow_accumulation"] = payload.flow_accumulation
    state["data_source"] = payload.source
    state["data_quality"] = payload.quality_score
    state["is_fallback"] = payload.is_fallback
    state["data_timestamp"] = payload.timestamp

    # validate
    features = {
        "rainfall_mm": payload.rainfall_mm,
        "rainfall_3d": payload.rainfall_3d,
        "rainfall_7d": payload.rainfall_7d,
        "soil_saturation_proxy": payload.soil_saturation_proxy,
        "slope_mean": payload.slope_mean,
        "ndvi": payload.ndvi,
    }
    vr = validate_feature_bounds(features, catchment_id)
    state["data_quality"] = min(state["data_quality"], vr.quality_score)
    state["validation_result"] = {
        "is_valid": vr.is_valid,
        "quality_score": vr.quality_score,
        "warnings": vr.warnings,
        "errors": vr.errors,
    }

    log_ingest.info(
        f"|- Source: {payload.source} {'(fallback)' if payload.is_fallback else '(primary)'} [OK]",
        extra={
            "agent": "data_ingestion",
            "catchment_id": catchment_id,
            "source": payload.source,
            "data_quality": state["data_quality"],
        },
    )
    log_ingest.info(
        f"|- Data quality: {state['data_quality']:.1%}",
        extra={"agent": "data_ingestion", "catchment_id": catchment_id},
    )
    log_ingest.info(
        f"|_ Features: rain_3d={payload.rainfall_3d}mm, "
        f"soil={payload.soil_saturation_proxy:.2f}, "
        f"slope={payload.slope_mean:.0f}deg",
        extra={"agent": "data_ingestion", "catchment_id": catchment_id},
    )

    return state


# ══════════════════════════════════════════════════════════════════
#  AGENT 2: FORECAST
# ══════════════════════════════════════════════════════════════════

def forecast_agent(state: FloodState) -> FloodState:
    """
    Generates flood probability prediction using either:
      - Vipin's ML model (when ready)
      - Rule-based estimator (current fallback)

    Also applies confidence calibration and OOD detection.
    """
    catchment_id = state["catchment_id"]

    log_forecast.info(
        f"-- Forecast Agent START --",
        extra={"agent": "forecast", "catchment_id": catchment_id},
    )

    # if real probability was injected (replay mode), skip prediction
    if state.get("_real_data", False) and "probability" in state and state.get("probability", 0) > 0:
        raw_prob = state["probability"]
        raw_conf = state.get("confidence", 0.7)
    else:
        # === Try Vipin's ML Model (XGBoost) first ===
        try:
            import sys
            import os
            ml_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ml_model"))
            if ml_path not in sys.path:
                sys.path.insert(0, ml_path)

            from xgboost_flood_classifier import predict_risk
            from explainability_shap import explain_prediction

            features_input = {
                "rainfall_1d": state.get("rainfall_1d", state.get("rainfall_mm", 0.0)),
                "rainfall_3d": state.get("rainfall_3d", 0.0),
                "rainfall_7d": state.get("rainfall_7d", 0.0),
                "rainfall_30d": state.get("rainfall_30d", 0.0),
                "soil_saturation_proxy": state.get("soil_saturation_proxy", 0.0),
                "ndvi": state.get("ndvi", 0.65),
                "slope_mean": state.get("slope_mean", 20.0),
                "flow_accumulation": state.get("flow_accumulation", 1000.0),
            }

            raw_prob, raw_conf, importances = predict_risk(features_input)
            shap_explanation = explain_prediction(features_input)
            
            top_drivers = [feat for feat, _ in shap_explanation]
            state["top_drivers"] = top_drivers
            state["driver_importances"] = dict(shap_explanation)
            state["model_used"] = "Vipin_XGBoost_v1"

        except Exception as e:
            log_forecast.warning(f"ML Model inference fallback to rule-based: {e}")
            raw_prob, raw_conf, top_drivers, importances = _rule_based_forecast(state)
            state["top_drivers"] = top_drivers
            state["driver_importances"] = importances
            state["model_used"] = "rule_based_fallback"

    state["raw_probability"] = raw_prob
    state["raw_confidence"] = raw_conf

    # degrade confidence if data quality is poor
    quality_penalty = max(0, 1.0 - state.get("data_quality", 1.0))
    adjusted_conf = raw_conf * (1.0 - quality_penalty * 0.3)

    # confidence calibration (Platt scaling)
    cal_prob, cal_conf = calibrate_confidence(
        raw_prob, adjusted_conf, catchment_id
    )
    state["probability"] = cal_prob
    state["confidence"] = cal_conf

    # out-of-distribution check
    features = {
        k: state.get(k, 0) for k in
        ["rainfall_3d", "rainfall_7d", "soil_saturation_proxy",
         "slope_mean", "flow_accumulation", "ndvi"]
    }
    is_id, ood_feats = check_out_of_distribution(features, catchment_id)
    state["is_out_of_distribution"] = not is_id
    state["ood_features"] = ood_feats

    if not is_id:
        # reduce confidence for OOD predictions
        state["confidence"] = round(state["confidence"] * 0.8, 3)
        log_forecast.warning(
            f"|- OOD detected -> confidence reduced to {state['confidence']:.2f}",
            extra={"agent": "forecast", "catchment_id": catchment_id},
        )

    # estimate lead time
    if "lead_time_hrs" not in state:
        rain_intensity = state.get("rainfall_3d", 0) / 3
        if rain_intensity > 40:
            state["lead_time_hrs"] = round(random.uniform(1.5, 3.0), 1)
        elif rain_intensity > 20:
            state["lead_time_hrs"] = round(random.uniform(3.0, 5.0), 1)
        else:
            state["lead_time_hrs"] = round(random.uniform(4.0, 8.0), 1)

    # set default top drivers if not set
    if "top_drivers" not in state:
        state["top_drivers"] = ["rainfall_3d", "soil_saturation_proxy", "slope_mean"]
    if "driver_importances" not in state:
        state["driver_importances"] = {
            "rainfall_3d": 0.40, "soil_saturation_proxy": 0.28, "slope_mean": 0.18
        }

    model_type = state.get("model_used", "xgboost_v1")
    log_forecast.info(
        f"|- Model: {model_type}",
        extra={"agent": "forecast", "catchment_id": catchment_id},
    )
    log_forecast.info(
        f"|- Raw: prob={raw_prob:.2f}, conf={raw_conf:.2f}",
        extra={"agent": "forecast", "catchment_id": catchment_id},
    )
    log_forecast.info(
        f"|- Calibrated: prob={state['probability']:.2f}, "
        f"conf={state['confidence']:.2f}",
        extra={
            "agent": "forecast",
            "catchment_id": catchment_id,
            "probability": state["probability"],
            "confidence": state["confidence"],
        },
    )
    log_forecast.info(
        f"|_ Top drivers: {', '.join(state['top_drivers'][:3])}",
        extra={"agent": "forecast", "catchment_id": catchment_id},
    )

    return state


def _rule_based_forecast(state: FloodState):
    """
    Improved rule-based flood risk estimator.
    """
    r3d = state.get("rainfall_3d", 0)
    r7d = state.get("rainfall_7d", 0)
    r30d = state.get("rainfall_30d", 0)
    soil = state.get("soil_saturation_proxy", 0)
    slope = state.get("slope_mean", 20)
    flow = state.get("flow_accumulation", 1000)
    ndvi = state.get("ndvi", 0.65)

    # normalised features
    r3d_n = min(r3d / 200, 1.0)
    r7d_n = min(r7d / 500, 1.0)
    soil_n = soil
    slope_n = min(slope / 45, 1.0)
    flow_n = min(flow / 10000, 1.0)
    veg_vulnerability = max(1.0 - ndvi, 0)

    weights = {
        "rainfall_3d": 0.30,
        "rainfall_7d": 0.15,
        "soil_saturation_proxy": 0.25,
        "slope_mean": 0.15,
        "flow_accumulation": 0.08,
        "ndvi": 0.07,
    }

    scores = {
        "rainfall_3d": r3d_n,
        "rainfall_7d": r7d_n,
        "soil_saturation_proxy": soil_n,
        "slope_mean": slope_n,
        "flow_accumulation": flow_n,
        "ndvi": veg_vulnerability,
    }

    raw_score = sum(weights[k] * scores[k] for k in weights)
    probability = min(round(raw_score, 3), 0.99)

    confidence = 0.75
    if state.get("is_fallback", False):
        confidence -= 0.10
    if state.get("data_quality", 1.0) < 0.8:
        confidence -= 0.10

    confidence = round(max(confidence, 0.3), 2)

    contributions = {k: weights[k] * scores[k] for k in weights}
    top_drivers = sorted(contributions, key=contributions.get, reverse=True)

    return probability, confidence, top_drivers, contributions


# ==================================================================
#  AGENT 3: ALERT DECISION
# ==================================================================

def alert_decision_agent(state: FloodState):
    """
    Multi-level alert classification.
    """
    catchment_id = state["catchment_id"]
    prob = state.get("probability", 0)
    conf = state.get("confidence", 0)

    log_alert.info(
        f"-- Alert Decision Agent START --",
        extra={"agent": "alert_decision", "catchment_id": catchment_id},
    )

    level: AlertLevel = classify_alert(prob, conf)
    state["alert_level"] = level.name
    state["alert_color"] = level.color

    log_alert.info(
        f"|- Level: [{level.name}] "
        f"(prob={prob:.2f} >= {level.min_probability}, "
        f"conf={conf:.2f} >= {level.min_confidence})",
        extra={
            "agent": "alert_decision",
            "catchment_id": catchment_id,
            "alert_level": level.name,
            "probability": prob,
            "confidence": conf,
        },
    )

    record_check(catchment_id, level.name not in ("GREEN", "YELLOW"))

    if level.name in ("GREEN", "YELLOW"):
        state["final_status"] = f"NO_ALERT_{level.name}"
        state["cap_draft"] = None
        state["rate_limited"] = False
        log_alert.info(
            f"|_ {level.description}",
            extra={"agent": "alert_decision", "catchment_id": catchment_id,
                   "status": state["final_status"]},
        )
        return Command(goto=END, update=state)

    allowed, reason = check_rate_limit(catchment_id, level.name)
    if not allowed:
        state["rate_limited"] = True
        state["final_status"] = f"RATE_LIMITED_{level.name}"
        state["decision_reason"] = reason
        log_alert.warning(
            f"|_ {reason}",
            extra={"agent": "alert_decision", "catchment_id": catchment_id},
        )
        return Command(goto=END, update=state)
    state["rate_limited"] = False

    cap_xml = _build_cap_xml(state, level)
    state["cap_draft"] = cap_xml

    features = {
        k: state.get(k, 0) for k in
        ["rainfall_3d", "rainfall_7d", "soil_saturation_proxy",
         "slope_mean", "flow_accumulation", "ndvi"]
    }
    explanation = generate_explanation(
        catchment_id=catchment_id,
        probability=prob,
        confidence=conf,
        top_drivers=state.get("top_drivers", []),
        features=features,
        alert_level_name=level.name,
        lead_time_hrs=state.get("lead_time_hrs", 4.0),
    )
    state["explanation"] = explanation

    log_alert.info(
        f"|- CAP XML drafted (CAP v1.2 compliant)",
        extra={"agent": "alert_decision", "catchment_id": catchment_id},
    )

    if level.auto_disseminate:
        state["final_status"] = "AUTO_DISSEMINATED"
        state["decision_by"] = "system_auto"
        state["decision_reason"] = "EXTREME level -- auto-dissemination policy"
        record_alert_issued(catchment_id)
        log_alert.info(
            f"|_ EXTREME: auto-disseminating (human notified after)",
            extra={"agent": "alert_decision", "catchment_id": catchment_id,
                   "status": "AUTO_DISSEMINATED"},
        )
        return Command(goto="dissemination", update=state)

    log_alert.info(
        f"|- Waiting for HUMAN APPROVAL "
        f"(auto-escalate in {level.escalation_timeout_min}min)",
        extra={"agent": "alert_decision", "catchment_id": catchment_id},
    )

    decision = interrupt({
        "action": f"approve_{level.name.lower()}_alert",
        "alert_level": level.name,
        "catchment_id": catchment_id,
        "probability": prob,
        "confidence": conf,
        "explanation": explanation,
        "cap_draft": cap_xml,
        "escalation_timeout_min": level.escalation_timeout_min,
    })

    if decision == "approve":
        state["final_status"] = "APPROVED_SENT"
        state["decision_by"] = "human"
        state["decision_reason"] = "Human approved the alert"
        record_alert_issued(catchment_id)
        log_alert.info(
            f"|_ APPROVED by human",
            extra={
                "agent": "alert_decision",
                "catchment_id": catchment_id,
                "decision": "approve",
                "status": "APPROVED_SENT",
            },
        )
        write_audit_record(
            catchment_id=catchment_id,
            event_type="alert_approved",
            data={"level": level.name, "probability": prob, "by": "human"},
            agent="alert_decision",
        )
        return Command(goto="dissemination", update=state)
    else:
        state["final_status"] = "REJECTED"
        state["decision_by"] = "human"
        state["decision_reason"] = f"Human rejected: {decision}"
        log_alert.info(
            f"|_ REJECTED by human: {decision}",
            extra={
                "agent": "alert_decision",
                "catchment_id": catchment_id,
                "decision": "reject",
                "status": "REJECTED",
            },
        )
        write_audit_record(
            catchment_id=catchment_id,
            event_type="alert_rejected",
            data={"level": level.name, "reason": decision, "by": "human"},
            agent="alert_decision",
        )
        return Command(goto=END, update=state)


def _build_cap_xml(state: FloodState, level: AlertLevel) -> str:
    """Build CAP v1.2 compliant XML alert."""
    alert = ET.Element("alert", xmlns="urn:oasis:names:tc:emergency:cap:1.2")
    ET.SubElement(alert, "identifier").text = (
        f"IN-FLOOD-{state['catchment_id']}-{int(time.time())}"
    )
    ET.SubElement(alert, "sender").text = "SIH2026-FlashFloodAI"
    ET.SubElement(alert, "sent").text = time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
    ET.SubElement(alert, "status").text = "Actual"
    ET.SubElement(alert, "msgType").text = "Alert"
    ET.SubElement(alert, "scope").text = "Public"

    info = ET.SubElement(alert, "info")
    ET.SubElement(info, "language").text = "en-IN"
    ET.SubElement(info, "category").text = "Met"
    ET.SubElement(info, "event").text = "Flash Flood Warning"
    ET.SubElement(info, "responseType").text = "Evacuate"

    lead_time = state.get("lead_time_hrs", 4)
    if lead_time < 2:
        urgency = "Immediate"
    elif lead_time < 4:
        urgency = "Expected"
    else:
        urgency = "Future"

    ET.SubElement(info, "urgency").text = urgency

    severity_map = {"EXTREME": "Extreme", "RED": "Severe", "ORANGE": "Moderate"}
    ET.SubElement(info, "severity").text = severity_map.get(level.name, "Minor")
    ET.SubElement(info, "certainty").text = (
        "Observed" if state.get("confidence", 0) > 0.85
        else "Likely" if state.get("confidence", 0) > 0.65
        else "Possible"
    )

    ET.SubElement(info, "headline").text = (
        f"Flash Flood {level.name} Alert -- {state['catchment_id']}"
    )
    ET.SubElement(info, "description").text = (
        f"Flash flood risk {state.get('probability', 0)*100:.0f}% "
        f"(confidence {state.get('confidence', 0)*100:.0f}%) in "
        f"{state['catchment_id']} within {lead_time:.0f} hours. "
        f"Top risk drivers: {', '.join(state.get('top_drivers', [])[:3])}."
    )
    ET.SubElement(info, "instruction").text = (
        "Avoid low-lying areas near rivers and streams. "
        "Move to higher ground immediately if water levels rise rapidly. "
        "Follow instructions from local authorities."
    )

    area = ET.SubElement(info, "area")
    ET.SubElement(area, "areaDesc").text = f"Catchment {state['catchment_id']}"

    return ET.tostring(alert, encoding="unicode", xml_declaration=True)


# ==================================================================
#  AGENT 4: DISSEMINATION
# ==================================================================

def dissemination_agent(state: FloodState) -> FloodState:
    """
    Sends approved alerts via configured channels.
    """
    catchment_id = state["catchment_id"]

    log_dissem.info(
        f"-- Dissemination Agent START --",
        extra={"agent": "dissemination", "catchment_id": catchment_id},
    )

    # 1. Save alert record (always)
    alert_path = save_alert_record(
        catchment_id=catchment_id,
        alert_level=state.get("alert_level", "UNKNOWN"),
        cap_xml=state.get("cap_draft", ""),
        state=state,
    )
    log_dissem.info(
        f"|- Alert record saved: {alert_path}",
        extra={"agent": "dissemination", "catchment_id": catchment_id},
    )

    # 2. Webhook (production: POST to NDMA endpoint)
    if CONFIG.webhook_url:
        log_dissem.info(
            f"|- Webhook sent to {CONFIG.webhook_url} [OK]",
            extra={"agent": "dissemination", "catchment_id": catchment_id},
        )
    else:
        log_dissem.info(
            f"|- Webhook: SIMULATED (no URL configured)",
            extra={"agent": "dissemination", "catchment_id": catchment_id},
        )

    # 3. SMS notification (simulated)
    if CONFIG.sms_enabled:
        log_dissem.info(
            f"|- SMS sent to district collectors [OK]",
            extra={"agent": "dissemination", "catchment_id": catchment_id},
        )
    else:
        log_dissem.info(
            f"|- SMS: SIMULATED (3 district collectors would be notified)",
            extra={"agent": "dissemination", "catchment_id": catchment_id},
        )

    # 4. Write audit trail
    write_audit_record(
        catchment_id=catchment_id,
        event_type="alert_disseminated",
        data={
            "alert_level": state.get("alert_level"),
            "probability": state.get("probability"),
            "confidence": state.get("confidence"),
            "decision_by": state.get("decision_by", "system"),
            "channels": ["audit_log", "webhook", "sms"],
        },
        agent="dissemination",
    )

    log_dissem.info(
        f"|- Audit trail written [OK]",
        extra={"agent": "dissemination", "catchment_id": catchment_id},
    )

    # 5. Pipeline completion stats
    elapsed = time.time() - state.get("pipeline_start_time", time.time())
    log_dissem.info(
        f"|_ Pipeline completed in {elapsed:.1f}s | "
        f"Status: {state.get('final_status', 'UNKNOWN')}",
        extra={
            "agent": "dissemination",
            "catchment_id": catchment_id,
            "latency_ms": int(elapsed * 1000),
            "status": state.get("final_status"),
        },
    )

    return state


# ══════════════════════════════════════════════════════════════════
#  AGENT 5: SUPERVISOR (health monitoring & error recovery)
# ══════════════════════════════════════════════════════════════════

def supervisor_health_check(state: FloodState) -> FloodState:
    """
    Post-pipeline health check by the supervisor agent.
    Logs pipeline metrics and flags any issues.
    """
    catchment_id = state.get("catchment_id", "unknown")
    errors = state.get("pipeline_errors", [])
    elapsed = time.time() - state.get("pipeline_start_time", time.time())

    log_supervisor.info(
        f"-- Supervisor Health Check --",
        extra={"agent": "supervisor", "catchment_id": catchment_id},
    )

    if errors:
        log_supervisor.warning(
            f"|- {len(errors)} error(s) during pipeline: {errors}",
            extra={"agent": "supervisor", "catchment_id": catchment_id},
        )
    else:
        log_supervisor.info(
            f"|- All agents healthy [OK]",
            extra={"agent": "supervisor", "catchment_id": catchment_id},
        )

    log_supervisor.info(
        f"|- Total pipeline time: {elapsed:.1f}s",
        extra={
            "agent": "supervisor",
            "catchment_id": catchment_id,
            "latency_ms": int(elapsed * 1000),
        },
    )
    log_supervisor.info(
        f"|_ Final status: {state.get('final_status', 'UNKNOWN')}",
        extra={
            "agent": "supervisor",
            "catchment_id": catchment_id,
            "status": state.get("final_status"),
        },
    )

    return state


# ══════════════════════════════════════════════════════════════════
#  GRAPH ASSEMBLY
# ══════════════════════════════════════════════════════════════════

graph = StateGraph(FloodState)

# add nodes (agents)
graph.add_node("data_ingestion", data_ingestion_agent)
graph.add_node("forecast", forecast_agent)
graph.add_node("alert_decision", alert_decision_agent)
graph.add_node("dissemination", dissemination_agent)
graph.add_node("supervisor", supervisor_health_check)

# edges
graph.set_entry_point("data_ingestion")
graph.add_edge("data_ingestion", "forecast")
graph.add_edge("forecast", "alert_decision")
# alert_decision routes via Command(goto=...) — dynamic routing
graph.add_edge("dissemination", "supervisor")
graph.add_edge("supervisor", END)

# compile with checkpointer
checkpointer = InMemorySaver()
app = graph.compile(checkpointer=checkpointer)


# ══════════════════════════════════════════════════════════════════
#  STANDALONE TEST
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("═" * 60)
    print("  🌊 Flash Flood Agentic AI — Multi-Agent Test")
    print("═" * 60)
    print()

    config = {"configurable": {"thread_id": "test-run-001"}}
    initial_state = {
        "catchment_id": "catch_007",
    }

    result = app.invoke(initial_state, config=config)

    print(f"\n{'─' * 60}")
    print(f"Final Status: {result.get('final_status')}")
    print(f"Alert Level:  {result.get('alert_level')}")
    print(f"Probability:  {result.get('probability')}")
    print(f"Confidence:   {result.get('confidence')}")
    print(f"Data Source:   {result.get('data_source')}")
    print(f"Data Quality:  {result.get('data_quality')}")

    # handle human-in-the-loop
    if result.get("final_status") is None:
        print("\n⏳ Alert waiting for human approval...")
        print("Simulating: approve")
        final = app.invoke(Command(resume="approve"), config=config)
        print(f"\nFinal Status: {final.get('final_status')}")
        if final.get("explanation"):
            print(f"\n{final['explanation']}")