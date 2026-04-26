"""
backend/app/services/solution_service.py
=========================================
Sends simulation output to Gemma via OpenRouter and returns
structured recommendations + plain-English advisory.

Requires OPENROUTER_API_KEY in environment (or .env file).

Model: google/gemma-3-27b-it:free  (falls back to gemma-3-12b-it:free)
"""

import json
import os
import re
from typing import Dict, List, Union

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

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL     = "https://openrouter.ai/api/v1/chat/completions"

# Model preference order — all free tier
MODELS = [
    "google/gemma-3-27b-it:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-2-9b-it:free",
]


# ─────────────────────────────────────────────────────────────────
# PROMPT BUILDER
# ─────────────────────────────────────────────────────────────────

def _build_prompt(
    prediction:  PredictionResponse,
    simulation:  SimulationResponse,
    input_data:  Dict[str, Union[float, str]],
) -> str:
    """
    Build a tight, structured prompt for the LLM.
    Keeps token count low — Gemma free tier has context limits.
    All simulation field access uses getattr with defaults for safety.
    """
    # Input context — support both origin_port and port_name keys
    port   = input_data.get("origin_port") or input_data.get("port_name") or "unknown port"
    dest   = input_data.get("destination_port", "destination")
    cargo  = input_data.get("cargo_type",        "cargo")
    volume = input_data.get("cargo_volume_teu",  "unknown")
    season = input_data.get("season",            "unknown")

    # Safe simulation field access
    estimated_delay  = getattr(simulation, "estimated_delay_hours", 0.0)
    delay_p75        = getattr(simulation, "delay_p75",             0.0)
    delay_p90        = getattr(simulation, "delay_p90",             0.0)
    delay_p95        = getattr(simulation, "delay_p95",             0.0)
    prob_disruption  = getattr(simulation, "prob_disruption",       0.0)
    prob_missed_sla  = getattr(simulation, "prob_missed_sla",       0.0)
    congestion_level = getattr(simulation, "congestion_level",      "UNKNOWN")

    # Top cascade ports (max 4 for brevity)
    cascade_str  = "none"
    cascade_risk = getattr(simulation, "cascade_risk", None) or {}
    if cascade_risk:
        top = sorted(cascade_risk.items(), key=lambda x: -x[1])[:4]
        cascade_str = ", ".join(f"{pid} ({v*100:.0f}%)" for pid, v in top)

    # Top disruption type
    disruption_breakdown = getattr(simulation, "disruption_breakdown", None) or {}
    breakdown     = {k: v for k, v in disruption_breakdown.items() if k != "none"}
    top_disruption = max(breakdown, key=breakdown.get) if breakdown else "unknown"

    prompt = f"""You are a supply chain risk advisor for a logistics company.
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

Provide 3-4 recommendations. Examples of recommendation types:
reroute via alternative port, delay departure by N days, increase insurance coverage,
pre-position safety stock, switch to air freight for critical items, notify consignee.
Base cost and delay_factor on the simulation numbers above.
Return ONLY valid JSON. No explanation outside the JSON."""

    return prompt


# ─────────────────────────────────────────────────────────────────
# OPENROUTER CALL
# ─────────────────────────────────────────────────────────────────

def _call_openrouter(prompt: str) -> str:
    """
    Call OpenRouter with model fallback.
    Returns raw response text or raises on complete failure.
    """
    if not OPENROUTER_API_KEY:
        raise EnvironmentError(
            "OPENROUTER_API_KEY not set. Add it to .env or environment."
        )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://github.com/supply-chain-intelligence",
        "X-Title":       "Supply Chain Disruption Intelligence",
    }

    last_error = None
    for model in MODELS:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 800,
            "temperature": 0.3,   # low temp = more consistent JSON
        }
        try:
            logger.info("Calling OpenRouter model: %s", model)
            resp = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                logger.info("OpenRouter call succeeded with model: %s", model)
                return content
            else:
                logger.warning(
                    "Model %s returned HTTP %s: %s",
                    model, resp.status_code, resp.text[:200]
                )
                last_error = f"HTTP {resp.status_code}"
        except requests.Timeout:
            logger.warning("Model %s timed out.", model)
            last_error = "timeout"
        except Exception as e:
            logger.warning("Model %s error: %s", model, e)
            last_error = str(e)

    raise RuntimeError(f"All OpenRouter models failed. Last error: {last_error}")


# ─────────────────────────────────────────────────────────────────
# RESPONSE PARSER
# ─────────────────────────────────────────────────────────────────

def _parse_llm_response(raw: str) -> tuple[str, List[RecommendationItem]]:
    """
    Parse LLM JSON response into (advisory_text, [RecommendationItem]).
    Robust — handles markdown fences and minor formatting issues.
    """
    # Strip markdown fences if present
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()

    # Extract first JSON object
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        logger.error("No JSON found in LLM response: %s", raw[:300])
        return _fallback_advisory(), _fallback_recommendations()

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as e:
        logger.error("JSON parse failed: %s | raw: %s", e, cleaned[:300])
        return _fallback_advisory(), _fallback_recommendations()

    advisory = data.get("advisory", _fallback_advisory())
    raw_recs = data.get("recommendations", [])

    items = []
    for r in raw_recs:
        try:
            items.append(RecommendationItem(
                route        = str(r.get("route",        "Unknown action")),
                cost         = float(r.get("cost",        0.0)),
                delay_factor = float(r.get("delay_factor", 1.0)),
                reason       = str(r.get("reason",       "")),
            ))
        except Exception as e:
            logger.warning("Skipping malformed recommendation: %s | %s", r, e)

    if not items:
        items = _fallback_recommendations()

    return advisory, items


def _fallback_advisory() -> str:
    return (
        "Risk assessment complete. Elevated disruption probability detected. "
        "Review simulation metrics and consider contingency routing."
    )


def _fallback_recommendations() -> List[RecommendationItem]:
    return [
        RecommendationItem(
            route="Review alternate routing",
            cost=2000.0,
            delay_factor=0.7,
            reason="Fallback recommendation — LLM response unavailable.",
        )
    ]


# ─────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────

def get_recommendations(
    input_data: Dict[str, Union[float, str]],
) -> List[RecommendationItem]:
    """
    Called by /recommend endpoint.
    Standalone use — returns pointer to full pipeline.
    """
    logger.info("get_recommendations called (standalone).")
    return [
        RecommendationItem(
            route="Run full pipeline",
            cost=0.0,
            delay_factor=1.0,
            reason="Use /run_pipeline for full prediction + simulation + LLM recommendations.",
        )
    ]


def get_llm_recommendations(
    prediction:  PredictionResponse,
    simulation:  SimulationResponse,
    input_data:  Dict[str, Union[float, str]],
) -> tuple[str, List[RecommendationItem]]:
    """
    Called by pipeline_service after simulation.
    Returns (advisory_text, [RecommendationItem]).
    """
    logger.info("Generating LLM recommendations via OpenRouter.")

    prompt = _build_prompt(prediction, simulation, input_data)

    try:
        raw = _call_openrouter(prompt)
        advisory, items = _parse_llm_response(raw)
        logger.info("LLM recommendations parsed: %d items", len(items))
        return advisory, items
    except EnvironmentError as e:
        logger.error("OpenRouter not configured: %s", e)
        return (
            f"OpenRouter API key not configured. {_fallback_advisory()}",
            _fallback_recommendations(),
        )
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return _fallback_advisory(), _fallback_recommendations()