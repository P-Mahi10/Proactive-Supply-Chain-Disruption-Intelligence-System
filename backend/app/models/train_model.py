from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import joblib
import pandas as pd
from sklearn.metrics import precision_recall_curve
from xgboost import XGBClassifier

from app.utils.logger import get_logger

logger = get_logger(__name__)


def _load_dataset() -> pd.DataFrame:
    # Dataset is CSV-formatted despite the .xls extension.
    backend_root = Path(__file__).resolve().parents[2]
    candidate_paths = [
        backend_root / "portwatch_prediction_dataset.xls",
        backend_root / "data" / "portwatch_prediction_dataset.xls",
        backend_root.parent / "portwatch_prediction_dataset.xls",
    ]
    dataset_path = next((path for path in candidate_paths if path.exists()), None)
    if dataset_path is None:
        raise FileNotFoundError(
            "Dataset not found. Expected portwatch_prediction_dataset.xls in the repo root, backend/ directory, or backend/data/."
        )
    df = pd.read_csv(dataset_path)
    df.columns = df.columns.str.strip()
    return df


def _add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values(["port_name", "date"]).reset_index(drop=True)

    if "month" not in df.columns:
        df["month"] = df["date"].dt.month
    if "day_of_week" not in df.columns:
        df["day_of_week"] = df["date"].dt.dayofweek

    return df


def _add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    for lag in range(1, 8):
        df[f"portcalls_lag{lag}"] = df.groupby("port_name")["portcalls"].shift(lag)
        df[f"cargo_lag{lag}"] = df.groupby("port_name")["cargo_volume_teu"].shift(lag)
        df[f"rainfall_lag{lag}"] = df.groupby("port_name")["rainfall_mm"].shift(lag)
    return df


def _add_trend_features(df: pd.DataFrame) -> pd.DataFrame:
    df["trend_calls"] = df["portcalls"] - df["rolling_avg_calls_28d"]
    df["trend_cargo"] = df["cargo_volume_teu"] - df["rolling_avg_container_28d"]
    return df


def _add_target(df: pd.DataFrame) -> pd.DataFrame:
    df["target_congestion_t_plus_2"] = df.groupby("port_name")["current_congestion_level"].shift(-2)
    df["target"] = (df["target_congestion_t_plus_2"] > 0.6).astype(int)
    return df


def _select_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    base_operational = [
        "portcalls",
        "cargo_volume_teu",
        "total_trade_usd",
        "portcalls_container",
        "portcalls_dry_bulk",
        "portcalls_tanker",
        "portcalls_general_cargo",
        "import_container",
        "export_container",
        "berth_occupancy_rate",
        "vessels_in_queue",
        "historical_disruption_rate",
        "days_since_last_disruption",
        "active_disruptions_nearby",
        "disruption_flag",
        "weather_forecast_severity",
        "cyclone_probability",
        "wind_speed_kmh",
        "wave_height_m",
        "rainfall_mm",
        "visibility_km",
        "month",
        "day_of_week",
        "trend_calls",
        "trend_cargo",
        "port_name",
    ]

    lag_features = [
        f"portcalls_lag{lag}" for lag in range(1, 8)
    ] + [
        f"cargo_lag{lag}" for lag in range(1, 8)
    ] + [
        f"rainfall_lag{lag}" for lag in range(1, 8)
    ]

    feature_cols = [col for col in base_operational + lag_features if col in df.columns]
    df = df.dropna(subset=feature_cols + ["target"]).copy()

    features = df[feature_cols]
    target = df["target"]
    return features, target


def _encode_features(features: pd.DataFrame) -> pd.DataFrame:
    # Only encode port_name to preserve modularity for future categorical inputs.
    return pd.get_dummies(features, columns=["port_name"], drop_first=False)


def _time_split(features: pd.DataFrame, target: pd.Series) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    split_index = int(len(features) * 0.8)
    X_train = features.iloc[:split_index]
    X_test = features.iloc[split_index:]
    y_train = target.iloc[:split_index]
    y_test = target.iloc[split_index:]
    return X_train, X_test, y_train, y_test


def _select_threshold(y_true: pd.Series, scores: pd.Series) -> float:
    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    candidate_indices = [i for i, r in enumerate(recall) if r >= 0.75]

    if not candidate_indices:
        best_index = int((precision * recall).argmax())
        return float(thresholds[max(best_index - 1, 0)])

    best_index = max(candidate_indices, key=lambda i: precision[i])
    return float(thresholds[max(best_index - 1, 0)])


def train_and_save() -> None:
    logger.info("Loading dataset for training.")
    df = _load_dataset()
    df = _add_time_features(df)
    df = _add_lag_features(df)
    df = _add_trend_features(df)
    df = _add_target(df)

    features, target = _select_features(df)
    encoded_features = _encode_features(features)

    X_train, X_test, y_train, y_test = _time_split(encoded_features, target)

    positives = int(y_train.sum())
    negatives = int(len(y_train) - positives)
    scale_pos_weight = (negatives / positives) if positives else 1.0

    logger.info("Training XGBoost model.")
    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        scale_pos_weight=scale_pos_weight,
    )
    model.fit(X_train, y_train)

    logger.info("Selecting decision threshold using precision-recall.")
    scores = pd.Series(model.predict_proba(X_test)[:, 1])
    threshold = _select_threshold(y_test.reset_index(drop=True), scores)

    backend_root = Path(__file__).resolve().parents[2]
    data_dir = backend_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, data_dir / "congestion_model.pkl")
    joblib.dump(list(encoded_features.columns), data_dir / "model_columns.pkl")
    joblib.dump(threshold, data_dir / "model_threshold.pkl")

    logger.info("Artifacts saved to %s", data_dir)


if __name__ == "__main__":
    train_and_save()
