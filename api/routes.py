import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException, Query
from sklearn.metrics.pairwise import cosine_similarity
from rapidfuzz import process, fuzz
from model.loader import movies, tfidf_matrix
from database.history import save_search, get_search_history
from database.connection import get_connection

router = APIRouter()

# Pre-compute list of titles for fuzzy matching
_all_titles = movies["primaryTitle"].tolist()


def fuzzy_find(title: str, score_cutoff: int = 50):
    """Find the closest matching movie title using fuzzy matching."""
    result = process.extractOne(title, _all_titles, scorer=fuzz.WRatio, score_cutoff=score_cutoff)
    if result is None:
        return None
    matched_title, score, index = result
    return matched_title


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/recommend")
def recommend(title: str, n: int = 10):
    fuzzy_used = False
    matched_title = title

    matches = movies[movies["primaryTitle"].str.lower() == title.lower()]

    if matches.empty:
        matches = movies[movies["primaryTitle"].str.contains(title, case=False, na=False)]

    if matches.empty:
        fuzzy_match = fuzzy_find(title)
        if fuzzy_match:
            matches = movies[movies["primaryTitle"].str.lower() == fuzzy_match.lower()]
            fuzzy_used = True
            matched_title = fuzzy_match

    if matches.empty:
        raise HTTPException(status_code=404, detail="Movie not found")

    idx = matches.sort_values("numVotes", ascending=False).index[0]

    sim_scores = cosine_similarity(
        tfidf_matrix[idx],
        tfidf_matrix
    ).flatten()

    sim_scores[idx] = -1
    top_indices = sim_scores.argsort()[-n:][::-1]

    results = movies.iloc[top_indices][
        ["primaryTitle", "startYear", "genres", "averageRating"]
    ].copy()

    results["similarity"] = sim_scores[top_indices]

    response = {
        "recommendations": results.to_dict(orient="records"),
        "matched_title": matched_title,
        "fuzzy_match": fuzzy_used,
    }
    return response


@router.get("/search")
def search_movie(title: str = Query(..., description="Movie title to search for")):
    fuzzy_used = False

    matches = movies[movies["primaryTitle"].str.lower() == title.lower()]

    if matches.empty:
        matches = movies[movies["primaryTitle"].str.contains(title, case=False, na=False)]

    if matches.empty:
        fuzzy_match = fuzzy_find(title)
        if fuzzy_match:
            matches = movies[movies["primaryTitle"].str.lower() == fuzzy_match.lower()]
            fuzzy_used = True

    if matches.empty:
        try:
            save_search(search_query=title, matched_title=None)
        except Exception:
            pass
        raise HTTPException(status_code=404, detail="Movie not found")

    best_match = matches.sort_values("numVotes", ascending=False).iloc[0]

    try:
        save_search(search_query=title, matched_title=best_match["primaryTitle"])
    except Exception:
        pass

    result_columns = ["tconst", "primaryTitle", "startYear", "genres",
                      "averageRating", "numVotes", "director_names"]
    result = best_match[result_columns].to_dict()

    for key, value in result.items():
        if isinstance(value, float) and (value != value):
            result[key] = None

    # Fetch extra details from PostgreSQL (runtime, original title, cast)
    tconst = result["tconst"]
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT original_title, runtime_minutes FROM movies WHERE tconst = %s",
            (tconst,),
        )
        row = cur.fetchone()
        if row:
            result["originalTitle"] = row[0]
            result["runtimeMinutes"] = row[1]

        cur.execute("""
            SELECT n.primary_name, p.category, p.characters
            FROM principals p
            JOIN names n ON p.nconst = n.nconst
            WHERE p.tconst = %s
            ORDER BY p.ordering
        """, (tconst,))
        cast = []
        for r in cur.fetchall():
            cast.append({
                "name": r[0],
                "role": r[1],
                "characters": r[2],
            })
        result["cast"] = cast

        cur.close()
        conn.close()
    except Exception:
        result["originalTitle"] = None
        result["runtimeMinutes"] = None
        result["cast"] = []

    if fuzzy_used:
        result["fuzzy_match"] = True
        result["searched_query"] = title

    return result


@router.get("/history")
def search_history(limit: int = Query(50, ge=1, le=500)):
    try:
        history = get_search_history(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not retrieve search history: {str(e)}")
    return history
