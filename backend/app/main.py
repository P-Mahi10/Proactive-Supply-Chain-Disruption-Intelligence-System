from fastapi import FastAPI

from app.api.routes import router
from app.utils.logger import get_logger

logger = get_logger(__name__)

# FastAPI application entrypoint for the backend service.
app = FastAPI(title="Proactive Supply Chain Disruption Intelligence System")
app.include_router(router)


@app.on_event("startup")
def on_startup() -> None:
    logger.info("API startup complete.")
