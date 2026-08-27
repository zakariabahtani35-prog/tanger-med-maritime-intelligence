"""
Maritime Anomaly & Risk Detection Engine (Isolation Forest)
Trains an unsupervised Isolation Forest model to detect navigational and kinematic anomalies
(suspicious speed drops in TSS corridors, erratic heading deviations, severe drift off shipping lanes).
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Tuple

# Add root directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import joblib
import numpy as np
import pandas as pd
import structlog
from sklearn.ensemble import IsolationForest

logger = structlog.get_logger(__name__)

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
ANOMALY_MODEL_PATH = ARTIFACTS_DIR / "anomaly_model.joblib"

ANOMALY_FEATURE_COLS = [
    "speed_knots",
    "speed_delta",
    "heading_deviation",
    "corridor_distance_offset",
]


def generate_synthetic_anomaly_dataset(n_samples: int = 1500, anomaly_ratio: float = 0.08) -> pd.DataFrame:
    """
    Generates realistic maritime kinematic training set containing nominal navigation
    patterns along with realistic anomalous behaviors.
    """
    np.random.seed(42)
    n_anomalies = int(n_samples * anomaly_ratio)
    n_nominal = n_samples - n_anomalies

    # 1. Nominal Navigation Traffic (92%)
    nominal_speed = np.random.normal(loc=17.5, scale=3.0, size=n_nominal).clip(8.0, 26.0)
    nominal_delta = np.random.exponential(scale=0.6, size=n_nominal).clip(0.0, 2.5)
    nominal_heading_dev = np.random.exponential(scale=3.5, size=n_nominal).clip(0.0, 18.0)
    nominal_corridor_offset = np.random.exponential(scale=2.5, size=n_nominal).clip(0.1, 7.5)

    # 2. Anomalous Traffic (8%)
    # Sub-patterns:
    # A. Suspicious standstill / engine cutoff in TSS corridor (speed ~ 0-2 kn, high delta)
    # B. Erratic sharp turns / zigzag drift (heading dev 60-170 deg)
    # C. Severe lane departure / unauthorized drift (corridor offset 18-50 km)
    anom_speed = np.random.choice([0.4, 2.1, 29.5, 34.0, 1.2], size=n_anomalies) + np.random.normal(0, 0.5, size=n_anomalies)
    anom_speed = anom_speed.clip(0.0, 45.0)
    anom_delta = np.random.uniform(5.0, 16.0, size=n_anomalies)
    anom_heading_dev = np.random.uniform(45.0, 175.0, size=n_anomalies)
    anom_corridor_offset = np.random.uniform(14.0, 48.0, size=n_anomalies)

    speeds = np.concatenate([nominal_speed, anom_speed])
    deltas = np.concatenate([nominal_delta, anom_delta])
    heading_devs = np.concatenate([nominal_heading_dev, anom_heading_dev])
    offsets = np.concatenate([nominal_corridor_offset, anom_corridor_offset])

    df = pd.DataFrame({
        "speed_knots": np.round(speeds, 2),
        "speed_delta": np.round(deltas, 2),
        "heading_deviation": np.round(heading_devs, 2),
        "corridor_distance_offset": np.round(offsets, 2),
    })

    return df.sample(frac=1.0, random_state=42).reset_index(drop=True)


def train_anomaly_detector(save_artifact: bool = True) -> Dict[str, Any]:
    """
    Trains the Isolation Forest anomaly detector, computes baseline anomaly score bounds,
    and serializes the model to disk.
    """
    logger.info("Initializing Maritime Anomaly Detection Training Pipeline (Isolation Forest)...")

    # 1. Generate training dataset
    df = generate_synthetic_anomaly_dataset(n_samples=1600, anomaly_ratio=0.08)
    X = df[ANOMALY_FEATURE_COLS]

    # 2. Train Isolation Forest
    model = IsolationForest(
        n_estimators=150,
        max_samples="auto",
        contamination=0.08,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X)

    # 3. Compute reference calibration scores for normalization
    raw_scores = -model.score_samples(X)  # Higher is more abnormal
    min_score = float(np.min(raw_scores))
    max_score = float(np.max(raw_scores))

    # Evaluate predictions on synthetic set
    normalized_scores = (raw_scores - min_score) / max(1e-5, (max_score - min_score))
    detected_anomalies = np.sum(normalized_scores > 0.65)

    print("=" * 60)
    print(" 🛡️ ISOLATION FOREST MARITIME ANOMALY DETECTOR - TRAINING RESULTS")
    print("=" * 60)
    print(f"  📊 Training Samples:         {len(X)}")
    print(f"  🎯 Contamination Rate:       0.08 (8%)")
    print(f"  🔍 Min Raw Score:            {min_score:.4f}")
    print(f"  🔍 Max Raw Score:            {max_score:.4f}")
    print(f"  🚨 Detected Outliers (>0.65): {detected_anomalies} ({detected_anomalies / len(X) * 100:.2f}%)")
    print("=" * 60)

    # 4. Save artifact
    if save_artifact:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": model,
            "feature_names": ANOMALY_FEATURE_COLS,
            "calibration": {
                "min_score": min_score,
                "max_score": max_score,
                "threshold": 0.65,
            },
            "trained_at": datetime.now(timezone.utc).isoformat(),
        }
        joblib.dump(payload, ANOMALY_MODEL_PATH)
        print(f"  💾 Anomaly Model saved to: {ANOMALY_MODEL_PATH}")

    return {
        "model": model,
        "min_score": min_score,
        "max_score": max_score,
        "model_path": str(ANOMALY_MODEL_PATH),
    }


def score_anomaly_vector(
    model: IsolationForest,
    feature_vector: np.ndarray,
    min_score: float = 0.35,
    max_score: float = 0.75,
) -> Tuple[float, bool]:
    """
    Computes calibrated anomaly score [0.0, 1.0] and binary flag for a single vessel feature vector.
    """
    raw = -float(model.score_samples(feature_vector.reshape(1, -1))[0])
    norm = (raw - min_score) / max(1e-5, (max_score - min_score))
    norm_clamped = float(max(0.0, min(1.0, round(norm, 3))))
    is_anom = bool(norm_clamped > 0.65)
    return norm_clamped, is_anom


if __name__ == "__main__":
    train_anomaly_detector(save_artifact=True)
