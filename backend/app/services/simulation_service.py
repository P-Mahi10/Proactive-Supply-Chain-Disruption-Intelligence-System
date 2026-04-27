"""
backend/app/services/simulation_service.py  —  v2
===================================================
Uses compare_routes() when destination_port is provided,
falls back to single run() for backward compatibility.
"""

import os
import sys
import traceback
from typing import Dict, Union

from app.schemas.response_schema import PredictionResponse, SimulationResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)

_HERE    = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.abspath(os.path.join(_HERE, "../../.."))
_ROOT    = _BACKEND if os.path.exists(os.path.join(_BACKEND, "simulation_model.py")) \
           else os.path.abspath(os.path.join(_BACKEND, ".."))

if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from simulation_model import SimulationModel, RouteComparisonOutput, format_for_llm
    _SIM_AVAILABLE = True
    logger.info("simulation_model.py loaded from %s", _ROOT)
except ImportError as e:
    logger.warning("simulation_model.py not found: %s", e)
    _SIM_AVAILABLE = False

PORT_NAME_TO_ID: Dict[str, str] = {
    "jnpt":                      "port776",
    "nhava sheva":               "port776",
    "mumbai-jawaharlal nehru (nhava sheva)": "port776",
    "mundra":                    "port777",
    "chennai":                   "port235",
    "chennai (madras)":          "port235",
    "visakhapatnam":             "port1367",
    "vizag":                     "port1367",
    "kolkata":                   "port442",
    "kolkata (syama prasad mookerje port)": "port442",
    "haldia":                    "port442",
    "cochin":                    "port583",
    "cochin (kochi)":            "port583",
    "kochi":                     "port583",
    "pipavav":                   "port907",
    "shanghai":                  "port1188",
    "shanghai (pudong)":         "port1188",
    "singapore":                 "port1201",
    "ningbo":                    "port824",
    "shenzhen":                  "port1189",
    "yantian":                   "port1189",
    "busan":                     "port1065",
    "hong kong":                 "port474",
    "qingdao":                   "port1069",
    "tianjin":                   "port1297",
    "tianjin xin gang":          "port1297",
    "rotterdam":                 "port1114",
    "jebel ali":                 "port306",
    "dubai":                     "port306",
    "hamburg":                   "port446",
    "new york":                  "port815",
    "new york-new jersey":       "port815",
    "los angeles":               "port664",
    "los angeles-long beach":    "port664",
    "tanjung pelepas":           "port1269",
    "colombo":                   "port254",
    "port said":                 "port192",
    "antwerp":                   "port57",
    "felixstowe":                "port343",
    "yokohama":                  "port1417",
    "karachi":                   "port543",
}

CALIB_PATH = os.path.join(_ROOT, "calibration.json")
_model = None


def _get_model():
    global _model
    if not _SIM_AVAILABLE:
        return None
    if _model is None:
        if not os.path.exists(CALIB_PATH):
            logger.error("calibration.json not found at %s", CALIB_PATH)
            return None
        _model = SimulationModel()
        _model.load_calibration(CALIB_PATH)
        logger.info("SimulationModel loaded.")
    return _model


def _resolve(name: str) -> str:
    return PORT_NAME_TO_ID.get(name.strip().lower(), "port776")


def should_trigger(prediction: PredictionResponse, threshold: float) -> bool:
    return prediction.congestion_probability > threshold


def _comparison_to_response(
    comparison: "RouteComparisonOutput",
    origin_name: str,
    dest_name:   str,
) -> SimulationResponse:
    """Convert RouteComparisonOutput → SimulationResponse, using recommended route stats."""
    best = comparison.recommended

    congestion_level = (
        "HIGH"   if best.delay_p90 > 24
        else "MEDIUM" if best.delay_p50 > 8
        else "LOW"
    )

    # Build route_options list for the response
    route_options = [
        {
            "rank":           i + 1,
            "route":          " → ".join(best_r.route),
            "route_names":    " → ".join(
                __import__("simulation_model").PORTS.get(p, {}).get("name", p)
                for p in best_r.route
            ),
            "legs":           len(best_r.route) - 1,
            "distance_km":    best_r.total_distance_km,
            "delay_p50":      best_r.delay_p50,
            "delay_p90":      best_r.delay_p90,
            "disruption_pct": round(best_r.prob_any_disruption * 100, 1),
            "missed_sla_pct": round(best_r.prob_missed_sla * 100, 1),
        }
        for i, best_r in enumerate(comparison.routes)
    ]

    return SimulationResponse(
        estimated_delay_hours = best.delay_p50,
        delay_p75             = best.delay_p75,
        delay_p90             = best.delay_p90,
        delay_p95             = best.delay_p95,
        prob_disruption       = best.prob_any_disruption,
        prob_missed_sla       = best.prob_missed_sla,
        queue_size            = float(best.delay_mean),
        congestion_level      = congestion_level,
        disruption_breakdown  = best.disruption_breakdown,
        cascade_risk          = best.cascade_risk,
        origin_port           = origin_name,
        destination_port      = dest_name,
        recommended_route     = " → ".join(
            __import__("simulation_model").PORTS.get(p, {}).get("name", p)
            for p in best.route
        ),
        route_options         = route_options,
    )


