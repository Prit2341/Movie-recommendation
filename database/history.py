import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_connection


def init_search_history_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            id SERIAL PRIMARY KEY,
            search_query VARCHAR(512) NOT NULL,
            matched_title VARCHAR(512),
            searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


def save_search(search_query: str, matched_title: str | None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO search_history (search_query, matched_title) VALUES (%s, %s)",
        (search_query, matched_title),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_search_history(limit: int = 50):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, search_query, matched_title, searched_at "
        "FROM search_history ORDER BY searched_at DESC LIMIT %s",
        (limit,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "id": row[0],
            "search_query": row[1],
            "matched_title": row[2],
            "searched_at": row[3].isoformat() if row[3] else None,
        }
        for row in rows
    ]
