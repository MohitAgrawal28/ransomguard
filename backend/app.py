"""
PHASE 8 — BACKEND API
======================
Flask REST API that:
  - Loads the trained LSTM model at startup
  - /predict  → accepts behavioral features, returns ransomware probability
  - /monitor  → returns current system monitoring status
  - /alert    → receives alerts from the detection engine
  - /health   → liveness check
  - /logs     → returns recent attack logs

Designed to run alongside the detection engine and feed
the frontend dashboard with live data.
"""

import os
import sys
import json
import time
import threading
from datetime import datetime
from collections import deque
from typing import Optional, List

import numpy as np
import joblib
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

# ─────────────────────────────────────────────────────────────
# BOOTSTRAP
# ─────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)   # Allow React frontend to call this API

# ─────────────────────────────────────────────────────────────
# MODEL STATE (loaded once at startup)
# ─────────────────────────────────────────────────────────────

class ModelServer:
    """Thread-safe model loader and inference server."""

    FEATURE_ORDER = [
        "file_write_count", "file_rename_count", "entropy_before",
        "entropy_after", "entropy_change", "process_execution_time",
        "api_call_frequency", "file_access_rate", "extension_change_count",
        "encryption_indicator", "rename_to_write_ratio", "entropy_spike",
        "aggression_score", "ext_change_rate",
    ]

    def __init__(self):
        self.model  = None
        self.scaler = None
        self.meta   = {}
        self.loaded = False
        self._lock  = threading.Lock()
        self._load()

    def _load(self):
        try:
            import tensorflow as tf
            self.model  = tf.keras.models.load_model("models/ransomware_lstm.h5")
            self.scaler = joblib.load("models/scaler.pkl")
            with open("models/training_metadata.json") as f:
                self.meta = json.load(f)
            self.loaded = True
            print("✅ Model loaded successfully")
        except Exception as e:
            print(f"⚠️  Model not loaded: {e}")
            print("   Run: python models/train_model.py")

    def predict(self, features: dict) -> dict:
        if not self.loaded:
            return {"error": "model_not_loaded", "probability": -1}

        with self._lock:
            try:
                vec = np.array([[features.get(f, 0.0) for f in self.FEATURE_ORDER]],
                               dtype=np.float32)
                n = self.scaler.n_features_in_
                vec = vec[:, :n]
                vec_scaled = self.scaler.transform(vec)
                vec_3d = vec_scaled.reshape(1, 1, vec_scaled.shape[1])
                prob = float(self.model.predict(vec_3d, verbose=0)[0][0])
                label = "ransomware" if prob >= 0.5 else "benign"
                confidence = prob if prob >= 0.5 else 1 - prob
                return {
                    "probability": round(prob, 6),
                    "label": label,
                    "confidence": round(confidence, 6),
                    "threshold": 0.5,
                }
            except Exception as e:
                return {"error": str(e), "probability": -1}


# ─────────────────────────────────────────────────────────────
# APPLICATION STATE
# ─────────────────────────────────────────────────────────────

model_server = ModelServer()

# In-memory alert store (use Redis/DB in production)
alert_store: deque = deque(maxlen=500)
alert_store_lock = threading.Lock()

# System monitoring stats
monitor_stats = {
    "start_time":         datetime.now().isoformat(),
    "total_predictions":  0,
    "ransomware_detections": 0,
    "processes_killed":   0,
    "watch_directory":    os.path.expanduser("~/Documents"),
    "engine_status":      "running",
}


# ─────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────

def success(data: dict, status: int = 200):
    return jsonify({"success": True, "data": data, "timestamp": datetime.now().isoformat()}), status

def error(msg: str, status: int = 400):
    return jsonify({"success": False, "error": msg, "timestamp": datetime.now().isoformat()}), status


# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """Liveness/readiness check."""
    return success({
        "status":       "ok",
        "model_loaded": model_server.loaded,
        "uptime_secs":  round(time.time() - app._start_time, 1),
        "version":      "1.0.0",
    })


