from pathlib import Path
from typing import List

import joblib

from app.utils.logger import get_logger

logger = get_logger(__name__)


class ModelLoader:
    """Centralized loader for ML model artifacts."""

    def __init__(self) -> None:
        self._model = None
        self._columns: List[str] | None = None
        self._threshold: float | None = None

    def load_model(self) -> object:
        if self._model is None:
            model_path = self._data_path("congestion_model.pkl")
            logger.info("Loading model from %s", model_path)
            self._model = joblib.load(model_path)
        return self._model

    def load_columns(self) -> List[str]:
        if self._columns is None:
            columns_path = self._data_path("model_columns.pkl")
            logger.info("Loading model columns from %s", columns_path)
            self._columns = joblib.load(columns_path)
        return self._columns

    def load_threshold(self) -> float:
        if self._threshold is None:
            threshold_path = self._data_path("model_threshold.pkl")
            logger.info("Loading model threshold from %s", threshold_path)
            self._threshold = float(joblib.load(threshold_path))
        return self._threshold

    def _data_path(self, filename: str) -> Path:
        backend_root = Path(__file__).resolve().parents[2]
        return backend_root / "data" / filename
