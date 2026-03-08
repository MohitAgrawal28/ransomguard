"""
PHASE 4 — MODEL DEVELOPMENT
PHASE 5 — MODEL EXPORT
=================================

WHY LSTM?
----------
Ransomware doesn't happen in a single instant. It unfolds over TIME:
  1. Process starts
  2. Begins reading files
  3. Starts writing encrypted versions
  4. Renames files with new extension
  5. Deletes originals

LSTM (Long Short-Term Memory) is a type of Recurrent Neural Network (RNN)
that remembers SEQUENCES. It can learn: "if I see pattern A, then B, then C
rapidly → that's ransomware."

MODEL ARCHITECTURE:
--------------------
Input (n_features) 
  → LSTM Layer 1 (128 units, return_sequences=True)
  → Dropout (0.3)                          # Prevents overfitting
  → LSTM Layer 2 (64 units)
  → Dropout (0.3)
  → Dense Layer (32 units, ReLU)           # Pattern recognition
  → BatchNormalization
  → Dense Output (1 unit, Sigmoid)         # Probability of ransomware [0-1]

Loss: Binary Crossentropy (standard for binary classification)
Optimizer: Adam (adaptive learning rate, best general-purpose optimizer)
"""

import numpy as np
import os
import sys
import json

# TensorFlow / Keras
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import (
    LSTM, Dense, Dropout, BatchNormalization, Input
)
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import (
    EarlyStopping, ModelCheckpoint, ReduceLROnPlateau, TensorBoard
)
from tensorflow.keras.regularizers import l2

# Evaluation metrics
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score, roc_curve,
    precision_recall_curve, f1_score, accuracy_score
)

import warnings
warnings.filterwarnings("ignore")

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.preprocess import run_preprocessing


# ─────────────────────────────────────────────────────────────
# MODEL DEFINITION
# ─────────────────────────────────────────────────────────────

def build_lstm_model(n_features: int, timesteps: int = 1,
                     lstm_units_1: int = 128, lstm_units_2: int = 64,
                     dense_units: int = 32, dropout_rate: float = 0.3,
                     learning_rate: float = 0.001) -> tf.keras.Model:
    """
    Builds the LSTM ransomware detection model.
    
    Parameters:
        n_features    : number of behavioral features
        timesteps     : sequence length (1 for snapshot mode, >1 for windowed mode)
        lstm_units_*  : LSTM cell count (more = captures more complex patterns)
        dense_units   : neurons in fully-connected layer
        dropout_rate  : fraction of neurons dropped during training (regularization)
        learning_rate : how fast the model adjusts weights
    """
    model = Sequential([
        # Input shape: (batch, timesteps, features)
        Input(shape=(timesteps, n_features)),

        # ── LSTM LAYER 1 ──────────────────────────────────────
        # return_sequences=True → passes sequence to next LSTM
        LSTM(lstm_units_1,
             return_sequences=True,
             kernel_regularizer=l2(1e-4),
             recurrent_regularizer=l2(1e-4),
             name="lstm_1"),
        Dropout(dropout_rate, name="dropout_1"),

        # ── LSTM LAYER 2 ──────────────────────────────────────
        # return_sequences=False → outputs single vector
        LSTM(lstm_units_2,
             return_sequences=False,
             kernel_regularizer=l2(1e-4),
             name="lstm_2"),
        Dropout(dropout_rate, name="dropout_2"),

        # ── DENSE LAYERS ──────────────────────────────────────
        Dense(dense_units, activation="relu",
              kernel_regularizer=l2(1e-4), name="dense_1"),
        BatchNormalization(name="bn_1"),
        Dropout(dropout_rate / 2, name="dropout_3"),

        # ── OUTPUT LAYER ──────────────────────────────────────
        # Sigmoid: outputs probability [0, 1]
        # > 0.5 → ransomware, <= 0.5 → benign
        Dense(1, activation="sigmoid", name="output"),
    ])

    optimizer = Adam(learning_rate=learning_rate)

    model.compile(
        optimizer=optimizer,
        loss="binary_crossentropy",        # Best for binary yes/no classification
        metrics=[
            "accuracy",
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
            tf.keras.metrics.AUC(name="auc"),
        ]
    )
    return model


