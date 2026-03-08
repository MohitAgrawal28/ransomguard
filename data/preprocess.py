"""
PHASE 2 — DATA PREPROCESSING
PHASE 3 — FEATURE ENGINEERING
================================

WHY EACH STEP MATTERS:
-----------------------
1. Remove duplicates     → Duplicate rows skew model training (model memorizes them)
2. Handle missing values → NaN causes errors in numpy/tensorflow math
3. Normalize features    → Features on different scales (0-5000 writes vs 0-8 entropy)
                           cause larger-magnitude features to dominate training
4. Encode labels         → ML models need numbers, not strings
5. Train/test split      → We evaluate on UNSEEN data to detect overfitting

ENTROPY EXPLANATION:
---------------------
Shannon entropy measures randomness/unpredictability in a byte stream.

  H(X) = -Σ p(x) * log2(p(x))

- Plain text:       entropy ≈ 3-5  (limited character set, repetitive)
- Compressed file:  entropy ≈ 6-7  (denser, less repetition)
- ENCRYPTED file:   entropy ≈ 7.5-8.0 (looks like pure random noise)

Ransomware turns low-entropy files into high-entropy encrypted blobs.
Detecting an entropy JUMP is one of the strongest ransomware signals.
"""

import numpy as np
import pandas as pd
import math
import hashlib
import os
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.utils import shuffle
import joblib
import warnings
warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────
# ENTROPY CALCULATION
# ─────────────────────────────────────────────────────────────

def calculate_byte_entropy(data: bytes) -> float:
    """
    Compute Shannon entropy of a byte sequence.
    
    Returns a value between 0.0 (all same bytes) and 8.0 (perfectly random).
    
    Example:
        with open("document.docx", "rb") as f:
            entropy = calculate_byte_entropy(f.read())
        # Normal .docx  → ~4.5
        # Encrypted     → ~7.9
    """
    if not data:
        return 0.0

    # Count frequency of each byte value (0-255)
    byte_counts = np.zeros(256, dtype=np.float64)
    for byte in data:
        byte_counts[byte] += 1

    # Convert to probabilities
    total = len(data)
    probabilities = byte_counts[byte_counts > 0] / total

    # Shannon entropy formula: H = -Σ p * log2(p)
    entropy = -np.sum(probabilities * np.log2(probabilities))
    return float(entropy)


def calculate_file_entropy(filepath: str) -> float:
    """Calculate entropy of a file on disk."""
    try:
        with open(filepath, "rb") as f:
            data = f.read()
        return calculate_byte_entropy(data)
    except (IOError, PermissionError) as e:
        print(f"  [WARN] Cannot read {filepath}: {e}")
        return 0.0


def entropy_category(entropy: float) -> str:
    """Human-readable entropy classification."""
    if entropy < 3.5:
        return "LOW (plaintext/structured)"
    elif entropy < 6.0:
        return "MEDIUM (compressed/mixed)"
    elif entropy < 7.0:
        return "HIGH (compressed/encrypted)"
    else:
        return "VERY HIGH (encrypted/random) ⚠️"


# ─────────────────────────────────────────────────────────────
# PREPROCESSING PIPELINE
# ─────────────────────────────────────────────────────────────

FEATURE_COLS = [
    "file_write_count",
    "file_rename_count",
    "entropy_before",
    "entropy_after",
    "entropy_change",
    "process_execution_time",
    "api_call_frequency",
    "file_access_rate",
    "extension_change_count",
    "encryption_indicator",
]
LABEL_COL = "label"


