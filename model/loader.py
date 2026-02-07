import os
import joblib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "model", "models")

movies = joblib.load(os.path.join(MODELS_DIR, "movies_df.pkl"))
tfidf_matrix = joblib.load(os.path.join(MODELS_DIR, "tfidf_matrix.pkl"))
