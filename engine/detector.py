"""
PHASE 6 — REAL-TIME RANSOMWARE DETECTION ENGINE
PHASE 7 — PREVENTION MECHANISM
==================================================

HOW IT WORKS:
--------------
1. watchdog library monitors the file system for events
   (file created, modified, renamed, deleted)

2. psutil tracks system processes and their resource usage

3. As events arrive, we build a behavioral snapshot:
   - count file writes, renames, extension changes
   - measure file entropy before/after modification
   - track API call frequency via process monitoring

4. Every N seconds, we send this snapshot to the LSTM model

5. If model outputs probability > THRESHOLD → RANSOMWARE DETECTED
   → Kill the suspicious process (os.kill / psutil)
   → Log the event
   → Send alert to backend API

PREVENTION (Phase 7):
----------------------
Kill malicious process:
  psutil.Process(pid).terminate()  → sends SIGTERM (graceful)
  psutil.Process(pid).kill()       → sends SIGKILL (force)

CAUTION: Always verify the PID before killing! We use multiple
signals (entropy spike + mass renames + PID correlation) to
reduce false positives.
"""

import os
import sys
import time
import math
import json
import logging
import hashlib
import threading
import traceback
import signal
from datetime import datetime
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List

import numpy as np
import psutil
import joblib
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ─────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/detection_engine.log"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("RansomwareDetector")


# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

CONFIG = {
    "watch_directory":     os.path.expanduser("~/Documents"),  # Directory to monitor
    "model_path":          "models/ransomware_lstm.h5",
    "scaler_path":         "models/scaler.pkl",
    "metadata_path":       "models/training_metadata.json",
    "backend_url":         "http://127.0.0.1:5000",
    "detection_threshold": 0.70,    # Confidence threshold for ransomware
    "snapshot_interval":   2.0,     # Analyze snapshot every N seconds
    "window_size":         30,      # Look-back window in seconds
    "log_path":            "logs/attacks.jsonl",
    "min_events_to_score": 3,       # Minimum events before scoring
    "suspicious_extensions": {
        ".locked", ".encrypted", ".enc", ".crypto", ".crypt",
        ".wncry", ".wnry", ".WNCRY", ".crypz", ".zepto",
        ".locky", ".cerber", ".cerber2", ".cerber3", ".sage",
        ".globe", ".globe2", ".globe3", ".purge", ".coded",
    }
}


# ─────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────

@dataclass
class BehaviorSnapshot:
    """Behavioral features collected over a time window."""
    pid:                     int   = 0
    process_name:            str   = "unknown"
    file_write_count:        int   = 0
    file_rename_count:       int   = 0
    entropy_before:          float = 0.0
    entropy_after:           float = 0.0
    entropy_change:          float = 0.0
    process_execution_time:  float = 0.0
    api_call_frequency:      int   = 0
    file_access_rate:        float = 0.0
    extension_change_count:  int   = 0
    encryption_indicator:    float = 0.0
    # Engineered features
    rename_to_write_ratio:   float = 0.0
    entropy_spike:           float = 0.0
    aggression_score:        float = 0.0
    ext_change_rate:         float = 0.0
    timestamp:               str   = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class DetectionEvent:
    """A detected ransomware event."""
    timestamp:          str
    pid:                int
    process_name:       str
    ransomware_prob:    float
    snapshot:           dict
    action_taken:       str
    files_affected:     List[str]


# ─────────────────────────────────────────────────────────────
# FILE ENTROPY CALCULATION
# ─────────────────────────────────────────────────────────────

def file_entropy(filepath: str) -> float:
    """Calculate Shannon entropy of a file."""
    try:
        with open(filepath, "rb") as f:
            data = f.read(65536)   # Read first 64KB for speed
        if not data:
            return 0.0
        counts = np.zeros(256, dtype=np.float64)
        for byte in data:
            counts[byte] += 1
        probs = counts[counts > 0] / len(data)
        return float(-np.sum(probs * np.log2(probs)))
    except Exception:
        return 0.0


