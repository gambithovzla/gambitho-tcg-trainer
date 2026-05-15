from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.decks import router as decks_router
from src.api.routes.ingestion import router as ingestion_router
from src.api.routes.simulation import router as simulation_router

app = FastAPI(
    title="Gambitho TCG Trainer API",
    version="0.1.0",
    description="Lorcana-first neuro-symbolic MVP backend.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(decks_router, prefix="/decks", tags=["decks"])
app.include_router(simulation_router, prefix="/simulate", tags=["simulation"])
app.include_router(ingestion_router, prefix="/ingest", tags=["ingestion"])


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
