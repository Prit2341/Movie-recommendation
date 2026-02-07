import os
import psycopg2

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:12345678@localhost:5432/IMDB"
)


def get_connection():
    return psycopg2.connect(DATABASE_URL)
