from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.domain.engine.fsm import GameEngineFSM
from src.domain.simulation.determinization import DeterminizationContext
from src.domain.simulation.heuristic_bot import simulate_simple_match
from src.domain.simulation.ismcts import ISMCTSBot

router = APIRouter()


class MatchRequest(BaseModel):
    max_turns: int = Field(default=20, ge=1, le=200)
    target_lore: int = Field(default=20, ge=1, le=40)
    strategy: str = Field(default="heuristic")
    ismcts_iterations: int = Field(default=128, ge=1, le=2000)
    observed_opponent_profile: str = Field(default="balanced")
    observed_avg_cost: float | None = Field(default=None, ge=0.0, le=20.0)
    observed_turns: int = Field(default=1, ge=1, le=40)


class MatchResponse(BaseModel):
    winner_player_id: int | None
    turns_played: int
    history: list[str]


class DecisionRequest(BaseModel):
    target_lore: int = Field(default=20, ge=1, le=40)
    active_player_id: int = Field(default=1, ge=1, le=2)
    player_one_lore: int = Field(default=0, ge=0, le=40)
    player_two_lore: int = Field(default=0, ge=0, le=40)
    ismcts_iterations: int = Field(default=128, ge=1, le=2000)
    observed_opponent_profile: str = Field(default="balanced")
    observed_avg_cost: float | None = Field(default=None, ge=0.0, le=20.0)
    observed_turns: int = Field(default=1, ge=1, le=40)


class DecisionOptionResponse(BaseModel):
    action_type: str
    player_id: int
    amount: int | None
    visits: int
    reward_sum: float
    mean_value: float


class DecisionResponse(BaseModel):
    chosen_action_type: str
    chosen_player_id: int
    chosen_amount: int | None
    total_iterations: int
    options: list[DecisionOptionResponse]


@router.post("/match", response_model=MatchResponse)
def run_match(payload: MatchRequest) -> MatchResponse:
    if payload.strategy not in {"heuristic", "ismcts"}:
        payload.strategy = "heuristic"

    result = simulate_simple_match(
        max_turns=payload.max_turns,
        target_lore=payload.target_lore,
        strategy=payload.strategy,
        ismcts_iterations=payload.ismcts_iterations,
        observed_opponent_profile=payload.observed_opponent_profile,
        observed_avg_cost=payload.observed_avg_cost,
        observed_turns=payload.observed_turns,
    )
    return MatchResponse(
        winner_player_id=result.winner_player_id,
        turns_played=result.turns_played,
        history=result.history,
    )


@router.post("/decision", response_model=DecisionResponse)
def explain_decision(payload: DecisionRequest) -> DecisionResponse:
    engine = GameEngineFSM(target_lore=payload.target_lore)
    engine.state.active_player_id = payload.active_player_id
    engine.state.players[1].lore = payload.player_one_lore
    engine.state.players[2].lore = payload.player_two_lore

    legal_actions = engine.get_legal_actions()
    bot = ISMCTSBot(iterations=payload.ismcts_iterations, rollout_depth=24)
    context = DeterminizationContext(
        root_player_id=payload.active_player_id,
        observed_opponent_profile=payload.observed_opponent_profile,
        observed_avg_cost=payload.observed_avg_cost,
        observed_turns=payload.observed_turns,
    )
    report = bot.evaluate_root(
        engine=engine,
        legal_actions=legal_actions,
        context_override=context,
    )

    chosen = report.chosen_action
    return DecisionResponse(
        chosen_action_type=chosen.action_type,
        chosen_player_id=chosen.player_id,
        chosen_amount=getattr(chosen, "amount", None),
        total_iterations=report.total_iterations,
        options=[
            DecisionOptionResponse(
                action_type=option.action_type,
                player_id=option.player_id,
                amount=option.amount,
                visits=option.visits,
                reward_sum=option.reward_sum,
                mean_value=option.mean_value,
            )
            for option in report.options
        ],
    )
