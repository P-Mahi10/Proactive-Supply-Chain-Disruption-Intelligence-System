from typing import Dict, Optional, Union

from app.schemas.response_schema import PipelineResponse, PredictionResponse, SimulationResponse
from app.services import prediction_service, simulation_service, solution_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _maybe_simulate(
    prediction: PredictionResponse,
    input_data: Dict[str, Union[float, str]],
    threshold: float,
) -> Optional[SimulationResponse]:
    if not simulation_service.should_trigger(prediction, threshold):
        logger.info("Simulation skipped (risk below threshold).")
        return None

    logger.info("Simulation triggered.")
    return simulation_service.simulate(prediction, input_data)


def run_pipeline(input_data: Dict[str, Union[float, str]]) -> PipelineResponse:
    logger.info("Running pipeline orchestration.")
    prediction = prediction_service.predict(input_data)
    threshold = prediction_service.get_threshold()
    simulation = _maybe_simulate(prediction, input_data, threshold)
    recommendation = None

    if simulation is not None:
        recommendation = solution_service.get_recommendations(input_data)
        logger.info("Recommendations generated.")

    return PipelineResponse(
        prediction=prediction,
        simulation=simulation,
        recommendation=recommendation,
    )