@app.route("/predict", methods=["POST"])
def predict():
    """
    Predict whether a behavioral snapshot represents ransomware.
    
    Request body (JSON):
    {
        "file_write_count": 1500,
        "file_rename_count": 1200,
        "entropy_before": 4.2,
        "entropy_after": 7.8,
        "entropy_change": 3.6,
        "process_execution_time": 12.5,
        "api_call_frequency": 8000,
        "file_access_rate": 45.0,
        "extension_change_count": 800,
        "encryption_indicator": 0.92,
        ...optional engineered features...
    }
    
    Response:
    {
        "probability": 0.9873,
        "label": "ransomware",
        "confidence": 0.9873,
        "threshold": 0.5
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return error("Request body must be JSON")

    result = model_server.predict(data)

    if "error" not in result:
        monitor_stats["total_predictions"] += 1
        if result["label"] == "ransomware":
            monitor_stats["ransomware_detections"] += 1

    return success(result)


@app.route("/predict/batch", methods=["POST"])
def predict_batch():
    """
    Batch prediction for multiple snapshots.
    Body: {"samples": [{...}, {...}]}
    """
    data = request.get_json(silent=True)
    if not data or "samples" not in data:
        return error("Missing 'samples' array")

    results = []
    for sample in data["samples"][:100]:   # Cap at 100
        results.append(model_server.predict(sample))

    return success({"predictions": results, "count": len(results)})


@app.route("/monitor", methods=["GET"])
def monitor():
    """
    Return current monitoring engine status.
    Called by the frontend to display live stats.
    """
    with alert_store_lock:
        recent_alerts = list(alert_store)[-10:]

    return success({
        **monitor_stats,
        "recent_alerts":  recent_alerts,
        "model_meta":     model_server.meta,
        "alert_count":    len(alert_store),
    })


@app.route("/alert", methods=["POST"])
def receive_alert():
    """
    Receive an alert from the detection engine.
    The detection engine POSTs here when ransomware is detected.
    """
    data = request.get_json(silent=True)
    if not data:
        return error("Invalid JSON")

    data["received_at"] = datetime.now().isoformat()

    with alert_store_lock:
        alert_store.append(data)

    if data.get("type") == "process_killed":
        monitor_stats["processes_killed"] += 1

    print(f"🚨 ALERT received: {data.get('process_name','?')} "
          f"pid={data.get('pid','?')} "
          f"prob={data.get('probability','?')}")

    return success({"stored": True, "alert_id": len(alert_store)})


@app.route("/alerts", methods=["GET"])
def get_alerts():
    """Get all stored alerts (paginated)."""
    page  = int(request.args.get("page", 1))
    limit = min(int(request.args.get("limit", 20)), 100)
    with alert_store_lock:
        all_alerts = list(alert_store)
    total  = len(all_alerts)
    start  = (page - 1) * limit
    subset = all_alerts[start:start + limit]
    return success({
        "alerts": subset,
        "total":  total,
        "page":   page,
        "limit":  limit,
    })


@app.route("/alerts/clear", methods=["DELETE"])
def clear_alerts():
    """Clear all stored alerts (admin action)."""
    with alert_store_lock:
        count = len(alert_store)
        alert_store.clear()
    return success({"cleared": count})


@app.route("/logs", methods=["GET"])
def get_logs():
    """Return recent lines from the attack log file."""
    log_path = "logs/attacks.jsonl"
    if not os.path.exists(log_path):
        return success({"logs": [], "total": 0})

    with open(log_path) as f:
        lines = f.readlines()

    limit = min(int(request.args.get("limit", 50)), 200)
    recent = lines[-limit:]
    parsed = []
    for line in recent:
        try:
            parsed.append(json.loads(line.strip()))
        except Exception:
            pass

    return success({"logs": parsed, "total": len(lines)})


@app.route("/model/info", methods=["GET"])
def model_info():
    """Return model metadata."""
    if not model_server.loaded:
        return error("Model not loaded", 503)
    return success({
        "loaded":   True,
        "metadata": model_server.meta,
        "features": model_server.FEATURE_ORDER,
    })


@app.route("/simulate/benign", methods=["GET"])
def simulate_benign():
    """Generate a sample benign prediction for testing."""
    sample = {
        "file_write_count": 5, "file_rename_count": 0,
        "entropy_before": 4.2, "entropy_after": 4.3, "entropy_change": 0.1,
        "process_execution_time": 120.0, "api_call_frequency": 250,
        "file_access_rate": 0.1, "extension_change_count": 0,
        "encryption_indicator": 0.02,
        "rename_to_write_ratio": 0.0, "entropy_spike": 0.01,
        "aggression_score": 0.002, "ext_change_rate": 0.0,
    }
    return success({"sample": sample, "prediction": model_server.predict(sample)})


@app.route("/simulate/ransomware", methods=["GET"])
def simulate_ransomware():
    """Generate a sample ransomware prediction for testing."""
    sample = {
        "file_write_count": 2500, "file_rename_count": 2400,
        "entropy_before": 4.2, "entropy_after": 7.9, "entropy_change": 3.7,
        "process_execution_time": 15.0, "api_call_frequency": 25000,
        "file_access_rate": 80.0, "extension_change_count": 2000,
        "encryption_indicator": 0.95,
        "rename_to_write_ratio": 0.96, "entropy_spike": 0.46,
        "aggression_score": 76.0, "ext_change_rate": 133.3,
    }
    return success({"sample": sample, "prediction": model_server.predict(sample)})


# ─────────────────────────────────────────────────────────────
# ERROR HANDLERS
# ─────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return error("Endpoint not found", 404)

@app.errorhandler(500)
def server_error(e):
    return error(f"Internal server error: {e}", 500)


# ─────────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app._start_time = time.time()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
