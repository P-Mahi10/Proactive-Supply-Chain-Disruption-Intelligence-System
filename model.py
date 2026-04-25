import pandas as pd
import numpy as np

from sklearn.metrics import classification_report, roc_auc_score
from sklearn.metrics import precision_recall_curve
from xgboost import XGBClassifier
import joblib

# =========================
# 1. LOAD DATA
# =========================
df = pd.read_csv("portwatch_prediction_dataset.xls")
df.columns = df.columns.str.strip()

# =========================
# 2. SORT
# =========================
df = df.sort_values(by=["port_name", "date"])

# =========================
# 3. LAG FEATURES (7 days)
# =========================
for lag in range(1, 8):
    df[f"portcalls_lag{lag}"] = df.groupby("port_name")["portcalls"].shift(lag)
    df[f"cargo_lag{lag}"] = df.groupby("port_name")["cargo_volume_teu"].shift(lag)
    df[f"rainfall_lag{lag}"] = df.groupby("port_name")["rainfall_mm"].shift(lag)

# =========================
# 4. TREND FEATURES
# =========================
df["trend_calls"] = df["portcalls"] - df["rolling_avg_calls_28d"]
df["trend_cargo"] = df["cargo_volume_teu"] - df["rolling_avg_container_28d"]

# =========================
# 5. TARGET (t+2)
# =========================
df["target_congestion_t+2"] = df.groupby("port_name")["current_congestion_level"].shift(-2)
df = df.dropna(subset=["target_congestion_t+2"])

df["target_congestion_t+2"] = (df["target_congestion_t+2"] > 0.6).astype(int)

# =========================
# 6. FEATURE LIST
# =========================
base_features = [
    "portcalls",
    "cargo_volume_teu",
    "total_trade_usd",

    "rolling_avg_calls_28d",
    "rolling_avg_container_28d",
    "rolling_avg_trade_28d",

    "weather_forecast_severity",
    "cyclone_probability",
    "wind_speed_kmh",
    "wave_height_m",
    "rainfall_mm",
    "visibility_km",

    "historical_disruption_rate",
    "days_since_last_disruption",
    "active_disruptions_nearby",

    "month",
    "day_of_week",

    "trend_calls",
    "trend_cargo"
]

lag_features = [col for col in df.columns if "lag" in col]

features = base_features + lag_features

df_model = df[features + ["port_name", "season", "target_congestion_t+2"]]

# =========================
# 7. ENCODE
# =========================
df_model = pd.get_dummies(df_model, columns=["port_name", "season"], drop_first=True)

# =========================
# 8. CLEAN
# =========================
df_model = df_model.fillna(0)

# =========================
# 9. SPLIT
# =========================
X = df_model.drop(columns=["target_congestion_t+2"])
y = df_model["target_congestion_t+2"]

split_index = int(len(df_model) * 0.8)
X_train, X_test = X.iloc[:split_index], X.iloc[split_index:]
y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]

# =========================
# 10. CLASS WEIGHT
# =========================
scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()

# =========================
# 11. MODEL
# =========================
model = XGBClassifier(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    eval_metric='logloss',
    scale_pos_weight=scale_pos_weight
)

model.fit(X_train, y_train)

# =========================
# 12. THRESHOLD TUNING
# =========================
y_prob = model.predict_proba(X_test)[:, 1]

precision, recall, thresholds = precision_recall_curve(y_test, y_prob)

# pick threshold where recall ~0.75
best_threshold = 0.6

y_pred = (y_prob > best_threshold).astype(int)

print("\nClassification Report:")
print(classification_report(y_test, y_pred))

print("\nROC-AUC Score:")
print(roc_auc_score(y_test, y_prob))

# =========================
# 13. SAVE
# =========================
joblib.dump(model, "congestion_model.pkl")
joblib.dump(X.columns.tolist(), "model_columns.pkl")

print("\nModel saved")