"""
backend/app/services/pipeline_service.py
=========================================
Orchestrates: predict → simulate → LLM recommendations.
"""

from typing import Dict, Optional, Union

from app.schemas.response_schema import PipelineResponse, PredictionResponse, SimulationResponse
from app.services import firebase_service, prediction_service, simulation_service, solution_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _maybe_simulate(
    prediction:  PredictionResponse,
    input_data:  Dict[str, Union[float, str]],
    threshold:   float,
) -> Optional[SimulationResponse]:
    if not simulation_service.should_trigger(prediction, threshold):
        logger.info("Simulation skipped (risk below threshold).")
        return None
    logger.info("Simulation triggered.")
    return simulation_service.simulate(prediction, input_data)


def run_pipeline(
    input_data: Dict[str, Union[float, str]],
) -> PipelineResponse:
    logger.info("Running pipeline orchestration.")
    
    prediction = prediction_service.predict(input_data)
    threshold  = prediction_service.get_threshold()
    logger.info(
        "Prediction: prob=%.3f risk=%s threshold=%.3f",
        prediction.congestion_probability,
        prediction.risk_level,
        threshold,
    )

    # ── Step 2: Simulation ────────────────────────────────────────
    simulation = _maybe_simulate(prediction, input_data, threshold)

    # ── Step 3: LLM recommendations ───────────────────────────────
    advisory       = None
    recommendation = None

    if simulation is not None:
        advisory, recommendation = solution_service.get_llm_recommendations(
            prediction  = prediction,
            simulation  = simulation,
            input_data  = input_data,
        )
        logger.info(
            "LLM advisory generated. Recommendations: %d",
            len(recommendation) if recommendation else 0,
        )
    else:
        logger.info("LLM step skipped — simulation not triggered.")

    response = PipelineResponse(
        prediction=prediction,
        simulation=simulation,
        recommendation=recommendation,
        advisory=advisory,
    )
    
    # Save run (input + output) to Firebase for history
    firebase_service.save_pipeline_run(
        output_data=response.model_dump(),
        input_data=input_data,
    )
    
    return response
