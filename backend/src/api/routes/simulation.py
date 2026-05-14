from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.domain.simulation.heuristic_bot import simulate_simple_match

router = APIRouter()


class MatchRequest(BaseModel):
    max_turns: int = Field(default=20, ge=1, le=200)
    target_lore: int = Field(default=20, ge=1, le=40)


class MatchResponse(BaseModel):
    winner_player_id: int | None
    turns_played: int
    history: list[str]


@router.post("/match", response_model=MatchResponse)
def run_match(payload: MatchRequest) -> MatchResponse:
    result = simulate_simple_match(
        max_turns=payload.max_turns,
        target_lore=payload.target_lore,
    )
    return MatchResponse(
        winner_player_id=result.winner_player_id,
        turns_played=result.turns_played,
        history=result.history,
    )
