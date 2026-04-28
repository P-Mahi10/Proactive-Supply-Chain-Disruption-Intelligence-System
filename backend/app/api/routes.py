from typing import List

from fastapi import APIRouter, HTTPException

from app.schemas.request_schema import ChatRequest, InputRequest
from app.schemas.response_schema import (
    PipelineResponse,
    PredictionResponse,
    RecommendationItem,
    RouteSummary,
    SimulationResponse,
)
from app.services import (
    db_service,
    firebase_service,
    pipeline_service,
    prediction_service,
    simulation_service,
    solution_service,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/predict", response_model=PredictionResponse)
def predict(request: InputRequest) -> PredictionResponse:
    logger.info("Request received: /predict")
    prediction = prediction_service.predict(request.input_data)
    logger.info("Prediction output: %s", prediction.model_dump())
    return prediction


@router.post("/simulate", response_model=SimulationResponse)
def simulate(request: InputRequest) -> SimulationResponse:
    logger.info("Request received: /simulate")
    prediction = prediction_service.predict(request.input_data)

    threshold = prediction_service.get_threshold()
    if not simulation_service.should_trigger(prediction, threshold):
        logger.info("Simulation skipped (risk below threshold).")
        return SimulationResponse(
            estimated_delay_hours=0.0,
            queue_size=0.0,
            congestion_level="LOW",
        )

    simulation = simulation_service.simulate(prediction, request.input_data)
    logger.info("Simulation output: %s", simulation.model_dump())
    return simulation


@router.post("/recommend", response_model=List[RecommendationItem])
def recommend(request: InputRequest) -> List[RecommendationItem]:
    logger.info("Request received: /recommend")
    recommendations = solution_service.get_recommendations(request.input_data)
    logger.info("Recommendation output count: %d", len(recommendations))
    return recommendations


@router.post("/run_pipeline", response_model=PipelineResponse)
def run_pipeline(request: InputRequest) -> PipelineResponse:
    logger.info("Request received: /run_pipeline")
    response = pipeline_service.run_pipeline(request.input_data)
    logger.info("Pipeline response assembled.")
    return response


@router.get("/history")
def get_history(limit: int = 20):
    logger.info("Request received: /history")
    history = firebase_service.get_recent_runs(
        limit=limit,
    )
    return history


@router.get("/routes", response_model=list[RouteSummary])
def get_routes(limit: int = 5):
    logger.info("Request received: /routes")
    return db_service.fetch_best_routes(limit=limit)


@router.post("/chat")
def save_chat(request: ChatRequest):
    logger.info("Request received: /chat")
    saved = firebase_service.save_chat_message(
        conversation_id=request.conversation_id,
        message=request.message,
    )
    if not saved:
        raise HTTPException(status_code=503, detail="Firebase not initialized")
    return {"status": "saved"}