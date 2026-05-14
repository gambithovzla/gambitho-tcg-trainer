from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.infra.db.neo4j.synergy_loader import Neo4jSynergyLoader
from src.infra.db.postgres.card_repository import PostgresCardRepository
from src.infra.db.qdrant.embed_indexer import QdrantEmbedIndexer
from src.infra.ingestion.lorcana_ingestor import IngestionSummary, LorcanaIngestor

router = APIRouter()


class LorcanaIngestRequest(BaseModel):
    cards: list[dict[str, Any]] = Field(default_factory=list)


class LorcanaIngestResponse(BaseModel):
    cards_seen: int
    cards_loaded_sql: int
    cards_loaded_graph: int
    cards_loaded_vector: int
    cards_rejected: int


@router.post("/lorcana", response_model=LorcanaIngestResponse)
def ingest_lorcana(payload: LorcanaIngestRequest) -> LorcanaIngestResponse:
    ingestor = LorcanaIngestor(
        card_repository=PostgresCardRepository(),
        graph_loader=Neo4jSynergyLoader(),
        embed_indexer=QdrantEmbedIndexer(),
    )
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
