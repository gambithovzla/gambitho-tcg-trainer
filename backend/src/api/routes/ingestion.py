from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.infra.db.neo4j.synergy_loader import Neo4jSynergyLoader
from src.infra.db.postgres.card_repository import PostgresCardRepository
from src.infra.db.qdrant.embed_indexer import QdrantEmbedIndexer
from src.infra.ingestion.lorcana_ingestor import IngestionSummary, LorcanaIngestor
from src.infra.ingestion.lorcast_client import fetch_card_search

router = APIRouter()

LORCANAJSON_FILES_BASE = "https://lorcanajson.org/files/current"


def _lorcanajson_all_cards_url(language: str) -> str:
    return f"{LORCANAJSON_FILES_BASE}/{language}/allCards.json"


def _lorcanajson_setdata_url(language: str, set_code: str) -> str:
    return f"{LORCANAJSON_FILES_BASE}/{language}/sets/setdata.{set_code}.json"


class LorcanaIngestRequest(BaseModel):
    cards: list[dict[str, Any]] = Field(default_factory=list)


class LorcanaIngestResponse(BaseModel):
    cards_seen: int
    cards_loaded_sql: int
    cards_loaded_graph: int
    cards_loaded_vector: int
    cards_rejected: int


class LorcanaIngestFromSourceRequest(BaseModel):
    url: str = Field(..., min_length=1)


class LorcastIngestRequest(BaseModel):
    """Query Lorcast search API then ingest (https://api.lorcast.com/v0/cards/search)."""

    q: str = Field(default="set:1", min_length=1, max_length=512)
    unique: Literal["cards", "prints"] = "prints"


class LorcanaJsonIngestRequest(BaseModel):
    """Fetch official LorcanaJSON dumps from https://lorcanajson.org/files/current/..."""

    language: Literal["en", "fr", "de", "it"] = "en"
    resource: Literal["all_cards", "set"] = "all_cards"
    set_code: str | None = Field(
        default=None,
        description='Set id for resource "set", e.g. "1" for The First Chapter (setdata.1.json).',
    )


def _build_ingestor() -> LorcanaIngestor:
    return LorcanaIngestor(
        card_repository=PostgresCardRepository(),
        graph_loader=Neo4jSynergyLoader(),
        embed_indexer=QdrantEmbedIndexer(),
    )


@router.post("/lorcana", response_model=LorcanaIngestResponse)
def ingest_lorcana(payload: LorcanaIngestRequest) -> LorcanaIngestResponse:
    ingestor = _build_ingestor()
    try:
        result: IngestionSummary = ingestor.ingest_from_payload(payload.cards)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Ingestion failed: {exc}") from exc

    return LorcanaIngestResponse(
        cards_seen=result.cards_seen,
        cards_loaded_sql=result.cards_loaded_sql,
        cards_loaded_graph=result.cards_loaded_graph,
        cards_loaded_vector=result.cards_loaded_vector,
        cards_rejected=result.cards_rejected,
    )


@router.post("/lorcana/source", response_model=LorcanaIngestResponse)
def ingest_lorcana_from_source(payload: LorcanaIngestFromSourceRequest) -> LorcanaIngestResponse:
    headers = {"User-Agent": "gambitho-tcg-trainer/0.1"}
    timeout = httpx.Timeout(120.0, connect=30.0)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(payload.url, headers=headers)
            response.raise_for_status()
            source_payload = response.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Source fetch failed: {exc}") from exc

    cards = LorcanaIngestor.extract_cards(source_payload)
    ingestor = _build_ingestor()
    try:
        result = ingestor.ingest_from_payload(cards)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Ingestion failed: {exc}") from exc

    return LorcanaIngestResponse(
        cards_seen=result.cards_seen,
        cards_loaded_sql=result.cards_loaded_sql,
        cards_loaded_graph=result.cards_loaded_graph,
        cards_loaded_vector=result.cards_loaded_vector,
        cards_rejected=result.cards_rejected,
    )


@router.post("/lorcana/lorcanajson", response_model=LorcanaIngestResponse)
def ingest_lorcana_from_lorcanajson(payload: LorcanaJsonIngestRequest) -> LorcanaIngestResponse:
    if payload.resource == "set":
        if not (payload.set_code and payload.set_code.strip()):
            raise HTTPException(
                status_code=422,
                detail='resource "set" requires non-empty set_code (e.g. "1").',
            )
        url = _lorcanajson_setdata_url(payload.language, payload.set_code.strip())
    else:
        url = _lorcanajson_all_cards_url(payload.language)

    headers = {"User-Agent": "gambitho-tcg-trainer/0.1"}
    timeout = httpx.Timeout(300.0, connect=30.0)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            source_payload = response.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"LorcanaJSON fetch failed: {exc}") from exc

    cards = LorcanaIngestor.extract_cards(source_payload)
    ingestor = _build_ingestor()
    try:
        result = ingestor.ingest_from_payload(cards)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Ingestion failed: {exc}") from exc

    return LorcanaIngestResponse(
        cards_seen=result.cards_seen,
        cards_loaded_sql=result.cards_loaded_sql,
        cards_loaded_graph=result.cards_loaded_graph,
        cards_loaded_vector=result.cards_loaded_vector,
        cards_rejected=result.cards_rejected,
    )


@router.post("/lorcana/lorcast", response_model=LorcanaIngestResponse)
def ingest_lorcana_from_lorcast(payload: LorcastIngestRequest) -> LorcanaIngestResponse:
    try:
        source_payload = fetch_card_search(query=payload.q, unique=payload.unique)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Lorcast fetch failed: {exc}") from exc

    cards = LorcanaIngestor.extract_cards(source_payload)
    ingestor = _build_ingestor()
    try:
        result = ingestor.ingest_from_payload(cards)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Ingestion failed: {exc}") from exc

    return LorcanaIngestResponse(
        cards_seen=result.cards_seen,
        cards_loaded_sql=result.cards_loaded_sql,
        cards_loaded_graph=result.cards_loaded_graph,
        cards_loaded_vector=result.cards_loaded_vector,
        cards_rejected=result.cards_rejected,
    )
