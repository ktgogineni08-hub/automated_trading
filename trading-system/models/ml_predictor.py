#!/usr/bin/env python3
"""
ML Predictor
Loads trained model and provides predictions for live trading.
"""

import os
import joblib
import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional, Tuple

from models.data_builder import MLDataBuilder
from utilities.structured_logger import get_logger

logger = get_logger(__name__)

class MLPredictor:
    def __init__(self, model_dir: str = None):
        if model_dir is None:
            model_dir = os.path.join(os.path.dirname(__file__), 'saved')
            
        self.model_path = os.path.join(model_dir, 'rf_model_latest.joblib')
        self.scaler_path = os.path.join(model_dir, 'scaler_latest.joblib')
        
        self.model = None
        self.scaler = None
        self.builder = MLDataBuilder(None) # Data provider not needed for feature calc on existing df
        
        self._load_model()
        
    def _load_model(self):
        """Load model and scaler from disk"""
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                logger.info(f"✅ ML Model loaded from {self.model_path}")
            else:
                logger.warning(f"⚠️ ML Model not found at {self.model_path}")
        except Exception as e:
            logger.error(f"❌ Failed to load ML model: {e}")
            
    def predict(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Generate prediction for the latest candle
        Returns: {'probability': float, 'direction': int}
        """
        if self.model is None or df is None or df.empty:
            return {'probability': 0.5, 'direction': 0}
            
        try:
            # 1. Calculate Features
            # We need enough history to calculate features (e.g. 26 periods for MACD)
            if len(df) < 50:
                return {'probability': 0.5, 'direction': 0}
                
            df_features = self.builder._add_technical_features(df)
            
            # 2. Select Features (must match training)
            # Drop non-feature columns
            drop_cols = ['open', 'high', 'low', 'close', 'volume', 'target', 'log_return']
            features = [c for c in df_features.columns if c not in drop_cols and df_features[c].dtype in [np.float64, np.int64]]
            
            # Get latest row
            X_latest = df_features[features].iloc[[-1]]
            
            # Handle NaNs (replace with 0 or mean)
            X_latest = X_latest.fillna(0)
            
            # 3. Scale
            X_scaled = self.scaler.transform(X_latest)
            
            # 4. Predict
            prob = self.model.predict_proba(X_scaled)[0][1] # Probability of class 1 (Up)
            direction = 1 if prob > 0.5 else 0
            
            return {
                'probability': float(prob),
                'direction': direction,
                'confidence': float(abs(prob - 0.5) * 2) # 0 to 1 scale
            }
            
        except Exception as e:
            logger.error(f"❌ Prediction failed: {e}")
            return {'probability': 0.5, 'direction': 0}
