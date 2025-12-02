#!/usr/bin/env python3
"""
Train ML Model
Trains a Random Forest Classifier to predict short-term price direction.
"""

import os
import sys
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, accuracy_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.data_builder import MLDataBuilder
from data.provider import DataProvider
from utilities.structured_logger import get_logger

logger = get_logger(__name__)

def train_model(symbol: str = "NIFTY 50", days: int = 365):
    """Train and save Random Forest model"""
    logger.info(f"🚀 Starting model training for {symbol}...")
    
    # 1. Fetch Data
    dp = DataProvider()
    builder = MLDataBuilder(dp)
    df = builder.fetch_and_prepare_data(symbol, days=days)
    
    if df is None or df.empty:
        logger.error("❌ Training aborted: No data")
        return
        
    # 2. Prepare Features (X) and Target (y)
    # Drop columns that are not features
    drop_cols = ['open', 'high', 'low', 'close', 'volume', 'target', 'log_return']
    # Keep only numeric columns
    features = [c for c in df.columns if c not in drop_cols and df[c].dtype in [np.float64, np.int64]]
    
    X = df[features]
    y = df['target']
    
    logger.info(f"📊 Features: {features}")
    logger.info(f"🔢 Samples: {len(X)}")
    
    # 3. Time Series Split (Train/Test)
    # Use last 20% for testing to respect time order
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # 4. Scaling
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 5. Train Random Forest
    logger.info("🧠 Training Random Forest Classifier...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=5,
        min_samples_split=10,
        random_state=42,
        n_jobs=-1,
        class_weight='balanced' # Handle potential class imbalance
    )
    model.fit(X_train_scaled, y_train)
    
    # 6. Evaluate
    y_pred = model.predict(X_test_scaled)
    y_prob = model.predict_proba(X_test_scaled)[:, 1]
    
    accuracy = accuracy_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_prob)
    
    print("\n" + "="*60)
    print(f"MODEL EVALUATION ({symbol})")
    print("="*60)
    print(f"Accuracy: {accuracy:.2%}")
    print(f"ROC AUC:  {roc_auc:.3f}")
    print("-" * 60)
    print("Classification Report:")
    print(classification_report(y_test, y_pred))
    print("="*60 + "\n")
    
    # 7. Save Model & Scaler
    save_dir = os.path.join(os.path.dirname(__file__), 'saved')
    os.makedirs(save_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d")
    model_path = os.path.join(save_dir, f"rf_model_{timestamp}.joblib")
    scaler_path = os.path.join(save_dir, f"scaler_{timestamp}.joblib")
    
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    
    logger.info(f"💾 Model saved to: {model_path}")
    logger.info(f"💾 Scaler saved to: {scaler_path}")
    
    # Save latest symlink
    latest_model = os.path.join(save_dir, "rf_model_latest.joblib")
    latest_scaler = os.path.join(save_dir, "scaler_latest.joblib")
    
    # Remove old links if exist
    if os.path.exists(latest_model): os.remove(latest_model)
    if os.path.exists(latest_scaler): os.remove(latest_scaler)
    
    # Create hard links (or copies if symlink fails on some OS)
    try:
        os.link(model_path, latest_model)
        os.link(scaler_path, latest_scaler)
        logger.info("🔗 Updated 'latest' model links")
    except OSError:
        import shutil
        shutil.copy(model_path, latest_model)
        shutil.copy(scaler_path, latest_scaler)
        logger.info("📋 Copied to 'latest' model files")

if __name__ == "__main__":
    train_model()
