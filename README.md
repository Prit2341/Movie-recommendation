# Movie Recommender System

A content-based movie recommendation system with search, recommendations, and search history tracking. Built with FastAPI, scikit-learn (TF-IDF + Cosine Similarity), PostgreSQL, and vanilla JavaScript.

## Project Structure

```
MLops_IA/
├── api/
│   └── routes.py              # API endpoints (/health, /recommend, /search, /history)
├── backend/
│   └── app.py                 # FastAPI app, CORS config, startup hook
├── database/
│   ├── connection.py          # PostgreSQL connection (reads DATABASE_URL env var)
│   ├── history.py             # Search history helpers (save, retrieve, init table)
│   ├── init.sql               # Schema: movies, names, principals, search_history
│   └── seed.py                # Loads IMDb TSV files into PostgreSQL
├── frontend/
│   └── index.html             # Web UI (Search, Recommend, History)
├── model/
│   ├── Dockerfile             # Docker image for model training
│   ├── loader.py              # Loads .pkl artifacts into memory
│   ├── train_model.py         # Trains TF-IDF model, saves .pkl files
│   └── models/                # Generated .pkl files (not in git)
├── dataset/
│   └── data/                  # Raw IMDb .tsv files (not in git)
├── docker-compose.yml         # Docker services
├── Dockerfile                 # Docker image for backend API
├── requirements.txt
└── README.md
```

## Data Flow

```
IMDb .tsv files → seed.py → PostgreSQL → train_model.py → .pkl files → API → Frontend
```

1. **seed.py** loads raw IMDb data into PostgreSQL, builds the `soup` feature (genres + directors + decade)
2. **train_model.py** reads from PostgreSQL, builds TF-IDF matrix, saves `.pkl` artifacts
3. **API** loads `.pkl` files into memory, serves recommendations and search results
4. **Frontend** calls the API and displays results

## Setup (Local)

### 1. Start PostgreSQL

```bash
docker-compose up -d
```

### 2. Install dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 3. Seed the database (one-time)

```bash
python database/seed.py
```

### 4. Train the model (one-time)

```bash
python model/train_model.py
```

### 5. Run the API

```bash
uvicorn backend.app:app --host 0.0.0.0 --port 5000
```

### 6. Open the frontend

Open `frontend/index.html` in a browser.

## Docker Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **db** | `postgres:16` | `5432` | PostgreSQL database |
| **backend** | `./Dockerfile` | `5000` | FastAPI API server |
| **frontend** | `nginx:alpine` | `3000` | Serves static HTML |
| **pgadmin** | `dpage/pgadmin4` | `5050` | Database management UI |
| **model** | `./model/Dockerfile` | — | Model training (runs once) |

All services share a Docker bridge network. The backend connects to PostgreSQL via the `DATABASE_URL` environment variable.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/recommend?title=<movie>&n=10` | GET | Get top N similar movies |
| `/search?title=<movie>` | GET | Search a movie, returns full details + cast |
| `/history?limit=50` | GET | Get recent search history |

### Example: Search

```
GET /search?title=The Dark Knight
```

Returns: title, year, genres, rating, votes, directors, runtime, original title, and full cast/crew list.

### Example: Recommend

```
GET /recommend?title=Inception&n=5
```

Returns: top 5 similar movies with similarity scores.

## Tech Stack

- **Backend:** FastAPI, scikit-learn, pandas, joblib, psycopg2
- **Database:** PostgreSQL 16
- **Frontend:** HTML, CSS, JavaScript (no frameworks)
- **ML:** TF-IDF Vectorizer + Cosine Similarity
- **Infrastructure:** Docker, Docker Compose, Nginx, pgAdmin