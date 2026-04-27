from typing import List, Optional

from pydantic import BaseModel, Field


class PredictionResponse(BaseModel):
    congestion_probability: float
    risk_level: str
    predicted_congestion_t_plus_2: float
    predicted_berth_occupancy_t_plus_2: float


class RouteOption(BaseModel):
    rank:           int
    route:          str
    route_names:    str
    legs:           int
    distance_km:    float
    delay_p50:      float
    delay_p90:      float
    disruption_pct: float
    missed_sla_pct: float

class SimulationResponse(BaseModel):
    estimated_delay_hours: float
    queue_size:            float
    congestion_level:      str
    delay_p75:             float = 0.0
    delay_p90:             float = 0.0
    delay_p95:             float = 0.0
    prob_disruption:       float = 0.0
    prob_missed_sla:       float = 0.0
    disruption_breakdown:  dict[str, float] = Field(default_factory=dict)
    cascade_risk:          dict[str, float] = Field(default_factory=dict)
    origin_port:           str = ""
    destination_port:      str = ""
    recommended_route:     str = ""
    route_options:         List[RouteOption] = Field(default_factory=list)


class RecommendationItem(BaseModel):
    route: str
    cost: float
    delay_factor: float


class PipelineResponse(BaseModel):
    prediction: PredictionResponse
    simulation: Optional[SimulationResponse]
    recommendation: Optional[List[RecommendationItem]]
