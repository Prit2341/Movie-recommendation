"""
Seed script: Load IMDb TSV data, process it, and insert into PostgreSQL.

Uses COPY (fastest bulk load method) for maximum speed.

Pipeline (same as model/train_model.ipynb):
  1. Load title.basics.tsv -> filter to movies only
  2. Load title.ratings.tsv -> merge, filter numVotes >= 100
  3. Load title.crew.tsv -> get director IDs
  4. Load name.basics.tsv -> resolve director IDs to names
  5. Build "soup" feature (genres + directors + decade)
  6. COPY into movies, names, and principals tables
"""

import os
import sys
import io
import time
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from connection import get_connection

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dataset", "data")
MIN_VOTES = 100


def load_and_process():
    print(f"Loading TSV files from: {DATA_DIR}")

    # 1. Load title.basics.tsv — filter to movies
    print("Loading title.basics.tsv...")
    basics = pd.read_csv(
        os.path.join(DATA_DIR, "title.basics.tsv"),
        sep="\t", dtype=str, na_values="\\N",
        usecols=["tconst", "titleType", "primaryTitle", "originalTitle",
                 "startYear", "runtimeMinutes", "genres"]
    )
    movies = basics[basics["titleType"] == "movie"].copy()
    movies.drop(columns=["titleType"], inplace=True)
    movies["startYear"] = pd.to_numeric(movies["startYear"], errors="coerce")
    movies["runtimeMinutes"] = pd.to_numeric(movies["runtimeMinutes"], errors="coerce")
    print(f"  Movies in basics: {len(movies)}")

    # 2. Load title.ratings.tsv — merge and filter
    print("Loading title.ratings.tsv...")
    ratings = pd.read_csv(
        os.path.join(DATA_DIR, "title.ratings.tsv"),
        sep="\t", na_values="\\N"
    )
    movies = movies.merge(ratings, on="tconst", how="inner")
    movies = movies[movies["numVotes"] >= MIN_VOTES].copy()
    print(f"  Movies after vote filter (>= {MIN_VOTES}): {len(movies)}")

    # 3. Load title.crew.tsv — get directors
    print("Loading title.crew.tsv...")
    crew = pd.read_csv(
        os.path.join(DATA_DIR, "title.crew.tsv"),
        sep="\t", dtype=str, na_values="\\N",
        usecols=["tconst", "directors"]
    )
    movies = movies.merge(crew, on="tconst", how="left")

    # 4. Load name.basics.tsv — resolve director IDs to names
    print("Loading name.basics.tsv...")
    names_df = pd.read_csv(
        os.path.join(DATA_DIR, "name.basics.tsv"),
        sep="\t", dtype=str, na_values="\\N",
        usecols=["nconst", "primaryName", "birthYear", "deathYear", "primaryProfession"]
    )
    name_lookup = dict(zip(names_df["nconst"], names_df["primaryName"]))

    def resolve_directors(director_ids):
        if pd.isna(director_ids):
            return ""
        ids = director_ids.split(",")
        resolved = [name_lookup.get(nid, "") for nid in ids]
        return " ".join([n.replace(" ", "") for n in resolved if n])

    movies["director_names"] = movies["directors"].apply(resolve_directors)
    movies.drop(columns=["directors"], inplace=True)

    # 5. Build soup feature
    def create_soup(row):
        parts = []
        if pd.notna(row["genres"]):
            parts.append(row["genres"].replace(",", " "))
        if row["director_names"]:
            parts.append(row["director_names"])
        if pd.notna(row["startYear"]):
            decade = f"{int(row['startYear'] // 10 * 10)}s"
            parts.append(decade)
        return " ".join(parts)

    movies["soup"] = movies.apply(create_soup, axis=1)
    movies = movies[movies["soup"].str.strip() != ""].copy()
    movies.reset_index(drop=True, inplace=True)
    print(f"  Final processed movies: {len(movies)}")

    return movies, names_df


def df_to_csv_buffer(df):
    """Convert DataFrame to an in-memory CSV buffer for COPY."""
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False, sep="\t", na_rep="\\N")
    buffer.seek(0)
    return buffer