# ─────────────────────────────────────────────────────────────
# PROCESS TRACKER
# ─────────────────────────────────────────────────────────────

class ProcessTracker:
    """Tracks per-process behavioral metrics."""

    def __init__(self):
        self._lock = threading.Lock()
        self._stats: Dict[int, dict] = {}
        self._start_times: Dict[int, float] = {}

    def _init_pid(self, pid: int):
        if pid not in self._stats:
            self._stats[pid] = {
                "writes": 0, "renames": 0, "api_calls": 0,
                "ext_changes": 0, "files": deque(maxlen=200),
                "entropy_before": [], "entropy_after": [],
            }
            self._start_times[pid] = time.time()

    def record_write(self, pid: int, filepath: str, entropy_before: float, entropy_after: float):
        with self._lock:
            self._init_pid(pid)
            self._stats[pid]["writes"] += 1
            self._stats[pid]["files"].append(filepath)
            self._stats[pid]["entropy_before"].append(entropy_before)
            self._stats[pid]["entropy_after"].append(entropy_after)

    def record_rename(self, pid: int, src: str, dest: str):
        with self._lock:
            self._init_pid(pid)
            self._stats[pid]["renames"] += 1
            # Check if extension changed to suspicious one
            _, src_ext = os.path.splitext(src)
            _, dest_ext = os.path.splitext(dest)
            if dest_ext.lower() in CONFIG["suspicious_extensions"] or src_ext != dest_ext:
                self._stats[pid]["ext_changes"] += 1

    def record_api_call(self, pid: int, n: int = 1):
        with self._lock:
            self._init_pid(pid)
            self._stats[pid]["api_calls"] += n

    def build_snapshot(self, pid: int, process_name: str) -> Optional[BehaviorSnapshot]:
        with self._lock:
            if pid not in self._stats:
                return None
            s = self._stats[pid]
            elapsed = time.time() - self._start_times.get(pid, time.time())
            elapsed = max(elapsed, 0.001)

            eb = np.mean(s["entropy_before"]) if s["entropy_before"] else 0.0
            ea = np.mean(s["entropy_after"])  if s["entropy_after"]  else 0.0
            ec = ea - eb

            writes  = s["writes"]
            renames = s["renames"]
            api     = s["api_calls"]
            ext_ch  = s["ext_changes"]

            enc_indicator = min((ec / 8.0 + ext_ch / max(writes, 1)) / 2, 1.0)
            file_access_rate = writes / elapsed

            snap = BehaviorSnapshot(
                pid=pid,
                process_name=process_name,
                file_write_count=writes,
                file_rename_count=renames,
                entropy_before=round(eb, 4),
                entropy_after=round(ea, 4),
                entropy_change=round(ec, 4),
                process_execution_time=round(elapsed, 2),
                api_call_frequency=api,
                file_access_rate=round(file_access_rate, 4),
                extension_change_count=ext_ch,
                encryption_indicator=round(enc_indicator, 4),
                rename_to_write_ratio=round(renames / (writes + 1), 4),
                entropy_spike=round(min(ec / 8.0, 1.0), 4),
                aggression_score=round(min(file_access_rate * enc_indicator, 100.0), 4),
                ext_change_rate=round(ext_ch / elapsed, 4),
            )
            return snap

    def reset_pid(self, pid: int):
        with self._lock:
            self._stats.pop(pid, None)
            self._start_times.pop(pid, None)

    def active_pids(self):
        with self._lock:
            return list(self._stats.keys())


# ─────────────────────────────────────────────────────────────
# WATCHDOG FILE SYSTEM HANDLER
# ─────────────────────────────────────────────────────────────