# ─────────────────────────────────────────────────────────────
# TRAINING
# ─────────────────────────────────────────────────────────────

def train_model(model, X_train, y_train, X_val, y_val,
                epochs=50, batch_size=64,
                checkpoint_path="models/best_model.keras") -> tf.keras.callbacks.History:
    """
    Train the LSTM model with callbacks for:
    - EarlyStopping: Stop when val_loss stops improving (prevents overfitting)
    - ModelCheckpoint: Save the best model weights automatically
    - ReduceLROnPlateau: Lower learning rate when stuck (helps escape local minima)
    """
    os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)

    callbacks = [
        EarlyStopping(
            monitor="val_loss",
            patience=8,            # Stop if no improvement for 8 epochs
            restore_best_weights=True,
            verbose=1
        ),
        ModelCheckpoint(
            filepath=checkpoint_path,
            monitor="val_loss",
            save_best_only=True,
            verbose=1
        ),
        ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,            # Halve learning rate
            patience=4,
            min_lr=1e-6,
            verbose=1
        ),
    ]

    # Class weights: in ransomware datasets, false negatives are VERY costly
    # (missing ransomware = data loss). We penalize missed ransomware more.
    class_weight = {0: 1.0, 1: 1.5}

    print(f"\n🚀 Starting training (max {epochs} epochs, batch={batch_size})")
    print(f"   Train samples : {len(X_train)}")
    print(f"   Val samples   : {len(X_val)}")

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        class_weight=class_weight,
        verbose=1,
    )
    return history


# ─────────────────────────────────────────────────────────────
# EVALUATION
# ─────────────────────────────────────────────────────────────

def evaluate_model(model, X_test, y_test, threshold: float = 0.5) -> dict:
    """
    Comprehensive model evaluation.
    
    Key metrics:
    - Accuracy    : overall correct predictions
    - Precision   : of predicted ransomware, how many are actually ransomware?
                    (Low precision = many false alarms)
    - Recall      : of actual ransomware, how many did we catch?
                    (Low recall = missed ransomware — DANGEROUS)
    - F1 Score    : harmonic mean of precision and recall
    - ROC-AUC     : area under ROC curve (1.0 = perfect, 0.5 = random)
    
    For ransomware detection, RECALL is most critical.
    We prefer to flag a benign app (false alarm) over missing ransomware.
    """
    print("\n" + "=" * 50)
    print("  MODEL EVALUATION")
    print("=" * 50)

    y_prob = model.predict(X_test, verbose=0).flatten()
    y_pred = (y_prob >= threshold).astype(int)

    acc       = accuracy_score(y_test, y_pred)
    f1        = f1_score(y_test, y_pred)
    roc_auc   = roc_auc_score(y_test, y_prob)
    cm        = confusion_matrix(y_test, y_pred)
    report    = classification_report(y_test, y_pred,
                                      target_names=["Benign", "Ransomware"])

    print(f"\n  Threshold   : {threshold}")
    print(f"  Accuracy    : {acc:.4f}")
    print(f"  F1 Score    : {f1:.4f}")
    print(f"  ROC-AUC     : {roc_auc:.4f}")
    print(f"\n  Classification Report:")
    print(report)
    print(f"\n  Confusion Matrix:")
    print(f"                Predicted Benign  Predicted Ransomware")
    print(f"  Actual Benign     {cm[0,0]:>6}              {cm[0,1]:>6}")
    print(f"  Actual Ransom     {cm[1,0]:>6}              {cm[1,1]:>6}")
    print(f"\n  True Negatives  (correctly benign)   : {cm[0,0]}")
    print(f"  False Positives (false alarms)        : {cm[0,1]}")
    print(f"  False Negatives (MISSED ransomware!)  : {cm[1,0]} ← minimize this!")
    print(f"  True Positives  (caught ransomware)   : {cm[1,1]}")

    return {
        "accuracy": float(acc), "f1": float(f1), "roc_auc": float(roc_auc),
        "confusion_matrix": cm.tolist(), "threshold": threshold,
        "y_prob": y_prob, "y_pred": y_pred,
    }


