"""
backend/app/schemas/response_schema.py
=======================================
Updated to carry full simulation output + LLM advisory.
All new fields are Optional with defaults so existing
/predict and /simulate endpoints stay backward compatible.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class PredictionResponse(BaseModel):
    congestion_probability:           float
    risk_level:                       str
    predicted_congestion_t_plus_2:    float
    predicted_berth_occupancy_t_plus_2: float


class SimulationResponse(BaseModel):
    # Core fields (backward compatible)
    estimated_delay_hours: float
    queue_size:            float
    congestion_level:      str

    # Extended simulation output from Monte Carlo model
    delay_p75:            float = 0.0
    delay_p90:            float = 0.0
    delay_p95:            float = 0.0
    prob_disruption:      float = 0.0
    prob_missed_sla:      float = 0.0
    disruption_breakdown: Dict[str, float] = Field(default_factory=dict)
    cascade_risk:         Dict[str, float] = Field(default_factory=dict)
    origin_port:          str = ""
    destination_port:     str = ""


class RecommendationItem(BaseModel):
    route:        str
    cost:         float
    delay_factor: float
    reason:       str = ""   # LLM-generated explanation


class PipelineResponse(BaseModel):
    prediction:     PredictionResponse
    simulation:     Optional[SimulationResponse] = None
    recommendation: Optional[List[RecommendationItem]] = None
    advisory:       Optional[str] = None   # LLM plain-English summary


class InputRequest(BaseModel):
    input_data: Dict[str, Any]
