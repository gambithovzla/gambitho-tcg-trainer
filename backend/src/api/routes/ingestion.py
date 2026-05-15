from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.infra.db.neo4j.synergy_loader import Neo4jSynergyLoader
from src.infra.db.postgres.card_repository import PostgresCardRepository
from src.infra.db.qdrant.embed_indexer import QdrantEmbedIndexer
from src.infra.ingestion.hybrid_source import fetch_hybrid_raw_cards, merge_hybrid_cards
from src.infra.ingestion.lorcana_ingestor import IngestionSummary, LorcanaIngestor
from src.infra.ingestion.lorcast_client import fetch_card_search

router = APIRouter()

LORCANJSON_DEFAULT_QUERY = "set:1"


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


class HybridIngestRequest(BaseModel):
    language: Literal["en", "fr", "de", "it"] = "en"
    lorcanajson_set_codes: list[str] = Field(default_factory=list)
    lorcast_queries: list[str] = Field(default_factory=lambda: [LORCANJSON_DEFAULT_QUERY])
    include_lorcanajson: bool = True
    include_lorcast: bool = True
    source_precedence: list[Literal["lorcast", "lorcanajson"]] = Field(
        default_factory=lambda: ["lorcast", "lorcanajson"]
    )


class HybridIngestResponse(LorcanaIngestResponse):
    cards_seen_by_source: dict[str, int]
    merged_cards_seen: int


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


@router.post("/lorcana/hybrid", response_model=HybridIngestResponse)
def ingest_lorcana_hybrid(payload: HybridIngestRequest) -> HybridIngestResponse:
    if not payload.include_lorcanajson and not payload.include_lorcast:
        raise HTTPException(status_code=422, detail="At least one source must be enabled.")

    try:
        fetched = fetch_hybrid_raw_cards(
            language=payload.language,
            lorcanajson_set_codes=payload.lorcanajson_set_codes,
            lorcast_queries=payload.lorcast_queries,
            include_lorcanajson=payload.include_lorcanajson,
            include_lorcast=payload.include_lorcast,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Hybrid source fetch failed: {exc}") from exc

    precedence = tuple(payload.source_precedence)
    if sorted(set(precedence)) != ["lorcanajson", "lorcast"]:
        precedence = ("lorcast", "lorcanajson")

    ingestor = _build_ingestor()
    merged_cards, merge_rejected = merge_hybrid_cards(
        ingestor=ingestor,
        raw_cards_by_source=fetched.raw_cards_by_source,
        source_precedence=precedence,
    )
    try:
        result = ingestor.ingest_from_normalized_cards(
            merged_cards,
            cards_seen=sum(fetched.cards_seen_by_source.values()),
            cards_rejected=merge_rejected,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Ingestion failed: {exc}") from exc

    return HybridIngestResponse(
        cards_seen=result.cards_seen,
        cards_loaded_sql=result.cards_loaded_sql,
        cards_loaded_graph=result.cards_loaded_graph,
        cards_loaded_vector=result.cards_loaded_vector,
        cards_rejected=result.cards_rejected,
        cards_seen_by_source=fetched.cards_seen_by_source,
        merged_cards_seen=len(merged_cards),
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
    if payload.resource == "set" and not (payload.set_code and payload.set_code.strip()):
        raise HTTPException(
            status_code=422,
            detail='resource "set" requires non-empty set_code (e.g. "1").',
        )
    try:
        set_codes = [payload.set_code.strip()] if payload.resource == "set" and payload.set_code else []
        fetched = fetch_hybrid_raw_cards(
            language=payload.language,
            lorcanajson_set_codes=set_codes,
            lorcast_queries=[],
            include_lorcanajson=True,
            include_lorcast=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"LorcanaJSON fetch failed: {exc}") from exc

    cards = fetched.raw_cards_by_source["lorcanajson"]
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
