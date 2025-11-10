import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
import os

def create_pretrained_model():
    np.random.seed(42)
    
    n_samples = 1000
    n_features = 12
    
    X_train = np.random.rand(n_samples, n_features)
    
    y_train = np.zeros(n_samples, dtype=int)
    
    y_train[X_train[:, 0] > 0.6] = 0
    y_train[(X_train[:, 0] <= 0.6) & (X_train[:, 1] > 0.5)] = 1
    y_train[(X_train[:, 0] <= 0.6) & (X_train[:, 1] <= 0.5) & (X_train[:, 2] > 0.4)] = 2
    y_train[(X_train[:, 0] <= 0.6) & (X_train[:, 1] <= 0.5) & (X_train[:, 2] <= 0.4)] = 3
    
    rf_model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    
    rf_model.fit(X_train, y_train)
    
    os.makedirs('models', exist_ok=True)
    joblib.dump(rf_model, 'models/crop_classifier.pkl')
    
    print("Pre-trained Random Forest model created successfully!")
    print(f"Model accuracy on training data: {rf_model.score(X_train, y_train):.2f}")
    print("Model saved to: models/crop_classifier.pkl")
    
    return rf_model

if __name__ == "__main__":
    create_pretrained_model()
