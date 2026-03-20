import sys
import os
from contextlib import asynccontextmanager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from database.history import init_search_history_table
        init_search_history_table()
        print("Search history table initialized.")
    except Exception as e:
        print(f"Warning: Could not initialize search history table: {e}")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
