"""
Port Dwell Time & Congestion Prediction Engine (XGBoost Regressor)
Trains and evaluates gradient-boosted regression model to predict
vessel waiting & dwell times before berthing at Tanger Med & Casablanca.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

# Add root directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import joblib
import numpy as np
import pandas as pd
import structlog
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import xgboost as xgb

from ml_engine.feature_engineering import (
    PORT_COORDINATES,
    haversine_distance_km,
    extract_dwell_features,
)

logger = structlog.get_logger(__name__)

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "dwell_model.joblib"

DWELL_FEATURE_COLS = [
    "vessel_type_encoded",
    "current_speed",
    "distance_to_port_km",
    "port_queue_density",
    "hour_of_day",
    "day_of_week",
]


def generate_synthetic_historical_dwell_dataset(n_samples: int = 1200) -> pd.DataFrame:
    """
    Generates realistic historical maritime dataset calibrated to Tanger Med & Casablanca operations.
    Includes container ships, crude tankers, bulk carriers, ro-ro, and general cargo.
    """
    np.random.seed(42)

    data = []
    ports = ["MAPTM", "MACAS"]

    for _ in range(n_samples):
        port_code = np.random.choice(ports, p=[0.65, 0.35])
        port_lat, port_lon = PORT_COORDINATES[port_code]

        vessel_type_idx = np.random.choice([0, 1, 2, 3, 4, 5, 6], p=[0.45, 0.15, 0.08, 0.12, 0.10, 0.05, 0.05])
        
        # Spatial placement: approaching vessel between 0.5 km and 120 km from port
        dist_km = np.random.exponential(scale=25.0) + 0.5
        bearing_rad = np.random.uniform(0, 2 * np.pi)
        
        # Approximate lat/lon displacement
        d_lat = (dist_km / 111.0) * np.cos(bearing_rad)
        d_lon = (dist_km / (111.0 * np.cos(np.radians(port_lat)))) * np.sin(bearing_rad)
        lat = port_lat + d_lat
        lon = port_lon + d_lon

        speed = max(0.0, np.random.normal(loc=14.0 if dist_km > 15 else 3.0, scale=3.5))
        queue_density = int(np.random.poisson(lam=5 if port_code == "MAPTM" else 7))
        hour = np.random.randint(0, 24)
        day = np.random.randint(0, 7)

        # Realistic physics-based dwell formula + random operational noise
        # Base dwell by vessel type: Container ~ 14h, Tanker ~ 24h, Bulk ~ 32h, Cargo ~ 20h
        base_dwell = {0: 14.0, 1: 24.0, 2: 26.0, 3: 32.0, 4: 20.0, 5: 4.0, 6: 12.0}.get(vessel_type_idx, 18.0)
        
        # Port efficiency factor (Tanger Med is highly automated ~ 0.85x, Casablanca ~ 1.15x)
        port_factor = 0.85 if port_code == "MAPTM" else 1.15

        # Distance & speed component: time to reach berth zone
        travel_time = dist_km / max(1.0, speed) if speed > 1.0 else 0.5

        # Queue congestion multiplier
        queue_penalty = queue_density * 1.85

        # Peak hours congestion factor (08:00 - 18:00)
        time_penalty = 2.5 if 8 <= hour <= 18 else 0.5

        # Target waiting & dwell hours
        dwell_hours = (base_dwell * port_factor) + (queue_penalty) + (travel_time * 0.4) + time_penalty + np.random.normal(0, 2.0)
        dwell_hours = float(max(1.5, round(dwell_hours, 2)))

        data.append({
            "vessel_type_encoded": float(vessel_type_idx),
            "current_speed": float(round(speed, 2)),
            "distance_to_port_km": float(round(dist_km, 2)),
            "port_queue_density": float(queue_density),
            "hour_of_day": float(hour),
            "day_of_week": float(day),
            "waiting_time_hours": dwell_hours,
        })

    return pd.DataFrame(data)


def train_dwell_predictor(save_artifact: bool = True) -> Dict[str, Any]:
    """
    Trains the XGBoost Regressor for Port Dwell Time prediction, evaluates metrics,
    and serializes the trained model artifact to disk.
    """
    logger.info("Initializing Port Dwell Time Prediction Training Pipeline (XGBoost Regressor)...")
    
    # 1. Prepare training dataset
    df = generate_synthetic_historical_dwell_dataset(n_samples=1500)
    X = df[DWELL_FEATURE_COLS]
    y = df["waiting_time_hours"]

    # 2. Train-test split (80% train, 20% test)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)

    # 3. Initialize and train XGBoost Regressor
    model = xgb.XGBRegressor(
        n_estimators=150,
        max_depth=5,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        objective="reg:squarederror",
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # 4. Evaluation
    y_pred = model.predict(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae = float(mean_absolute_error(y_test, y_pred))
    r2 = float(r2_score(y_test, y_pred))

    print("=" * 60)
    print(" 🚀 XGBOOST PORT DWELL TIME PREDICTOR - TRAINING RESULTS")
    print("=" * 60)
    print(f"  📊 Training Samples:    {len(X_train)}")
    print(f"  🧪 Testing Samples:     {len(X_test)}")
    print(f"  📉 Root Mean Sq Error:  {rmse:.3f} hours")
    print(f"  📐 Mean Absolute Error: {mae:.3f} hours")
    print(f"  ⭐ R² Score:            {r2:.4f} ({r2 * 100:.2f}% variance explained)")
    print("=" * 60)

    # 5. Persist artifact
    if save_artifact:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": model,
            "feature_names": DWELL_FEATURE_COLS,
            "metrics": {"rmse": rmse, "mae": mae, "r2": r2},
            "trained_at": datetime.now(timezone.utc).isoformat(),
        }
        joblib.dump(payload, MODEL_PATH)
        print(f"  💾 Model saved to: {MODEL_PATH}")

    return {
        "model": model,
        "rmse": rmse,
        "mae": mae,
        "r2": r2,
        "model_path": str(MODEL_PATH),
    }


if __name__ == "__main__":
    train_dwell_predictor(save_artifact=True)
