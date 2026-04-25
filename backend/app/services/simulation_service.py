from typing import Dict, Union

from app.schemas.response_schema import PredictionResponse, SimulationResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)

def should_trigger(prediction: PredictionResponse, threshold: float) -> bool:
    # The threshold used here is derived from model evaluation and directly determines whether the simulation engine is triggered.
    return prediction.congestion_probability > threshold


def simulate(prediction: PredictionResponse, input_data: Dict[str, Union[float, str]]) -> SimulationResponse:
    logger.info("Starting simulation based on prediction and input data.")

    rainfall = float(input_data.get("rainfall", 0.0))
    disruption_severity = float(input_data.get("disruption_severity", 0.0))
    base_queue = float(input_data.get("current_queue", 10.0))

    # Simple capacity reduction model influenced by rainfall and disruption severity.
    capacity_reduction = min(0.9, 0.1 + (rainfall * 0.05) + (disruption_severity * 0.3))

    # Queue buildup reflects reduced throughput and higher congestion probability.
    queue_size = base_queue * (1.0 + capacity_reduction + prediction.congestion_probability)

    # Delay increases with queue size and capacity reduction.
    estimated_delay_hours = max(0.0, queue_size * 0.2 + capacity_reduction * 5.0)

    congestion_level = "HIGH" if prediction.congestion_probability > 0.8 else "MEDIUM"

    return SimulationResponse(
        estimated_delay_hours=estimated_delay_hours,
        queue_size=queue_size,
        congestion_level=congestion_level,
    )
