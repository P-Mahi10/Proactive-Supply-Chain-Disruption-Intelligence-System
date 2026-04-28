from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.utils.logger import get_logger

logger = get_logger(__name__)

# FastAPI application entrypoint for the backend service.
app = FastAPI(title="Proactive Supply Chain Disruption Intelligence System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
    ],
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


@app.on_event("startup")
def on_startup() -> None:
    logger.info("API startup complete.")