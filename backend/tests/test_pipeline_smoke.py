from __future__ import annotations

from pathlib import Path
import sys

backend_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_root))

from app.services import pipeline_service


def test_pipeline_smoke() -> None:
    input_data = {
        "port_name": "Busan",
        "month": 11,
        "day_of_week": 6,
        "portcalls": 59,
        "cargo_volume_teu": 378138,
        "total_trade_usd": 435498,
        "portcalls_container": 35,
        "portcalls_dry_bulk": 2,
        "portcalls_tanker": 10,
        "portcalls_general_cargo": 10,
        "import_container": 116095,
        "export_container": 262043,
        "rolling_avg_calls_28d": 60,
        "rolling_avg_container_28d": 300000,
        "berth_occupancy_rate": 0.0,
        "vessels_in_queue": 0,
        "weather_forecast_severity": 0.12,
        "cyclone_probability": 0.05,
        "wind_speed_kmh": 12.3,
        "wave_height_m": 0.0,
        "rainfall_mm": 7.1,
        "visibility_km": 9.29,
        "historical_disruption_rate": 0.0,
        "days_since_last_disruption": -1,
        "active_disruptions_nearby": 0,
        "disruption_flag": 0,
        "portcalls_lag1": 62,
        "portcalls_lag2": 60,
        "portcalls_lag3": 58,
        "portcalls_lag4": 59,
        "portcalls_lag5": 61,
        "portcalls_lag6": 57,
        "portcalls_lag7": 63,
        "cargo_lag1": 298445,
        "cargo_lag2": 310000,
        "cargo_lag3": 295000,
        "cargo_lag4": 305000,
        "cargo_lag5": 300000,
        "cargo_lag6": 290000,
        "cargo_lag7": 315000,
        "rainfall_lag1": 0.0,
        "rainfall_lag2": 2.0,
        "rainfall_lag3": 1.0,
        "rainfall_lag4": 0.0,
        "rainfall_lag5": 3.0,
        "rainfall_lag6": 0.0,
        "rainfall_lag7": 4.0,
        "trend_calls": -1.0,
        "trend_cargo": 78138.0,
    }

    response = pipeline_service.run_pipeline(input_data)

    assert 0.0 <= response.prediction.congestion_probability <= 1.0
    assert response.prediction.risk_level in {"LOW", "HIGH"}
    assert response.prediction.predicted_congestion_t_plus_2 == response.prediction.congestion_probability
    assert response.prediction.predicted_berth_occupancy_t_plus_2 >= 0.0

    if response.simulation is not None:
        assert response.simulation.estimated_delay_hours >= 0.0
        assert response.simulation.queue_size >= 0.0