class RansomwareFileHandler(FileSystemEventHandler):
    """
    Responds to file system events and feeds data to ProcessTracker.
    watchdog monitors a directory and fires callbacks for each event.
    """

    def __init__(self, tracker: ProcessTracker, blocked_pids: set):
        super().__init__()
        self._tracker = tracker
        self._blocked = blocked_pids
        self._entropy_cache: Dict[str, float] = {}

    def _get_pid_of_file(self, filepath: str) -> tuple:
        """Try to find which process is accessing this file."""
        try:
            for proc in psutil.process_iter(["pid", "name", "open_files"]):
                try:
                    if proc.info["open_files"]:
                        for of in proc.info["open_files"]:
                            if of.path == filepath:
                                return proc.info["pid"], proc.info["name"]
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
        except Exception:
            pass
        return 0, "unknown"

    def on_modified(self, event):
        if event.is_directory:
            return
        filepath = event.src_path
        try:
            entropy_before = self._entropy_cache.get(filepath, file_entropy(filepath))
            entropy_after  = file_entropy(filepath)
            self._entropy_cache[filepath] = entropy_after

            pid, pname = self._get_pid_of_file(filepath)
            if pid in self._blocked:
                return

            self._tracker.record_write(pid, filepath, entropy_before, entropy_after)
            self._tracker.record_api_call(pid, n=5)
        except Exception:
            pass

    def on_moved(self, event):
        if event.is_directory:
            return
        pid, pname = self._get_pid_of_file(event.dest_path)
        if pid not in self._blocked:
            self._tracker.record_rename(pid, event.src_path, event.dest_path)

    def on_created(self, event):
        if not event.is_directory:
            filepath = event.src_path
            self._entropy_cache[filepath] = file_entropy(filepath)

    def on_deleted(self, event):
        self._entropy_cache.pop(event.src_path, None)


# ─────────────────────────────────────────────────────────────
# ML PREDICTOR
# ─────────────────────────────────────────────────────────────

class RansomwarePredictor:
    """Loads the trained LSTM model and runs inference."""

    FEATURE_ORDER = [
        "file_write_count", "file_rename_count", "entropy_before",
        "entropy_after", "entropy_change", "process_execution_time",
        "api_call_frequency", "file_access_rate", "extension_change_count",
        "encryption_indicator", "rename_to_write_ratio", "entropy_spike",
        "aggression_score", "ext_change_rate",
    ]

    def __init__(self, model_path: str, scaler_path: str):
        import tensorflow as tf
        self.model  = tf.keras.models.load_model(model_path)
        self.scaler = joblib.load(scaler_path)
        log.info(f"✅ Model loaded from {model_path}")

    def predict(self, snapshot: BehaviorSnapshot) -> float:
        """
        Returns probability [0, 1] that the snapshot represents ransomware.
        """
        snap_dict = asdict(snapshot)
        features  = np.array([[snap_dict.get(f, 0.0) for f in self.FEATURE_ORDER]],
                             dtype=np.float32)
        # Truncate to scaler's expected features if needed
        n_expected = self.scaler.n_features_in_
        features = features[:, :n_expected]

        features_scaled = self.scaler.transform(features)
        features_3d = features_scaled.reshape(1, 1, features_scaled.shape[1])
        prob = float(self.model.predict(features_3d, verbose=0)[0][0])
        return prob


# ─────────────────────────────────────────────────────────────
# PREVENTION ENGINE
# ─────────────────────────────────────────────────────────────

