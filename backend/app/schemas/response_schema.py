from typing import List, Optional

from pydantic import BaseModel


class PredictionResponse(BaseModel):
    congestion_probability: float
    risk_level: str
    predicted_congestion_t_plus_2: float
    predicted_berth_occupancy_t_plus_2: float


class SimulationResponse(BaseModel):
    estimated_delay_hours: float
    queue_size: float
    congestion_level: str


class RecommendationItem(BaseModel):
    route: str
    cost: float
    delay_factor: float


class PipelineResponse(BaseModel):
    prediction: PredictionResponse
    simulation: Optional[SimulationResponse]
    recommendation: Optional[List[RecommendationItem]]
