from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API startup complete.")
    yield
    logger.info("API shutdown.")

# FastAPI application entrypoint for the backend service.
app = FastAPI(
    title="Proactive Supply Chain Disruption Intelligence System",
    lifespan=lifespan,
)

def _get_allowed_origins() -> list[str]:
    default_origins = [
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5501",
        "http://127.0.0.1:5501",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "null",  # local file:// origin
    ]

    env_origins = [
        origin.strip()
        for origin in os.environ.get("CORS_ALLOW_ORIGINS", "").split(",")
        if origin.strip()
    ]

    allowed = []
    for origin in default_origins + env_origins:
        if origin not in allowed:
            allowed.append(origin)
    return allowed


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router)


@app.get("/")
def root():
    return {
        "status": "running",
        "service": "Proactive Supply Chain Disruption Intelligence System",
        "docs": "/docs"
    }