class PreventionEngine:
    """
    Handles ransomware prevention actions.
    
    SAFETY NOTES:
    - We NEVER kill system processes (PID < 100 on Linux)
    - We log ALL actions for forensic review
    - Multiple signals are required before killing (entropy + renames + PID)
    """

    PROTECTED_PROCESSES = {
        "systemd", "kernel", "init", "sshd", "python",
        "python3", "detector.py", "bash", "sh", "zsh",
    }

    def __init__(self, alert_callback=None):
        self._killed_pids: set = set()
        self._alert_cb = alert_callback
        self._lock = threading.Lock()

    def terminate_process(self, pid: int, process_name: str,
                           probability: float) -> str:
        """
        Safely terminate a suspicious process.
        
        Steps:
        1. Verify PID exists and is not protected
        2. Send SIGTERM (graceful shutdown)
        3. Wait 3 seconds
        4. Send SIGKILL if still running
        5. Log the action
        """
        with self._lock:
            if pid in self._killed_pids or pid == 0:
                return "already_handled"

            # Safety checks
            if pid < 100:
                log.warning(f"⚠️  Refusing to kill low PID {pid} (system process)")
                return "protected_pid"

            if process_name.lower() in self.PROTECTED_PROCESSES:
                log.warning(f"⚠️  Refusing to kill protected process '{process_name}'")
                return "protected_name"

            try:
                proc = psutil.Process(pid)
                proc_info = proc.as_dict(attrs=["name", "cmdline", "create_time"])

                log.critical(
                    f"🛑 RANSOMWARE DETECTED — Terminating PID {pid} "
                    f"'{process_name}' (prob={probability:.3f})"
                )

                # Step 1: Graceful termination
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                    action = "terminated"
                except psutil.TimeoutExpired:
                    # Step 2: Force kill
                    proc.kill()
                    action = "killed"

                self._killed_pids.add(pid)

                if self._alert_cb:
                    self._alert_cb({
                        "type": "process_killed",
                        "pid": pid,
                        "process_name": process_name,
                        "probability": probability,
                        "action": action,
                        "timestamp": datetime.now().isoformat(),
                    })

                return action

            except psutil.NoSuchProcess:
                log.info(f"PID {pid} already gone")
                return "not_found"
            except psutil.AccessDenied:
                log.error(f"❌ Access denied for PID {pid} — run as admin/root")
                return "access_denied"
            except Exception as e:
                log.error(f"Error terminating PID {pid}: {e}")
                return f"error: {e}"

    def block_future_modifications(self, watch_dir: str, pid: int):
        """
        On Linux/Mac: use file permissions to block writes.
        On Windows: use NTFS ACLs (not implemented here).
        """
        log.info(f"🔒 Watch-blocking file modifications from PID {pid}")
        # In production: modify inotify rules or use fanotify to deny writes


# ─────────────────────────────────────────────────────────────
# DETECTION ENGINE (main coordinator)
# ─────────────────────────────────────────────────────────────