# ─────────────────────────────────────────────────────────────
# PHASE 5 — MODEL EXPORT
# ─────────────────────────────────────────────────────────────

def save_model(model, path_h5="models/ransomware_lstm.h5",
               path_savedmodel="models/ransomware_savedmodel"):
    """
    Save the model in two formats:
    
    .h5 format:
        - Single file, easy to share
        - Load with: model = load_model('ransomware_lstm.h5')
    
    SavedModel format:
        - TensorFlow's native format
        - Deployable to TF Serving, TFLite, TF.js
        - Better for production APIs
    """
    os.makedirs(os.path.dirname(path_h5), exist_ok=True)

    model.save(path_h5)
    print(f"\n💾 Model saved (H5)         → {path_h5}")

    model.save(path_savedmodel + ".keras")
    print(f"💾 Model saved (SavedModel) → {path_savedmodel}")


def load_model_from_disk(path="models/ransomware_lstm.h5"):
    """Load trained model for inference."""
    model = load_model(path)
    print(f"✅ Model loaded from {path}")
    return model


def save_training_metadata(history, eval_results, feature_cols,
                            path="models/training_metadata.json"):
    """Save training history and config for reproducibility."""
    metadata = {
        "features": feature_cols,
        "n_features": len(feature_cols),
        "final_val_loss": float(min(history.history["val_loss"])),
        "final_val_accuracy": float(max(history.history["val_accuracy"])),
        "epochs_trained": len(history.history["loss"]),
        "evaluation": {k: v for k, v in eval_results.items()
                       if k not in ("y_prob", "y_pred")},
    }
    with open(path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"📋 Training metadata saved → {path}")


# ─────────────────────────────────────────────────────────────
# MAIN TRAINING SCRIPT
# ─────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  RANSOMWARE LSTM MODEL TRAINING")
    print("=" * 55)

    # ── Step 1: Load preprocessed data ─────────────────────
    data = run_preprocessing(
        csv_path="dataset.csv",
        scaler_path="models/scaler.pkl"
    )
    X_train = data["X_train"]
    X_val   = data["X_val"]
    X_test  = data["X_test"]
    y_train = data["y_train"]
    y_val   = data["y_val"]
    y_test  = data["y_test"]
    n_features   = data["n_features"]
    feature_cols = data["feature_cols"]

    # ── Step 2: Build model ──────────────────────────────────
    print(f"\n🏗️  Building LSTM model ({n_features} features)...")
    model = build_lstm_model(n_features=n_features)
    model.summary()

    # ── Step 3: Train ────────────────────────────────────────
    history = train_model(
        model, X_train, y_train, X_val, y_val,
        epochs=50, batch_size=64,
        checkpoint_path="models/best_model.keras"
    )

    # ── Step 4: Evaluate ─────────────────────────────────────
    eval_results = evaluate_model(model, X_test, y_test, threshold=0.5)

    # ── Step 5: Save ─────────────────────────────────────────
    save_model(model)
    save_training_metadata(history, eval_results, feature_cols)

    print("\n🎉 Training complete! Model is ready for deployment.")
    print(f"   Final Test Accuracy : {eval_results['accuracy']:.4f}")
    print(f"   Final ROC-AUC       : {eval_results['roc_auc']:.4f}")

    return model, history, eval_results


if __name__ == "__main__":
    main()
