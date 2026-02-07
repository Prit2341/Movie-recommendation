# Movie Recommendation System — Training
#
# Content-based recommendation using TF-IDF on movie features (genres, directors, decade).
# Data source: PostgreSQL (`IMDB` database, `movies` table)

import pandas as pd
import numpy as np
import os
import sys
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Add project root to path so we can import database.connection
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(MODEL_DIR, exist_ok=True)

print("Setup done!")

# ── 1. Load movies from PostgreSQL ──────────────────────────────────────────

from database.connection import get_connection

conn = get_connection()

movies = pd.read_sql("""
    SELECT tconst, primary_title AS "primaryTitle",
           start_year AS "startYear", genres,
           average_rating AS "averageRating",
           num_votes AS "numVotes",
           director_names, soup
    FROM movies
    WHERE soup IS NOT NULL AND soup != ''
""", conn)

conn.close()

movies.reset_index(drop=True, inplace=True)
print(f"Loaded {len(movies):,} movies from PostgreSQL")
print(movies.head())

# ── 2. Build TF-IDF matrix ──────────────────────────────────────────────────

tfidf = TfidfVectorizer(stop_words="english")
tfidf_matrix = tfidf.fit_transform(movies["soup"])

print(f"TF-IDF matrix shape: {tfidf_matrix.shape}")
print(f"TF-IDF matrix memory: {tfidf_matrix.data.nbytes / 1024 / 1024:.1f} MB")

# ── 3. Save model artifacts ─────────────────────────────────────────────────

# Save only the columns needed by the API
save_cols = ["tconst", "primaryTitle", "startYear", "genres", "averageRating",
             "numVotes", "director_names", "soup"]
movies_save = movies[save_cols].copy()

joblib.dump(movies_save, os.path.join(MODEL_DIR, "movies_df.pkl"))
joblib.dump(tfidf_matrix, os.path.join(MODEL_DIR, "tfidf_matrix.pkl"))
joblib.dump(tfidf, os.path.join(MODEL_DIR, "tfidf_vectorizer.pkl"))

print("Artifacts saved to models/:")
for f in os.listdir(MODEL_DIR):
    size_mb = os.path.getsize(os.path.join(MODEL_DIR, f)) / 1024 / 1024
    print(f"  {f}: {size_mb:.1f} MB")

# ── 4. Quick test — get recommendations ─────────────────────────────────────

def recommend(title, n=10):
    """Get movie recommendations based on a title."""
    matches = movies[movies["primaryTitle"].str.lower() == title.lower()]
    if matches.empty:
        matches = movies[movies["primaryTitle"].str.contains(title, case=False, na=False)]
    if matches.empty:
        print(f"No movie found matching '{title}'")
        return None

    # Pick the one with most votes if multiple matches
    idx = matches.sort_values("numVotes", ascending=False).index[0]
    print(f"Matched: {movies.loc[idx, 'primaryTitle']} ({int(movies.loc[idx, 'startYear'])})")

    sim_scores = cosine_similarity(tfidf_matrix[idx], tfidf_matrix).flatten()
    sim_scores[idx] = -1  # Exclude self
    top_indices = sim_scores.argsort()[-n:][::-1]

    results = movies.iloc[top_indices][["primaryTitle", "startYear", "genres", "averageRating"]].copy()
    results["similarity"] = sim_scores[top_indices]
    return results


# Test it!
print(recommend("The Dark Knight"))

# Try another movie
print(recommend("Inception"))
