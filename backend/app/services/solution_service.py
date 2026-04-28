"""
backend/app/services/solution_service.py
=========================================
Handles two separate recommendation flows:

1. get_recommendations()     — called by /recommend endpoint
                               queries PostgreSQL for route options

2. get_llm_recommendations() — called by pipeline_service after simulation
                               calls Gemma via OpenRouter for advisory + recs
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Union

import psycopg2
import requests
from dotenv import load_dotenv

from app.schemas.response_schema import (
    PredictionResponse,
    RecommendationItem,
    SimulationResponse,
)
from app.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

backend_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(backend_dir / ".env")

DATABASE_URL       = os.environ.get("DATABASE_URL")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL     = "https://openrouter.ai/api/v1/chat/completions"

MODELS = [
    "google/gemma-3-27b-it:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-2-9b-it:free",
]


# ─────────────────────────────────────────────────────────────────
# /recommend endpoint — PostgreSQL route lookup
# ─────────────────────────────────────────────────────────────────

def get_recommendations(
    input_data: Dict[str, Union[float, str]],
) -> List[RecommendationItem]:
    logger.info("Fetching recommendations from PostgreSQL.")

    if not DATABASE_URL:
        logger.warning("DATABASE_URL not set — returning mock data.")
        return _get_mock_recommendations()

    try:
        conn   = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        origin = str(input_data.get("origin_port") or input_data.get("port_name") or "").strip()
        destination = str(input_data.get("destination_port") or "").strip()

        filtered_query = """
            SELECT r.origin, r.destination, tm.name AS route,
                   rm.cost_per_unit AS cost, rm.estimated_time_hours AS delay_factor
            FROM route_metrics rm
            JOIN route_options ro ON rm.route_option_id = ro.id
            JOIN routes r        ON ro.route_id         = r.id
            JOIN transport_modes tm ON ro.transport_mode_id = tm.id
            WHERE rm.condition_type = 'current'
        """
        params: list[str] = []
        if origin or destination:
            filtered_query += """
              AND (
                    (%s <> '' AND (LOWER(r.origin) = LOWER(%s) OR LOWER(r.destination) = LOWER(%s)))
                 OR (%s <> '' AND (LOWER(r.origin) = LOWER(%s) OR LOWER(r.destination) = LOWER(%s)))
              )
            """
            params.extend([origin, origin, origin, destination, destination, destination])

        filtered_query += """
            ORDER BY rm.cost_per_unit ASC
            LIMIT 4;
        """

        cursor.execute(filtered_query, params)
        rows = cursor.fetchall()

        if not rows and params:
            cursor.execute("""
                SELECT r.origin, r.destination, tm.name AS route,
                       rm.cost_per_unit AS cost, rm.estimated_time_hours AS delay_factor
                FROM route_metrics rm
                JOIN route_options ro ON rm.route_option_id = ro.id
                JOIN routes r        ON ro.route_id         = r.id
                JOIN transport_modes tm ON ro.transport_mode_id = tm.id
                WHERE rm.condition_type = 'current'
                ORDER BY rm.cost_per_unit ASC
                LIMIT 4;
            """)
            rows = cursor.fetchall()

        cursor.close()
        conn.close()

        items = []
        for row in rows:
            route_val = str(row[2]).title() if row[2] else "Unknown"
            if route_val == "Air":
                route_val = "Air Freight"
            items.append(RecommendationItem(
                route        = route_val,
                cost         = float(row[3]),
                delay_factor = float(row[4]),
            ))

        return items if items else _get_mock_recommendations()

    except Exception as e:
        logger.error("DB query failed: %s", e)
        return _get_mock_recommendations()


def _get_mock_recommendations() -> List[RecommendationItem]:
    return [
        RecommendationItem(route="Route A",      cost=100.0, delay_factor=0.8),
        RecommendationItem(route="Route B",      cost=120.0, delay_factor=0.6),
        RecommendationItem(route="Air Freight",  cost=300.0, delay_factor=0.4),
        RecommendationItem(route="Rail",         cost=150.0, delay_factor=0.7),
    ]


# ─────────────────────────────────────────────────────────────────
# /run_pipeline — LLM advisory via OpenRouter
# ─────────────────────────────────────────────────────────────────

def _build_prompt(
    prediction: PredictionResponse,
    simulation: SimulationResponse,
    input_data: Dict[str, Union[float, str]],
) -> str:
    port   = input_data.get("origin_port") or input_data.get("port_name") or "unknown port"
    dest   = input_data.get("destination_port", "destination")
    cargo  = input_data.get("cargo_type",       "cargo")
    volume = input_data.get("cargo_volume_teu", "unknown")
    season = input_data.get("season",           "unknown")

    estimated_delay  = getattr(simulation, "estimated_delay_hours", 0.0)
    delay_p75        = getattr(simulation, "delay_p75",             0.0)
    delay_p90        = getattr(simulation, "delay_p90",             0.0)
    delay_p95        = getattr(simulation, "delay_p95",             0.0)
    prob_disruption  = getattr(simulation, "prob_disruption",       0.0)
    prob_missed_sla  = getattr(simulation, "prob_missed_sla",       0.0)
    congestion_level = getattr(simulation, "congestion_level",      "UNKNOWN")

    cascade_str  = "none"
    cascade_risk = getattr(simulation, "cascade_risk", None) or {}
    if cascade_risk:
        top = sorted(cascade_risk.items(), key=lambda x: -x[1])[:4]
        cascade_str = ", ".join(f"{pid} ({v*100:.0f}%)" for pid, v in top)

    disruption_breakdown = getattr(simulation, "disruption_breakdown", None) or {}
    breakdown            = {k: v for k, v in disruption_breakdown.items() if k != "none"}
    top_disruption       = max(breakdown, key=breakdown.get) if breakdown else "unknown"

    return f"""You are a supply chain risk advisor for a logistics company.
