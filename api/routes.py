import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException, Query
from sklearn.metrics.pairwise import cosine_similarity
from rapidfuzz import process, fuzz
from model.loader import movies, tfidf_matrix
from database.history import save_search, get_search_history
from database.connection import get_connection
import numpy as np

router = APIRouter()

# Pre-compute list of titles for fuzzy matching
_all_titles = movies["primaryTitle"].tolist()

# Pre-compute normalised ratings for hybrid scoring (0-1 range)
_max_votes = movies["numVotes"].max() or 1
_norm_rating = (movies["averageRating"].fillna(0) / 10).to_numpy()
_norm_votes = (np.log1p(movies["numVotes"].fillna(0)) /
               np.log1p(_max_votes))


def fuzzy_find(title: str, score_cutoff: int = 50):
    """Return the closest matching movie title using fuzzy matching."""
    result = process.extractOne(
        title, _all_titles, scorer=fuzz.WRatio, score_cutoff=score_cutoff
    )
    if result is None:
        return None
    matched_title, _score, _index = result
    return matched_title


def _lookup_movie(title: str):
    """
    Find the best DataFrame row for *title*.

    Returns (matches_df, fuzzy_used, matched_title).
    Raises HTTPException(404) if nothing found.
    """
    # 1. exact match
    matches = movies[movies["primaryTitle"].str.lower() == title.lower()]

    # 2. substring match
    if matches.empty:
        matches = movies[movies["primaryTitle"].str.contains(
            title, case=False, na=False, regex=False
        )]

    # 3. fuzzy match
    fuzzy_used = False
    matched_title = title
    if matches.empty:
        fuzzy_match = fuzzy_find(title)
        if fuzzy_match:
            matches = movies[movies["primaryTitle"].str.lower() == fuzzy_match.lower()]
            fuzzy_used = True
            matched_title = fuzzy_match

    if matches.empty:
        raise HTTPException(status_code=404, detail="Movie not found")

    return matches, fuzzy_used, matched_title


def _hybrid_scores(idx: int, n: int):
    """
    Blend cosine similarity (70 %) with a popularity/rating signal (30 %).
    Returns (top_indices, raw_sim_scores).
    """
    cos_sim = cosine_similarity(tfidf_matrix[idx], tfidf_matrix).flatten()
    cos_sim[idx] = -1  # exclude self

    # Popularity signal: geometric mean of normalised rating & log-votes
    pop = np.sqrt(_norm_rating * _norm_votes)

    hybrid = 0.70 * cos_sim + 0.30 * pop
    hybrid[idx] = -1

    top_indices = hybrid.argsort()[-n:][::-1]
    return top_indices, cos_sim


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/recommend")
def recommend(title: str, n: int = 10):
    matches, fuzzy_used, matched_title = _lookup_movie(title)

    idx = matches.sort_values("numVotes", ascending=False).index[0]
    top_indices, cos_scores = _hybrid_scores(idx, n)

    results = movies.iloc[top_indices][
        ["primaryTitle", "startYear", "genres", "averageRating"]
    ].copy()
    results["similarity"] = cos_scores[top_indices]

    return {
        "recommendations": results.to_dict(orient="records"),
        "matched_title": matched_title,
        "fuzzy_match": fuzzy_used,
    }


@router.get("/search")
def search_movie(title: str = Query(..., description="Movie title to search for")):
    try:
        matches, fuzzy_used, matched_title = _lookup_movie(title)
    except HTTPException:
        try:
            save_search(search_query=title, matched_title=None)
        except Exception:
            pass
        raise

    best_match = matches.sort_values("numVotes", ascending=False).iloc[0]

    try:
        save_search(search_query=title, matched_title=best_match["primaryTitle"])
    except Exception:
        pass

    result_columns = [
        "tconst", "primaryTitle", "startYear", "genres",
        "averageRating", "numVotes", "director_names",
    ]
    result = best_match[result_columns].to_dict()

    # Replace NaN floats with None for clean JSON
    result = {k: (None if isinstance(v, float) and v != v else v)
              for k, v in result.items()}

    # Extra details from PostgreSQL
    tconst = result["tconst"]
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT original_title, runtime_minutes FROM movies WHERE tconst = %s",
                (tconst,),
            )
            row = cur.fetchone()
            cur.close()
        finally:
            conn.close()

        if row:
            result["originalTitle"] = row[0]
            result["runtimeMinutes"] = row[1]
        else:
            result["originalTitle"] = None
            result["runtimeMinutes"] = None
    except Exception:
        result["originalTitle"] = None
        result["runtimeMinutes"] = None

    if fuzzy_used:
        result["fuzzy_match"] = True
        result["searched_query"] = title

    return result


@router.get("/history")
def search_history(limit: int = Query(50, ge=1, le=500)):
    try:
        history = get_search_history(limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Could not retrieve search history: {e}"
        )
    return history