def load_and_clean(csv_path: str) -> pd.DataFrame:
    """
    Step 1-2: Load dataset, remove duplicates, handle missing values.
    """
    print(f"\n📂 Loading dataset: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"   Raw shape: {df.shape}")

    # Step 1: Remove duplicates
    before = len(df)
    df.drop_duplicates(inplace=True)
    print(f"   Removed {before - len(df)} duplicate rows")

    # Step 2: Handle missing values
    missing = df.isnull().sum().sum()
    if missing > 0:
        print(f"   Found {missing} missing values — filling with column median")
        df.fillna(df.median(numeric_only=True), inplace=True)
    else:
        print(f"   No missing values found ✓")

    # Clip obviously invalid values (negative entropy, etc.)
    for col in ["entropy_before", "entropy_after", "entropy_change"]:
        if col in df.columns:
            df[col] = df[col].clip(lower=0.0, upper=8.0)

    df["file_write_count"]  = df["file_write_count"].clip(lower=0)
    df["file_rename_count"] = df["file_rename_count"].clip(lower=0)
    df["api_call_frequency"] = df["api_call_frequency"].clip(lower=0)
    df["file_access_rate"]  = df["file_access_rate"].clip(lower=0)

    print(f"   Clean shape: {df.shape}")
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Step: Feature engineering — create derived behavioral signals.
    
    These new features amplify ransomware signals that might be subtle individually.
    """
    df = df.copy()

    # Rename ratio: high renames relative to writes = suspicious
    # (ransomware renames every file it encrypts)
    df["rename_to_write_ratio"] = (
        df["file_rename_count"] / (df["file_write_count"] + 1)
    ).clip(0, 100)

    # Entropy spike indicator: normalized entropy change (0-1 scale)
    df["entropy_spike"] = (df["entropy_change"] / 8.0).clip(0, 1)

    # Encryption aggressiveness: combines multiple signals
    df["aggression_score"] = (
        df["file_access_rate"] * df["encryption_indicator"]
    ).clip(0, 100)

    # Extension change rate: how many extensions changed per second
    df["ext_change_rate"] = (
        df["extension_change_count"] / (df["process_execution_time"] + 0.1)
    ).clip(0, 1000)

    print(f"   Engineered features added: rename_to_write_ratio, entropy_spike, "
          f"aggression_score, ext_change_rate")
    return df


def normalize_features(df: pd.DataFrame,
                        scaler_type: str = "minmax",
                        scaler_path: str = "models/scaler.pkl") -> tuple:
    """
    Step 3: Normalize features.
    
    MinMaxScaler: scales each feature to [0, 1]
    StandardScaler: mean=0, std=1 (better for LSTM)
    
    We SAVE the scaler so that at inference time we apply
    the SAME transformation (critical for correct predictions).
    """
    all_feature_cols = FEATURE_COLS + [
        "rename_to_write_ratio", "entropy_spike",
        "aggression_score", "ext_change_rate"
    ]
    # Keep only columns that exist
    feature_cols = [c for c in all_feature_cols if c in df.columns]

    X = df[feature_cols].values
    y = df[LABEL_COL].values.astype(int)

    if scaler_type == "standard":
        scaler = StandardScaler()
    else:
        scaler = MinMaxScaler()

    X_scaled = scaler.fit_transform(X)

    os.makedirs(os.path.dirname(scaler_path) if os.path.dirname(scaler_path) else ".", exist_ok=True)
    joblib.dump(scaler, scaler_path)
    print(f"   Scaler ({scaler_type}) saved → {scaler_path}")

    return X_scaled, y, scaler, feature_cols


def split_dataset(X, y, test_size=0.2, val_size=0.1):
    """
    Step 5: Split into train / validation / test.
    
    80% train → model learns patterns
    10% val   → tuning during training (early stopping)
    10% test  → final evaluation on unseen data
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size + val_size, random_state=42, stratify=y
    )
    # Split the remaining into val and test
    X_val, X_test, y_val, y_test = train_test_split(
        X_test, y_test, test_size=test_size/(test_size + val_size),
        random_state=42, stratify=y_test
    )

    print(f"\n📊 Dataset splits:")
    print(f"   Train : {X_train.shape[0]} samples")
    print(f"   Val   : {X_val.shape[0]} samples")
    print(f"   Test  : {X_test.shape[0]} samples")
    return X_train, X_val, X_test, y_train, y_val, y_test


def reshape_for_lstm(X, timesteps=1):
    """
    LSTM requires 3D input: (samples, timesteps, features)
    
    In a real-time scenario, timesteps > 1 would mean we feed
    a WINDOW of observations (e.g., last 10 monitoring snapshots).
    For this dataset, we use timesteps=1 as each row is one snapshot.
    """
    return X.reshape(X.shape[0], timesteps, X.shape[1])


def run_preprocessing(csv_path: str = "dataset.csv",
                       scaler_path: str = "models/scaler.pkl") -> dict:
    """Full preprocessing pipeline."""
    print("=" * 55)
    print("  RANSOMWARE DETECTION — PREPROCESSING PIPELINE")
    print("=" * 55)

    df = load_and_clean(csv_path)
    df = engineer_features(df)
    X, y, scaler, feature_cols = normalize_features(df, scaler_path=scaler_path)
    X_train, X_val, X_test, y_train, y_val, y_test = split_dataset(X, y)

    # Reshape for LSTM
    X_train_3d = reshape_for_lstm(X_train)
    X_val_3d   = reshape_for_lstm(X_val)
    X_test_3d  = reshape_for_lstm(X_test)

    print(f"\n   LSTM input shape: {X_train_3d.shape}")
    print(f"   Features used   : {feature_cols}")
    print(f"\n✅ Preprocessing complete!")

    return {
        "X_train": X_train_3d, "X_val": X_val_3d, "X_test": X_test_3d,
        "y_train": y_train, "y_val": y_val, "y_test": y_test,
        "scaler": scaler, "feature_cols": feature_cols,
        "n_features": X_train_3d.shape[2],
    }


if __name__ == "__main__":
    # Demo entropy calculation
    print("── Entropy Examples ──")
    test_cases = [
        b"Hello World" * 100,            # Low entropy text
        bytes(range(256)) * 10,          # All possible bytes
        bytes(np.random.randint(0, 256, 1000, dtype=np.uint8)),  # Random (encrypted)
    ]
    labels = ["Plaintext", "Structured binary", "Random/encrypted"]
    for data, label in zip(test_cases, labels):
        e = calculate_byte_entropy(data)
        print(f"  {label:25s}  entropy = {e:.4f}  ({entropy_category(e)})")

    print()
    result = run_preprocessing("dataset.csv")
