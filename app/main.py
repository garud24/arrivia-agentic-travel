import logging

from fastapi import FastAPI
from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


app = FastAPI(
    title="Arrivia Agentic Travel Recommendations API",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "healthy"}


app.include_router(
    router,
    prefix="/api",
)
