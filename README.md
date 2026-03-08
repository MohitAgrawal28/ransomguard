<<<<<<< HEAD
# 🛡️ RansomGuard — Behavioral Ransomware Detection System

A complete, production-ready ransomware detection and prevention system using **LSTM deep learning** and real-time behavioral analysis.

---

## 📐 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    RANSOMGUARD ARCHITECTURE                       │
│                                                                   │
│  ┌──────────────┐    ┌────────────────┐    ┌─────────────────┐  │
│  │   DATASET     │    │  PREPROCESSING  │    │   LSTM MODEL    │  │
│  │  Generation   │───▶│  + Feature Eng  │───▶│  (TensorFlow)   │  │
│  │ (synthetic /  │    │  MinMaxScaler   │    │  Binary Classif │  │
│  │  real-world)  │    │  Train/Val/Test │    │  .h5 / SavedMod │  │
│  └──────────────┘    └────────────────┘    └────────┬────────┘  │
│                                                       │           │
│  ┌──────────────┐    ┌────────────────┐              │           │
│  │  FILE SYSTEM  │    │  BEHAVIORAL    │              │           │
│  │  (watchdog)   │───▶│  TRACKER       │──────────────┘           │
│  │  Monitors     │    │  Per-PID stats │    Real-time predict      │
│  │  ~/Documents  │    │  Entropy calc  │         │                │
│  └──────────────┘    └────────────────┘         │                │
│                                                   ▼               │
│  ┌──────────────┐    ┌────────────────┐    ┌─────────────────┐  │
│  │  PREVENTION   │    │   FLASK API    │    │  DETECTION      │  │
│  │  Kill Process │◀───│  /predict      │◀───│  ENGINE         │  │
│  │  Block writes │    │  /monitor      │    │  (detector.py)  │  │
│  │  Log event    │    │  /alert /logs  │    │  Threshold 0.70 │  │
│  └──────────────┘    └───────┬────────┘    └─────────────────┘  │
│                               │                                   │
│                       ┌───────▼────────┐                         │
│                       │  REACT FRONTEND │                         │
│                       │  Dashboard      │                         │
│                       │  Alerts         │                         │
│                       │  Predict form   │                         │
│                       │  Attack logs    │                         │
│                       └────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
ransomware_detection/
├── data/
│   ├── generate_dataset.py    # Phase 1: Dataset generation
│   └── preprocess.py          # Phase 2-3: Preprocessing + feature engineering
│
├── models/
│   ├── train_model.py         # Phase 4-5: LSTM training + export
│   ├── ransomware_lstm.h5     # Trained model (after training)
│   ├── ransomware_savedmodel/ # TF SavedModel format (after training)
│   ├── scaler.pkl             # MinMaxScaler (after training)
│   └── training_metadata.json # Training history
│
├── engine/
│   └── detector.py            # Phase 6-7: Real-time detection + prevention
│
├── backend/
│   └── app.py                 # Phase 8: Flask REST API
│
├── frontend/
│   └── src/
│       └── App.jsx            # Phase 9: React dashboard
│
├── tests/
│   └── ransomware_simulator.py # Phase 11: Safe testing simulator
│
├── logs/
│   ├── detection_engine.log   # Runtime logs
│   └── attacks.jsonl          # Attack events (JSON lines)
│
├── requirements.txt
└── README.md
```

---

## 🚀 Step-by-Step Deployment

### Prerequisites
- Python 3.9+
- Node.js 18+ (for React frontend)
- 4GB RAM minimum

---

### Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

### Step 2: Generate Dataset

```bash
cd ransomware_detection
python data/generate_dataset.py
```

This creates `dataset.csv` with 10,500 labeled behavioral samples:
- 5,000 benign samples
- 5,000 ransomware samples  
- 500 mixed/edge cases

---

### Step 3: Train the LSTM Model

```bash
python models/train_model.py
```

This will:
1. Load and preprocess `dataset.csv`
2. Train the LSTM model (50 epochs max, early stopping)
3. Print accuracy, precision, recall, F1, confusion matrix
4. Save model to `models/ransomware_lstm.h5`
5. Save scaler to `models/scaler.pkl`

**Expected results:**
```
Accuracy  : ~0.97+
F1 Score  : ~0.97+
ROC-AUC   : ~0.99+
```

---

### Step 4: Start the Backend API

```bash
python backend/app.py
```

API will be live at `http://localhost:5000`

