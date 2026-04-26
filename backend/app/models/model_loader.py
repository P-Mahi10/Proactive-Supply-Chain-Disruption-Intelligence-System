"""
backend/app/models/model_loader.py
====================================
Loads XGBoost model, feature columns, and threshold from
the data/ directory (relative to backend root).

Singleton pattern — files loaded once on first access.
"""

import os
from typing import List

import joblib
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Resolve data/ directory regardless of working directory
_HERE      = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR  = os.path.abspath(os.path.join(_HERE, "../../data"))


class ModelLoader:

    def __init__(self) -> None:
        self._model           = None
        self._columns: List[str] | None = None
        self._threshold: float | None   = None

    def load_model(self):
        if self._model is None:
            path = os.path.join(_DATA_DIR, "congestion_model.pkl")
            if not os.path.exists(path):
                raise FileNotFoundError(
                    f"Model not found at {path}. "
                    "Run model.py to train and save congestion_model.pkl."
                )
            self._model = joblib.load(path)
            logger.info("Model loaded from %s", path)
        return self._model

    def load_columns(self) -> List[str]:
        if self._columns is None:
            path = os.path.join(_DATA_DIR, "model_columns.pkl")
            if not os.path.exists(path):
                raise FileNotFoundError(
                    f"Columns not found at {path}. "
                    "Run model.py to save model_columns.pkl."
                )
            self._columns = joblib.load(path)
            logger.info("Feature columns loaded: %d columns", len(self._columns))
        return self._columns

    def load_threshold(self) -> float:
        if self._threshold is None:
            path = os.path.join(_DATA_DIR, "model_threshold.pkl")
            if os.path.exists(path):
                self._threshold = float(joblib.load(path))
                logger.info("Threshold loaded: %.3f", self._threshold)
            else:
                # Default matches the 0.6 threshold from model.py
                self._threshold = 0.6
                logger.warning(
                    "model_threshold.pkl not found — using default threshold 0.6"
                )
        return self._threshold