import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException, Query
from sklearn.metrics.pairwise import cosine_similarity
from model.loader import movies, tfidf_matrix
from database.history import save_search, get_search_history
from database.connection import get_connection

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/recommend")
def recommend(title: str, n: int = 10):
    matches = movies[movies["primaryTitle"].str.lower() == title.lower()]

    if matches.empty:
        matches = movies[movies["primaryTitle"].str.contains(title, case=False, na=False)]

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

    return results.to_dict(orient="records")


@router.get("/search")
def search_movie(title: str = Query(..., description="Movie title to search for")):
    matches = movies[movies["primaryTitle"].str.lower() == title.lower()]

    if matches.empty:
        matches = movies[movies["primaryTitle"].str.contains(title, case=False, na=False)]

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

    return result


@router.get("/history")
def search_history(limit: int = Query(50, ge=1, le=500)):
    try:
        history = get_search_history(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not retrieve search history: {str(e)}")
    return history