Test it:
```bash
# Health check
curl http://localhost:5000/health

# Test ransomware prediction
curl http://localhost:5000/simulate/ransomware

# Test benign prediction
curl http://localhost:5000/simulate/benign
```

---

### Step 5: Start the Detection Engine

**In a separate terminal:**

```bash
python engine/detector.py
```

The engine will:
- Monitor `~/Documents` for file activity
- Analyze behavior every 2 seconds
- Kill suspicious processes automatically
- Send alerts to the Flask backend

---

### Step 6: Launch the React Frontend

```bash
cd frontend
npm create vite@latest . -- --template react
# Replace src/App.jsx with our App.jsx
npm install
npm run dev
```

Open `http://localhost:5173` to see the dashboard.

---

### Step 7: Run the Simulator Test

**In a separate terminal:**

```bash
# Test API directly (no file system needed)
python tests/ransomware_simulator.py --api-test

# Simulate ransomware file behavior
python tests/ransomware_simulator.py --dir /tmp/test --mode ransomware

# Run all modes
python tests/ransomware_simulator.py --dir /tmp/test --mode all
```

---

## 🔌 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Server liveness check |
| `/predict` | POST | Analyze behavioral snapshot |
| `/predict/batch` | POST | Batch analysis |
| `/monitor` | GET | Current engine status |
| `/alert` | POST | Receive detection alert |
| `/alerts` | GET | List stored alerts |
| `/logs` | GET | Recent attack log entries |
| `/model/info` | GET | Model metadata |
| `/simulate/benign` | GET | Test with benign sample |
| `/simulate/ransomware` | GET | Test with ransomware sample |

### POST /predict — Request Body

```json
{
  "file_write_count": 2500,
  "file_rename_count": 2400,
  "entropy_before": 4.2,
  "entropy_after": 7.9,
  "entropy_change": 3.7,
  "process_execution_time": 15.0,
  "api_call_frequency": 25000,
  "file_access_rate": 80.0,
  "extension_change_count": 2000,
  "encryption_indicator": 0.95
}
```

### Response

```json
{
  "success": true,
  "data": {
    "probability": 0.9873,
    "label": "ransomware",
    "confidence": 0.9873,
    "threshold": 0.5
  }
}
```

---

## 🔬 Key Technical Concepts

### Why Entropy Detects Ransomware

Shannon entropy measures randomness in data:
- Plain text: ~3-5 bits  (limited character set, repetitive patterns)
- Compressed: ~6-7 bits  (denser, less repetition)
- **Encrypted: ~7.5-8.0 bits** (looks like pure random noise)

When ransomware encrypts your files, entropy **jumps** from ~4 to ~7.8.
Our engine measures this jump in real time.

### Why LSTM for Detection

Ransomware is a **sequence of events** over time:
1. Recon (reading files slowly)
2. Encryption start (writes increase)  
3. Mass rename (extension changes)
4. Deletion of originals

LSTM remembers this temporal pattern. A single snapshot might look
suspicious, but the FULL SEQUENCE makes detection reliable.

### Detection Threshold

Default threshold: **0.70** (70% confidence)

- Higher threshold → fewer false positives, but might miss some ransomware
- Lower threshold → catches more ransomware, but more false alarms

Tune in `engine/detector.py` → `CONFIG["detection_threshold"]`

---

## ⚠️ Important Safety Notes

1. **Run in a VM or sandbox** when testing with the simulator
2. The detection engine requires **admin/root** to kill other processes
3. Never run actual ransomware samples on a real machine
4. The process killer has protection against killing system processes (PID < 100)
5. All detection events are logged to `logs/attacks.jsonl` for forensic review

---

## 📈 Improving the System

To improve detection accuracy for production use:

1. **Real dataset**: Replace synthetic data with MLRAN or VirusShare datasets
2. **Windowed LSTM**: Use `timesteps > 1` to feed a 10-second rolling window
3. **API hook**: Use Windows ETW or Linux eBPF to track actual API calls
4. **fanotify**: Use Linux kernel fanotify to block writes before they happen
5. **Federated learning**: Train across multiple machines without sharing data
=======
# ransomguard
>>>>>>> 48ed31cc50209fd3fdeb9dbcac4028cc7e64c986
