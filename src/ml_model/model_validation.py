"""
model_validation.py — Cross-Validation & Metric Evaluation for Flash Flood Model.

Evaluates XGBoost model performance:
  - Accuracy, Precision, Recall, F1-Score
  - ROC-AUC Score
  - Confusion Matrix
"""

import os
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)

from xgboost_flood_classifier import FEATURE_NAMES, create_target_label

MODEL_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "models", "flood_xgboost.pkl")


def evaluate_model(data_path: str) -> dict:
    """
    Evaluates the trained model on test data split.
    """
    print(f"Reading validation data from {data_path}...")
    df = pd.read_csv(data_path)
    
    for col in FEATURE_NAMES:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())
        else:
            df[col] = 0.0

    df["flood_label"] = create_target_label(df)
    
    X = df[FEATURE_NAMES]
    y = df["flood_label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    if not os.path.exists(MODEL_FILE):
        print("Model file not found. Please train model first.")
        return {}

    model = joblib.load(MODEL_FILE)
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred)
    rec = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_prob)
    cm = confusion_matrix(y_test, y_pred)

    metrics = {
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(auc, 4),
        "confusion_matrix": cm.tolist(),
    }

    print("\n" + "="*50)
    print("      FLOOD PREDICTION MODEL EVALUATION METRICS      ")
    print("="*50)
    print(f" Accuracy:       {acc:.4f}")
    print(f" Precision:      {prec:.4f}")
    print(f" Recall:         {rec:.4f}")
    print(f" F1-Score:       {f1:.4f}")
    print(f" ROC-AUC Score:  {auc:.4f}")
    print("\nConfusion Matrix:")
    print(f"  TN: {cm[0][0]:<6} FP: {cm[0][1]:<6}")
    print(f"  FN: {cm[1][0]:<6} TP: {cm[1][1]:<6}")
    print("="*50)

    return metrics


if __name__ == "__main__":
    data_file = "data/processed/uttarakhand_full_features_REAL.csv"
    if os.path.exists(data_file):
        evaluate_model(data_file)
