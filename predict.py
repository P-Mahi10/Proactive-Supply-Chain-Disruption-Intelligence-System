import pandas as pd
import joblib

model = joblib.load("congestion_model.pkl")
model_columns = joblib.load("model_columns.pkl")

def predict_risk(input_dict):

    df = pd.DataFrame([input_dict])
    df = pd.get_dummies(df)

    # align with training columns
    df = df.reindex(columns=model_columns, fill_value=0)

    prob = model.predict_proba(df)[0][1]

    return {
        "congestion_probability": float(prob),
        "risk_level": "HIGH" if prob > 0.6 else "LOW"
    }


# =========================
# EXAMPLE INPUT
# =========================
sample_input = {
    "portcalls": 120,
    "cargo_volume_teu": 50000,
    "total_trade_usd": 1000000,

    "rolling_avg_calls_28d": 110,
    "rolling_avg_container_28d": 48000,
    "rolling_avg_trade_28d": 950000,

    "weather_forecast_severity": 2,
    "cyclone_probability": 0.3,
    "wind_speed_kmh": 40,
    "wave_height_m": 2,
    "rainfall_mm": 25,
    "visibility_km": 5,

    "historical_disruption_rate": 0.2,
    "days_since_last_disruption": 10,
    "active_disruptions_nearby": 1,

    "month": 7,
    "day_of_week": 3,

    "trend_calls": 10,
    "trend_cargo": 2000,

    "port_name": "Chennai",
    "season": "monsoon",

    # lag features (last 7 days)
    "portcalls_lag1": 115,
    "portcalls_lag2": 110,
    "portcalls_lag3": 105,
    "portcalls_lag4": 100,
    "portcalls_lag5": 95,
    "portcalls_lag6": 90,
    "portcalls_lag7": 85,

    "cargo_lag1": 48000,
    "cargo_lag2": 47000,
    "cargo_lag3": 46000,
    "cargo_lag4": 45000,
    "cargo_lag5": 44000,
    "cargo_lag6": 43000,
    "cargo_lag7": 42000,

    "rainfall_lag1": 20,
    "rainfall_lag2": 15,
    "rainfall_lag3": 10,
    "rainfall_lag4": 5,
    "rainfall_lag5": 0,
    "rainfall_lag6": 0,
    "rainfall_lag7": 0
}

print(predict_risk(sample_input))