Analyze the following disruption intelligence report and provide actionable recommendations.

=== SHIPMENT CONTEXT ===
Route        : {port} → {dest}
Cargo type   : {cargo}  |  Volume: {volume} TEU
Season       : {season}

=== PREDICTION MODEL OUTPUT ===
Congestion probability : {prediction.congestion_probability:.0%}
Risk level             : {prediction.risk_level}

=== SIMULATION OUTPUT (1000 Monte Carlo runs) ===
Median delay           : {estimated_delay:.1f} hrs
P75 delay              : {delay_p75:.1f} hrs
P90 delay              : {delay_p90:.1f} hrs
Worst 5%% delay        : {delay_p95:.1f} hrs
Disruption probability : {prob_disruption:.0%}
SLA breach probability : {prob_missed_sla:.0%}
Top disruption type    : {top_disruption}
Cascade risk ports     : {cascade_str}
Congestion level       : {congestion_level}

=== YOUR TASK ===
Return a JSON object with exactly this structure (no markdown, no extra text):
{{
  "advisory": "<2-3 sentence plain English summary of the risk situation>",
  "recommendations": [
    {{
      "route": "<action title>",
      "cost": <estimated cost impact as float, e.g. 5000.0>,
      "delay_factor": <delay multiplier 0.0-1.0, lower is better>,
      "reason": "<one sentence why>"
    }}
  ]
}}

Provide 3-4 recommendations. Examples: reroute via alternative port, delay departure,
increase insurance, pre-position safety stock, switch to air freight, notify consignee.
Return ONLY valid JSON. No explanation outside the JSON."""


def _call_openrouter(prompt: str) -> str:
    if not OPENROUTER_API_KEY:
        raise EnvironmentError("OPENROUTER_API_KEY not set.")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://github.com/supply-chain-intelligence",
        "X-Title":       "Supply Chain Disruption Intelligence",
    }

    last_error = None
    for model in MODELS:
        try:
            logger.info("Calling OpenRouter model: %s", model)
            resp = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json={
                    "model":       model,
                    "messages":    [{"role": "user", "content": prompt}],
                    "max_tokens":  800,
                    "temperature": 0.3,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                logger.info("OpenRouter succeeded with model: %s", model)
                return content
            logger.warning("Model %s HTTP %s: %s", model, resp.status_code, resp.text[:200])
            last_error = f"HTTP {resp.status_code}"
        except requests.Timeout:
            logger.warning("Model %s timed out.", model)
            last_error = "timeout"
        except Exception as e:
            logger.warning("Model %s error: %s", model, e)
            last_error = str(e)

    raise RuntimeError(f"All OpenRouter models failed. Last error: {last_error}")


def _parse_llm_response(raw: str) -> tuple[str, List[RecommendationItem]]:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    match   = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        logger.error("No JSON in LLM response: %s", raw[:300])
        return _fallback_advisory(), _fallback_llm_recommendations()
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as e:
        logger.error("JSON parse failed: %s", e)
        return _fallback_advisory(), _fallback_llm_recommendations()

    advisory = data.get("advisory", _fallback_advisory())
    items    = []
    for r in data.get("recommendations", []):
        try:
            items.append(RecommendationItem(
                route        = str(r.get("route",        "Unknown action")),
                cost         = float(r.get("cost",        0.0)),
                delay_factor = float(r.get("delay_factor", 1.0)),
                reason       = str(r.get("reason",       "")),
            ))
        except Exception as e:
            logger.warning("Skipping malformed rec: %s | %s", r, e)

    return advisory, items or _fallback_llm_recommendations()


def _fallback_advisory() -> str:
    return (
        "Risk assessment complete. Elevated disruption probability detected. "
        "Review simulation metrics and consider contingency routing."
    )


def _fallback_llm_recommendations() -> List[RecommendationItem]:
    return [
        RecommendationItem(
            route        = "Review alternate routing",
            cost         = 2000.0,
            delay_factor = 0.7,
            reason       = "Fallback — LLM response unavailable.",
        )
    ]


def get_llm_recommendations(
    prediction: PredictionResponse,
    simulation: SimulationResponse,
    input_data: Dict[str, Union[float, str]],
) -> tuple[str, List[RecommendationItem]]:
    logger.info("Generating LLM recommendations via OpenRouter.")
    prompt = _build_prompt(prediction, simulation, input_data)
    try:
        raw             = _call_openrouter(prompt)
        advisory, items = _parse_llm_response(raw)
        logger.info("LLM recommendations parsed: %d items", len(items))
        return advisory, items
    except EnvironmentError as e:
        logger.error("OpenRouter not configured: %s", e)
        return f"OpenRouter API key not configured. {_fallback_advisory()}", _fallback_llm_recommendations()
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return _fallback_advisory(), _fallback_llm_recommendations()