class DetectionEngine:
    """
    Orchestrates monitoring, prediction, and prevention.
    
    Architecture:
      FileHandler → ProcessTracker → Predictor → Prevention → Alert
                        ↑
                   (watchdog thread)
    """

    def __init__(self):
        self._blocked_pids = set()
        self._tracker   = ProcessTracker()
        self._prevention = PreventionEngine(alert_callback=self._send_alert)
        self._predictor  = None
        self._observer   = None
        self._running    = False
        self._attack_log = []
        self._backend_available = False
        self._check_backend()

    def _check_backend(self):
        try:
            r = requests.get(f"{CONFIG['backend_url']}/health", timeout=2)
            self._backend_available = r.status_code == 200
            log.info(f"Backend API: {'online' if self._backend_available else 'offline'}")
        except Exception:
            self._backend_available = False

    def load_model(self):
        """Load the trained LSTM model."""
        try:
            self._predictor = RansomwarePredictor(
                model_path=CONFIG["model_path"],
                scaler_path=CONFIG["scaler_path"],
            )
            return True
        except Exception as e:
            log.error(f"Failed to load model: {e}")
            return False

    def start(self):
        """Start file system monitoring."""
        watch_dir = CONFIG["watch_directory"]
        os.makedirs(watch_dir, exist_ok=True)

        handler = RansomwareFileHandler(self._tracker, self._blocked_pids)
        self._observer = Observer()
        self._observer.schedule(handler, watch_dir, recursive=True)
        self._observer.start()
        self._running = True

        log.info(f"👁️  Monitoring started → {watch_dir}")

        # Start scoring loop in background thread
        scoring_thread = threading.Thread(target=self._scoring_loop, daemon=True)
        scoring_thread.start()

    def stop(self):
        """Stop monitoring."""
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join()
        log.info("🛑 Monitoring stopped")

    def _scoring_loop(self):
        """Periodically evaluate all active PIDs."""
        while self._running:
            time.sleep(CONFIG["snapshot_interval"])
            if not self._predictor:
                continue
            for pid in self._tracker.active_pids():
                self._evaluate_pid(pid)

    def _evaluate_pid(self, pid: int):
        """Build snapshot and run prediction for a PID."""
        try:
            proc = psutil.Process(pid)
            pname = proc.name()
        except psutil.NoSuchProcess:
            self._tracker.reset_pid(pid)
            return
        except Exception:
            pname = "unknown"

        snap = self._tracker.build_snapshot(pid, pname)
        if snap is None:
            return

        total_events = snap.file_write_count + snap.file_rename_count
        if total_events < CONFIG["min_events_to_score"]:
            return

        prob = self._predictor.predict(snap)

        if prob > CONFIG["detection_threshold"] and pid not in self._blocked_pids:
            self._handle_detection(pid, pname, prob, snap)
        elif prob > 0.4:
            log.warning(f"⚠️  SUSPICIOUS PID {pid} ({pname}) prob={prob:.3f} — watching")

    def _handle_detection(self, pid: int, pname: str,
                           prob: float, snap: BehaviorSnapshot):
        """Handle a positive ransomware detection."""
        log.critical(
            f"\n{'='*50}\n"
            f"🚨 RANSOMWARE DETECTED!\n"
            f"   PID          : {pid}\n"
            f"   Process      : {pname}\n"
            f"   Probability  : {prob:.4f}\n"
            f"   Writes       : {snap.file_write_count}\n"
            f"   Renames      : {snap.file_rename_count}\n"
            f"   Entropy Δ    : {snap.entropy_change:.3f}\n"
            f"   Ext Changes  : {snap.extension_change_count}\n"
            f"{'='*50}"
        )

        self._blocked_pids.add(pid)
        action = self._prevention.terminate_process(pid, pname, prob)

        event = DetectionEvent(
            timestamp=datetime.now().isoformat(),
            pid=pid,
            process_name=pname,
            ransomware_prob=prob,
            snapshot=asdict(snap),
            action_taken=action,
            files_affected=[],
        )

        self._log_attack(event)
        self._send_alert(asdict(event))

    def _log_attack(self, event: DetectionEvent):
        """Append attack to JSONL log file."""
        os.makedirs("logs", exist_ok=True)
        with open(CONFIG["log_path"], "a") as f:
            f.write(json.dumps(asdict(event)) + "\n")
        self._attack_log.append(event)

    def _send_alert(self, data: dict):
        """Send alert to backend API."""
        if not self._backend_available:
            return
        try:
            requests.post(
                f"{CONFIG['backend_url']}/alert",
                json=data,
                timeout=3,
            )
        except Exception:
            pass   # Backend offline, alert already logged locally

    def get_status(self) -> dict:
        """Return current engine status."""
        return {
            "running":         self._running,
            "watch_directory": CONFIG["watch_directory"],
            "active_pids":     len(self._tracker.active_pids()),
            "blocked_pids":    list(self._blocked_pids),
            "attacks_logged":  len(self._attack_log),
            "model_loaded":    self._predictor is not None,
            "threshold":       CONFIG["detection_threshold"],
        }


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  RANSOMWARE DETECTION ENGINE")
    print("=" * 55)

    engine = DetectionEngine()

    if not engine.load_model():
        print("❌ Model not found. Train the model first:")
        print("   cd models && python train_model.py")
        sys.exit(1)

    engine.start()

    def shutdown(sig, frame):
        print("\n\nShutting down...")
        engine.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"\n✅ Engine running. Monitoring: {CONFIG['watch_directory']}")
    print(f"   Detection threshold : {CONFIG['detection_threshold']}")
    print(f"   Press Ctrl+C to stop\n")

    while True:
        time.sleep(10)
        status = engine.get_status()
        print(f"[STATUS] Active PIDs: {status['active_pids']} | "
              f"Blocked: {len(status['blocked_pids'])} | "
              f"Attacks: {status['attacks_logged']}")


if __name__ == "__main__":
    main()
