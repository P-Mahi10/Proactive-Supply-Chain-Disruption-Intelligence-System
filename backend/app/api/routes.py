from typing import List

from fastapi import APIRouter, HTTPException, Header

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


def _extract_user_id(authorization: str = None) -> str:
    """
    Extracts user_id from Firebase auth token in Authorization header.
    Header format: "Bearer {token}"
    Returns empty string if no valid auth header.
    """
    if not authorization:
        logger.warning("No authorization header provided")
        return ""
    
    try:
        # Extract token from "Bearer {token}" format
        parts = authorization.split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer":
            logger.warning("Invalid authorization header format")
            return ""
        
        token = parts[1]
        
        # Try to verify the token using Firebase Admin SDK
        try:
            from firebase_admin import auth
            decoded_token = auth.verify_id_token(token)
            user_id = decoded_token.get("uid", "")
            logger.info(f"Extracted user_id from token: {user_id}")
            return user_id
        except Exception as auth_err:
            logger.warning(f"Firebase token verification failed: {auth_err}")
            # If Firebase verification fails, try to decode without verification
            # This is useful for development/testing
            import base64
            try:
                # JWT format: header.payload.signature
                parts = token.split(".")
                if len(parts) == 3:
                    # Decode the payload (add padding if needed)
                    payload = parts[1]
                    payload += "=" * (4 - len(payload) % 4)
                    decoded = base64.urlsafe_b64decode(payload)
                    import json as json_module
                    payload_data = json_module.loads(decoded)
                    user_id = payload_data.get("sub", "")
                    logger.info(f"Extracted user_id from unverified token: {user_id}")
                    return user_id
            except Exception as decode_err:
                logger.warning(f"Failed to decode token payload: {decode_err}")
                return ""
        
    except Exception as e:
        logger.warning(f"Failed to extract user_id from auth header: {e}")
        return ""


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
def run_pipeline(request: InputRequest, authorization: str = Header(None)) -> PipelineResponse:
    logger.info("Request received: /run_pipeline")
    user_id = _extract_user_id(authorization)
    logger.info(f"Running pipeline for user_id: {user_id if user_id else 'EMPTY'}")
    response = pipeline_service.run_pipeline(request.input_data, user_id=user_id)
    logger.info("Pipeline response assembled.")
    return response


@router.get("/history")
def get_history(limit: int = 20, authorization: str = Header(None)):
    logger.info("Request received: /history")
    user_id = _extract_user_id(authorization)
    logger.info(f"Extracted user_id: {user_id if user_id else 'EMPTY - will fetch all runs'}")
    history = firebase_service.get_recent_runs(
        user_id=user_id,
        limit=limit,
    )
    logger.info(f"History query returned {len(history)} records")
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