def simulate(
    prediction: PredictionResponse,
    input_data: Dict[str, Union[float, str]],
) -> SimulationResponse:
    logger.info("Starting simulation.")

    origin_name = str(input_data.get("origin_port") or input_data.get("port_name") or "JNPT")
    dest_name   = str(input_data.get("destination_port", "Singapore"))
    cargo_type  = str(input_data.get("cargo_type",      "container")).lower()
    volume      = float(input_data.get("cargo_volume_teu", 300.0))
    season      = str(input_data.get("season",          "summer")).lower()
    n_runs      = int(input_data.get("sim_runs",         500))
    compare     = bool(input_data.get("compare_routes",  True))

    origin_id = _resolve(origin_name)
    dest_id   = _resolve(dest_name)

    if origin_id == dest_id:
        dest_id = "port1201"
        logger.warning("Same port resolved — defaulting dest to Singapore")

    risk_scores = {origin_id: float(prediction.congestion_probability)}
    model       = _get_model()

    if model is not None:
        try:
            if compare:
                logger.info("Running route comparison: %s → %s", origin_id, dest_id)
                comparison = model.compare_routes(
                    origin_port_id      = origin_id,
                    destination_port_id = dest_id,
                    cargo_type          = cargo_type,
                    cargo_volume_teu    = volume,
                    risk_scores         = risk_scores,
                    season              = season,
                    n_runs              = n_runs,
                )
                return _comparison_to_response(comparison, origin_name, dest_name)
            else:
                logger.info("Running single route simulation: %s → %s", origin_id, dest_id)
                result = model.run(
                    origin_port_id      = origin_id,
                    destination_port_id = dest_id,
                    cargo_type          = cargo_type,
                    cargo_volume_teu    = volume,
                    risk_scores         = risk_scores,
                    season              = season,
                    n_runs              = n_runs,
                )
                congestion_level = (
                    "HIGH"   if result.delay_p90 > 24
                    else "MEDIUM" if result.delay_p50 > 8
                    else "LOW"
                )
                return SimulationResponse(
                    estimated_delay_hours = result.delay_p50,
                    delay_p75             = result.delay_p75,
                    delay_p90             = result.delay_p90,
                    delay_p95             = result.delay_p95,
                    prob_disruption       = result.prob_any_disruption,
                    prob_missed_sla       = result.prob_missed_sla,
                    queue_size            = float(result.delay_mean),
                    congestion_level      = congestion_level,
                    disruption_breakdown  = result.disruption_breakdown,
                    cascade_risk          = result.cascade_risk,
                    origin_port           = origin_name,
                    destination_port      = dest_name,
                    recommended_route     = " → ".join(
                        __import__("simulation_model").PORTS.get(p, {}).get("name", p)
                        for p in result.route
                    ),
                    route_options         = [],
                )

        except Exception as e:
            logger.error("Simulation failed: %s\n%s", e, traceback.format_exc())

    # Fallback
    logger.warning("Using placeholder simulation.")
    rainfall       = float(input_data.get("rainfall_mm", 0.0))
    disruption_sev = float(input_data.get("weather_forecast_severity", 0.0))
    base_queue     = float(input_data.get("current_queue", 10.0))
    cap_reduction  = min(0.9, 0.1 + rainfall * 0.05 + disruption_sev * 0.3)
    queue_size     = base_queue * (1.0 + cap_reduction + prediction.congestion_probability)
    est_delay      = max(0.0, queue_size * 0.2 + cap_reduction * 5.0)
    congestion_level = (
        "HIGH"   if prediction.congestion_probability > 0.8
        else "MEDIUM" if prediction.congestion_probability > 0.5
        else "LOW"
    )
    return SimulationResponse(
        estimated_delay_hours = est_delay,
        delay_p75             = est_delay * 1.4,
        delay_p90             = est_delay * 1.8,
        delay_p95             = est_delay * 2.2,
        prob_disruption       = prediction.congestion_probability,
        prob_missed_sla       = prediction.congestion_probability * 0.6,
        queue_size            = queue_size,
        congestion_level      = congestion_level,
        disruption_breakdown  = {},
        cascade_risk          = {},
        origin_port           = origin_name,
        destination_port      = dest_name,
        recommended_route     = "",
        route_options         = [],
    )