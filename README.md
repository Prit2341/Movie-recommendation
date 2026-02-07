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
│   ├── index.html             # Web UI (Search, Recommend, History)
│   └── Dockerfile             # Nginx-based frontend image
├── model/
│   ├── Dockerfile             # Docker image for model training
│   ├── loader.py              # Loads .pkl artifacts into memory
│   ├── train_model.py         # Trains TF-IDF model, saves .pkl files
│   └── models/                # Generated .pkl files (not in git)
├── dataset/
│   └── data/                  # Raw IMDb .tsv files (not in git)
├── docker-compose.yml         # Docker services
├── Dockerfile                 # Docker image for backend API
├── .dockerignore
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

### 1. Install dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Start PostgreSQL

Make sure PostgreSQL is running locally. Set `DATABASE_URL` or update the default in `database/connection.py`.

### 3. Seed the database (one-time)

Download IMDb TSV files into `dataset/data/`:
- `title.basics.tsv`
- `title.ratings.tsv`
- `title.crew.tsv`
- `name.basics.tsv`

Then run:

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

## Setup (Docker)

### 1. Create a Docker network

```bash
docker network create mlops-bridge
```

### 2. Start the database

```bash
docker run -d --name db --network mlops-bridge -e POSTGRES_USER=<your_user> -e POSTGRES_PASSWORD=<your_password> -e POSTGRES_DB=<your_db> -p 5432:5432 postgres:16
```

Create the tables:

```bash
docker cp database/init.sql db:/init.sql
docker exec -it db psql -U <your_user> -d <your_db> -f /init.sql
```

### 3. Seed the database

If you have a local PostgreSQL with data, dump and load it:

```bash
pg_dump -U <your_user> -d <your_db> --data-only > data_dump.sql
docker cp data_dump.sql db:/data_dump.sql
docker exec -it db psql -U <your_user> -d <your_db> -f /data_dump.sql
```

### 4. Build the images

```bash
docker build -t mlops-backend -f Dockerfile .
docker build -t mlops-frontend -f frontend/Dockerfile ./frontend
docker build -t mlops-model -f model/Dockerfile .
```

### 5. Train the model

CMD:
```bash
docker run -d --name model-trainer --network mlops-bridge -v "%cd%/model/models:/app/model/models" -e DATABASE_URL=postgresql://<your_user>:<your_password>@db:5432/<your_db> mlops-model sh -c "python model/train_model.py && tail -f /dev/null"
```

PowerShell:
```bash
docker run -d --name model-trainer --network mlops-bridge -v "${PWD}/model/models:/app/model/models" -e DATABASE_URL=postgresql://<your_user>:<your_password>@db:5432/<your_db> mlops-model sh -c "python model/train_model.py && tail -f /dev/null"
```

### 6. Start the backend

CMD:
```bash
docker run -d --name backend --network mlops-bridge -v "%cd%/model/models:/app/model/models" -e DATABASE_URL=postgresql://<your_user>:<your_password>@db:5432/<your_db> -p 5000:5000 mlops-backend
```

PowerShell:
```bash
docker run -d --name backend --network mlops-bridge -v "${PWD}/model/models:/app/model/models" -e DATABASE_URL=postgresql://<your_user>:<your_password>@db:5432/<your_db> -p 5000:5000 mlops-backend
```

### 7. Start the frontend

```bash
docker run -d --name frontend --network mlops-bridge -p 3000:80 mlops-frontend
```

### 8. Start pgAdmin (optional)

```bash
docker run -d --name pgadmin --network mlops-bridge -e PGADMIN_DEFAULT_EMAIL=<your_email> -e PGADMIN_DEFAULT_PASSWORD=<your_password> -p 5050:80 dpage/pgadmin4
```

To connect pgAdmin to the database, add a new server with host `db`, port `5432`, and your database credentials.

### 9. Access the application

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:5000 |
| Health Check | http://localhost:5000/health |
| pgAdmin | http://localhost:5050 |

## Stopping and Starting

### Stop all containers

```bash
docker stop backend frontend model-trainer db pgadmin
```

### Start all containers again

```bash
docker start db
docker start backend frontend model-trainer pgadmin
```

> Start `db` first so the backend can connect to PostgreSQL on startup.

### Remove all containers and start fresh

```bash
docker rm -f backend frontend model-trainer db pgadmin
docker network rm mlops-bridge
```

### View logs

```bash
docker logs backend
docker logs frontend
docker logs model-trainer
docker logs db
docker logs pgadmin
```

## Updating Code

### After changing backend code (`backend/`, `api/`, `database/`)

Rebuild the backend image and restart the container:

CMD:
```bash
docker rm -f backend
docker build -t mlops-backend -f Dockerfile .
docker run -d --name backend --network mlops-bridge -v "%cd%/model/models:/app/model/models" -e DATABASE_URL=postgresql://<your_user>:<your_password>@db:5432/<your_db> -p 5000:5000 mlops-backend
```

PowerShell:
```bash
docker rm -f backend
docker build -t mlops-backend -f Dockerfile .
docker run -d --name backend --network mlops-bridge -v "${PWD}/model/models:/app/model/models" -e DATABASE_URL=postgresql://<your_user>:<your_password>@db:5432/<your_db> -p 5000:5000 mlops-backend
```

### After changing frontend code (`frontend/`)

Rebuild the frontend image and restart the container:

```bash
docker rm -f frontend
docker build -t mlops-frontend -f frontend/Dockerfile ./frontend
docker run -d --name frontend --network mlops-bridge -p 3000:80 mlops-frontend
```

### After changing model code (`model/train_model.py`)

Rebuild the model image and retrain:

CMD:
```bash
docker build -t mlops-model -f model/Dockerfile .
docker rm -f model-trainer
docker run -d --name model-trainer --network mlops-bridge -v "%cd%/model/models:/app/model/models" -e DATABASE_URL=postgresql://<your_user>:<your_password>@db:5432/<your_db> mlops-model sh -c "python model/train_model.py && tail -f /dev/null"
docker restart backend
```

PowerShell:
```bash
docker build -t mlops-model -f model/Dockerfile .
docker rm -f model-trainer
docker run -d --name model-trainer --network mlops-bridge -v "${PWD}/model/models:/app/model/models" -e DATABASE_URL=postgresql://<your_user>:<your_password>@db:5432/<your_db> mlops-model sh -c "python model/train_model.py && tail -f /dev/null"
docker restart backend
```

### After changing the database schema (`database/init.sql`)

```bash
docker cp database/init.sql db:/init.sql
docker exec -it db psql -U <your_user> -d <your_db> -f /init.sql
docker restart backend
```

## Docker Compose (Alternative)

Instead of running containers manually, use Docker Compose. Set your credentials in a `.env` file:

```env
POSTGRES_USER=<your_user>
POSTGRES_PASSWORD=<your_password>
POSTGRES_DB=<your_db>
```

Then run:

```bash
docker-compose up -d
```

Stop everything:

```bash
docker-compose down
```

## Docker Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **db** | `postgres:16` | `5432` | PostgreSQL database |
| **backend** | `./Dockerfile` | `5000` | FastAPI API server |
| **frontend** | `./frontend/Dockerfile` | `3000` | Serves static HTML via Nginx |
| **pgadmin** | `dpage/pgadmin4` | `5050` | Database management UI |
| **model** | `./model/Dockerfile` | — | Model training (runs once) |

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
