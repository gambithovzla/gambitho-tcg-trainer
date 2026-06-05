import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.domain.engine.real_deck import DeckEntry
from src.domain.simulation.real_match import RealMatchResult, simulate_real_card_match
from src.infra.db.postgres.catalog_provider import PostgresCatalogProvider

router = APIRouter()


def _catalog_fallback_mode() -> str:
    value = os.getenv("CATALOG_FALLBACK_MODE", "degraded").strip().lower()
    if value not in {"degraded", "strict"}:
        return "degraded"
    return value


class RealDeckCardInput(BaseModel):
    card_id: str = Field(..., min_length=1)
    copies: int = Field(default=1, ge=1, le=4)


class RealMatchRequest(BaseModel):
    player_one_deck: list[RealDeckCardInput] = Field(..., min_length=1)
    player_two_deck: list[RealDeckCardInput] = Field(..., min_length=1)
    max_turns: int = Field(default=20, ge=1, le=200)
    target_lore: int = Field(default=20, ge=1, le=40)
    rng_seed: int | None = None
    starting_player_id: int = Field(default=1, ge=1, le=2)


class RealMatchResponse(BaseModel):
    winner_player_id: int | None
    turns_played: int
    history: list[str]
    starting_player_id: int
    engine_mode: str
    turn_protocol_version: str
    cards_referenced: list[str]


def _to_deck_entries(cards: list[RealDeckCardInput]) -> list[DeckEntry]:
    return [DeckEntry(card_id=item.card_id, copies=item.copies) for item in cards]


def _to_response(result: RealMatchResult) -> RealMatchResponse:
    return RealMatchResponse(
        winner_player_id=result.winner_player_id,
        turns_played=result.turns_played,
        history=result.history,
        starting_player_id=result.starting_player_id,
        engine_mode=result.engine_mode,
        turn_protocol_version=result.turn_protocol_version,
        cards_referenced=result.cards_referenced,
    )


@router.post("/match/real", response_model=RealMatchResponse)
def run_real_match(payload: RealMatchRequest) -> RealMatchResponse:
    try:
        catalog = PostgresCatalogProvider()
        result = simulate_real_card_match(
            catalog=catalog,
            player_one_deck=_to_deck_entries(payload.player_one_deck),
            player_two_deck=_to_deck_entries(payload.player_two_deck),
            max_turns=payload.max_turns,
            target_lore=payload.target_lore,
            rng_seed=payload.rng_seed,
            starting_player_id=payload.starting_player_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        if _catalog_fallback_mode() == "strict":
            raise HTTPException(status_code=503, detail=f"Real match failed: {exc}") from exc
        raise HTTPException(status_code=503, detail=f"Real match failed: {exc}") from exc
    return _to_response(result)
