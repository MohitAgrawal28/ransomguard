"""
PHASE 1 — DATASET GENERATION
=============================
This script generates a synthetic ransomware behavioral dataset.

In a real-world scenario, you would use:
- MLRAN dataset: https://mlran.com
- Kaggle ransomware behavioral datasets

Ransomware BEHAVES differently from benign programs:
- It writes/renames many files rapidly (e.g., encrypting "document.docx" → "document.docx.locked")
- File entropy INCREASES (encrypted data looks random = high entropy)
- Unusual API calls for encryption libraries
- High CPU/disk I/O in short time windows

We simulate this statistically using known behavioral profiles.
"""

import numpy as np
import pandas as pd
from sklearn.utils import shuffle
import os

# ─────────────────────────────────────────────
# SEED for reproducibility
# ─────────────────────────────────────────────
np.random.seed(42)

def generate_benign_samples(n=5000):
    """
    Benign programs (normal apps, browsers, editors):
    - Low file write counts
    - Rare renames
    - Moderate entropy (text files, images)
    - Normal API call rates
    """
    data = {
        "file_write_count":        np.random.randint(0, 20, n),
        "file_rename_count":       np.random.randint(0, 3, n),
        "entropy_before":          np.random.uniform(2.0, 5.5, n),   # normal files
        "entropy_after":           np.random.uniform(2.0, 5.5, n),   # unchanged
        "entropy_change":          np.random.uniform(-0.3, 0.3, n),  # tiny change
        "process_execution_time":  np.random.uniform(0.1, 300.0, n), # seconds
        "api_call_frequency":      np.random.randint(10, 500, n),
        "file_access_rate":        np.random.uniform(0.01, 2.0, n),  # files/sec
        "extension_change_count":  np.random.randint(0, 1, n),
        "encryption_indicator":    np.random.uniform(0.0, 0.15, n),  # low
        "label": np.zeros(n, dtype=int)
    }
    return pd.DataFrame(data)


def generate_ransomware_samples(n=5000):
    """
    Ransomware (WannaCry, Ryuk, Locky behavioral profiles):
    - HIGH file write + rename counts (bulk encryption)
    - Entropy JUMPS to near 8.0 (encrypted = high entropy)
    - Rapid file access rate
    - Extension changes (e.g., .docx → .docx.WNCRY)
    - Encryption API calls detected
    """
    data = {
        "file_write_count":        np.random.randint(100, 5000, n),  # bulk writes
        "file_rename_count":       np.random.randint(50, 3000, n),   # bulk renames
        "entropy_before":          np.random.uniform(2.0, 5.5, n),   # normal before
        "entropy_after":           np.random.uniform(7.0, 8.0, n),   # HIGH after encryption
        "entropy_change":          np.random.uniform(2.0, 6.0, n),   # large jump
        "process_execution_time":  np.random.uniform(0.5, 120.0, n), # fast execution
        "api_call_frequency":      np.random.randint(1000, 50000, n),# many crypto APIs
        "file_access_rate":        np.random.uniform(5.0, 100.0, n), # rapid access
        "extension_change_count":  np.random.randint(20, 2000, n),   # mass rename
        "encryption_indicator":    np.random.uniform(0.7, 1.0, n),   # high
        "label": np.ones(n, dtype=int)
    }
    return pd.DataFrame(data)


def generate_mixed_samples(n=500):
    """
    Edge cases: partial encryption, slow ransomware, false positives
    These make the model more robust.
    """
    data = {
        "file_write_count":        np.random.randint(10, 200, n),
        "file_rename_count":       np.random.randint(5, 100, n),
        "entropy_before":          np.random.uniform(3.0, 6.5, n),
        "entropy_after":           np.random.uniform(4.0, 7.5, n),
        "entropy_change":          np.random.uniform(0.5, 3.0, n),
        "process_execution_time":  np.random.uniform(1.0, 600.0, n),
        "api_call_frequency":      np.random.randint(200, 5000, n),
        "file_access_rate":        np.random.uniform(1.0, 20.0, n),
        "extension_change_count":  np.random.randint(1, 50, n),
        "encryption_indicator":    np.random.uniform(0.3, 0.7, n),
        # Label based on a heuristic threshold
        "label": (np.random.uniform(0, 1, n) > 0.5).astype(int)
    }
    return pd.DataFrame(data)


def build_dataset(output_path="dataset.csv"):
    print("🔧 Generating synthetic ransomware behavioral dataset...")

    benign     = generate_benign_samples(5000)
    ransomware = generate_ransomware_samples(5000)
    mixed      = generate_mixed_samples(500)

    df = pd.concat([benign, ransomware, mixed], ignore_index=True)
    df = shuffle(df, random_state=42).reset_index(drop=True)

    # Add small amount of noise to make it realistic
    numeric_cols = [c for c in df.columns if c != "label"]
    noise = np.random.normal(0, 0.01, df[numeric_cols].shape)
    df[numeric_cols] = df[numeric_cols] + noise
    df[numeric_cols] = df[numeric_cols].clip(lower=0)

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"✅ Dataset saved → {output_path}")
    print(f"   Total samples : {len(df)}")
    print(f"   Benign        : {(df['label']==0).sum()}")
    print(f"   Ransomware    : {(df['label']==1).sum()}")
    print(f"   Features      : {df.columns.tolist()}")
    return df


if __name__ == "__main__":
    df = build_dataset("dataset.csv")
    print("\nSample rows:")
    print(df.head(5).to_string())
