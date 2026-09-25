"""AMEX Healthcare Hackathon starter API.

Run locally with:
    uvicorn app.main:app --reload

All static/reference data your track needs (CSVs, JSON, sample docs, etc.)
should live in the top-level `/resources` folder and be loaded through
`app.resources.resource_path()` so the whole team uses one consistent location.
"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).resolve().parents[1] / ".env")  # backend/.env

from app.dcr.store import store  # noqa: E402  (after load_dotenv so env settings apply)
from app.routers import dcr, example  # noqa: E402

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.load()
    yield


app = FastAPI(
    title="AMEX Healthcare — Auto DCR Tracker API",
    description="Tracks Deviations, Complaints and Recalls (SOP 5) and turns incoming e-mails into DCR drafts.",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow the local Vite dev server (and any preview host) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(example.router)
app.include_router(dcr.router)


@app.get("/health", tags=["system"])
def health_check() -> dict:
    """Simple liveness check used by the frontend and CI."""
    return {"status": "ok"}
