import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.catalog import router as catalog_router
from src.api.routes.decks import router as decks_router
from src.api.routes.ingestion import router as ingestion_router
from src.api.routes.simulation import router as simulation_router


def _load_env_file() -> None:
    env_path = Path.cwd() / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()

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

app.include_router(catalog_router, prefix="/catalog", tags=["catalog"])
app.include_router(decks_router, prefix="/decks", tags=["decks"])
app.include_router(simulation_router, prefix="/simulate", tags=["simulation"])
app.include_router(ingestion_router, prefix="/ingest", tags=["ingestion"])


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