def seed_names(conn, names_df):
    print("Inserting names via COPY...")
    start = time.time()
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE names;")
    conn.commit()

    # Prepare DataFrame columns to match table (convert floats to nullable ints)
    names_db = pd.DataFrame({
        "nconst": names_df["nconst"],
        "primary_name": names_df["primaryName"],
        "birth_year": pd.to_numeric(names_df["birthYear"], errors="coerce").astype("Int64"),
        "death_year": pd.to_numeric(names_df["deathYear"], errors="coerce").astype("Int64"),
        "primary_profession": names_df["primaryProfession"],
    })

    buffer = df_to_csv_buffer(names_db)
    cur.copy_expert(
        "COPY names (nconst, primary_name, birth_year, death_year, primary_profession) FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t', NULL '\\N')",
        buffer
    )
    conn.commit()

    elapsed = time.time() - start
    print(f"  Names done: {len(names_db):,} rows in {elapsed:.0f}s")


def seed_movies(conn, movies):
    print("Inserting movies via COPY...")
    start = time.time()
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE movies;")
    conn.commit()

    # Prepare DataFrame columns to match table (convert floats to nullable ints)
    movies_db = pd.DataFrame({
        "tconst": movies["tconst"],
        "primary_title": movies["primaryTitle"],
        "original_title": movies.get("originalTitle"),
        "start_year": movies["startYear"].astype("Int64"),
        "runtime_minutes": movies["runtimeMinutes"].astype("Int64"),
        "genres": movies["genres"],
        "average_rating": movies["averageRating"],
        "num_votes": movies["numVotes"].astype("Int64"),
        "director_names": movies["director_names"],
        "soup": movies["soup"],
    })

    buffer = df_to_csv_buffer(movies_db)
    cur.copy_expert(
        "COPY movies (tconst, primary_title, original_title, start_year, runtime_minutes, genres, average_rating, num_votes, director_names, soup) FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t', NULL '\\N')",
        buffer
    )
    conn.commit()

    elapsed = time.time() - start
    print(f"  Movies done: {len(movies_db):,} rows in {elapsed:.0f}s")


def seed_principals(conn):
    """Load title.principals.tsv in chunks and COPY into principals table."""
    print("Inserting principals via chunked COPY...")
    start = time.time()
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE principals;")
    conn.commit()

    tsv_path = os.path.join(DATA_DIR, "title.principals.tsv")
    total_rows = 0
    chunk_size = 5_000_000

    for chunk in pd.read_csv(
        tsv_path, sep="\t", dtype=str, na_values="\\N",
        usecols=["tconst", "ordering", "nconst", "category", "job", "characters"],
        chunksize=chunk_size
    ):
        chunk["ordering"] = pd.to_numeric(chunk["ordering"], errors="coerce").astype("Int64")
        principals_db = pd.DataFrame({
            "tconst": chunk["tconst"],
            "ordering": chunk["ordering"],
            "nconst": chunk["nconst"],
            "category": chunk["category"],
            "job": chunk["job"],
            "characters": chunk["characters"],
        })
        buffer = df_to_csv_buffer(principals_db)
        cur.copy_expert(
            "COPY principals (tconst, ordering, nconst, category, job, characters) FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t', NULL '\\N')",
            buffer
        )
        conn.commit()
        total_rows += len(chunk)
        print(f"  ... {total_rows:,} rows loaded")

    elapsed = time.time() - start
    print(f"  Principals done: {total_rows:,} rows in {elapsed:.0f}s")


def create_tables(conn):
    print("Creating tables...")
    cur = conn.cursor()
    cur.execute(open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "init.sql")
    ).read())
    cur.execute("ALTER TABLE movies ALTER COLUMN director_names TYPE TEXT;")
    conn.commit()
    print("  Tables created.")


def ensure_database():
    """Create the IMDB database if it doesn't exist."""
    import psycopg2
    conn = psycopg2.connect("postgresql://postgres:12345678@localhost:5432/postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'IMDB'")
    if not cur.fetchone():
        print("Creating database IMDB...")
        cur.execute('CREATE DATABASE "IMDB"')
        print("  Database created.")
    else:
        print("Database IMDB already exists.")
    conn.close()


def main():
    total_start = time.time()
    movies, names_df = load_and_process()

    print("\nConnecting to database...")
    ensure_database()
    conn = get_connection()

    create_tables(conn)
    seed_names(conn, names_df)
    seed_movies(conn, movies)
    seed_principals(conn)

    # Verify
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM movies;")
    print(f"\nVerification — movies in DB: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM names;")
    print(f"Verification — names in DB: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM principals;")
    print(f"Verification — principals in DB: {cur.fetchone()[0]}")

    conn.close()
    total_elapsed = time.time() - total_start
    print(f"Seeding complete! Total time: {total_elapsed:.0f}s")


if __name__ == "__main__":
    main()
