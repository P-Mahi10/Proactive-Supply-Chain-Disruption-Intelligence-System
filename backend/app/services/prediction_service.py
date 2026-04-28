from typing import Dict, Union

import pandas as pd

from app.models.model_loader import ModelLoader
from app.schemas.response_schema import PredictionResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)
model_loader = ModelLoader()


def predict(input_data: Dict[str, Union[float, str]]) -> PredictionResponse:
    try:
        logger.info("Loading model and feature columns.")
        model = model_loader.load_model()
        model_columns = model_loader.load_columns()
        threshold = model_loader.load_threshold()

        prediction_input = dict(input_data)
        prediction_input["port_name"] = prediction_input.get("origin_port", "Unknown")
        # Remove non-model fields so they don't confuse reindex
        prediction_input.pop("origin_port", None)
        prediction_input.pop("destination_port", None)

        input_frame = pd.DataFrame([prediction_input])

        # Coerce numeric-like fields to numeric types to match training dtypes.
        for col in list(input_frame.columns):
            if col == "port_name":
                continue
            # convert strings like "1" or "0" to numbers; non-convertible -> NaN
            input_frame[col] = pd.to_numeric(input_frame[col], errors="coerce")
        # Replace NaNs with 0 for missing numeric features
        input_frame = input_frame.fillna(0)

        # One-hot encode port_name as during training
        input_frame = pd.get_dummies(input_frame, columns=["port_name"], drop_first=False)
        aligned_frame = input_frame.reindex(columns=model_columns, fill_value=0)

        logger.info("Running model inference.")
        probability = _predict_probability(model, aligned_frame)
        risk_level = "HIGH" if probability > threshold else "LOW"

        # Placeholder logic: these derived values will be replaced once specialized models exist.
        predicted_congestion_t_plus_2 = probability
        # Placeholder approximation. Replace with a dedicated regression model in future.
        predicted_berth_occupancy_t_plus_2 = probability * 0.9

        return PredictionResponse(
            congestion_probability=probability,
            risk_level=risk_level,
            predicted_congestion_t_plus_2=predicted_congestion_t_plus_2,
            predicted_berth_occupancy_t_plus_2=predicted_berth_occupancy_t_plus_2,
        )
    except Exception as e:
        logger.error("Prediction failed — returning safe fallback: %s", e)
        # Return a safe default so the API doesn't crash (useful for local dev)
        return PredictionResponse(
            congestion_probability=0.0,
            risk_level="LOW",
            predicted_congestion_t_plus_2=0.0,
            predicted_berth_occupancy_t_plus_2=0.0,
        )


def _predict_probability(model: object, aligned_features: pd.DataFrame) -> float:
    # Supports both predict_proba and predict to stay compatible with multiple model types.
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(aligned_features)
        return float(proba[0][1])

    prediction = model.predict(aligned_features)
    return float(prediction[0])


def get_threshold() -> float:
    return model_loader.load_threshold()
