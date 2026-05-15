from dataclasses import dataclass

from src.domain.engine.actions import EndTurnAction, GainLoreAction, GameAction
from src.domain.engine.fsm import GameEngineFSM
from src.domain.simulation.determinization import DeterminizationContext
from src.domain.simulation.ismcts import ISMCTSBot


@dataclass
class MatchResult:
    winner_player_id: int | None
    turns_played: int
    history: list[str]


class HeuristicBot:
    """Simple policy: gain lore, then end turn."""

    def choose_action(self, legal_actions: list[GameAction]) -> GameAction:
        for action in legal_actions:
            if isinstance(action, GainLoreAction):
                return action
        for action in legal_actions:
            if isinstance(action, EndTurnAction):
                return action
        return legal_actions[0]


def _build_bot(strategy: str, ismcts_iterations: int):
    if strategy == "ismcts":
        return ISMCTSBot(iterations=ismcts_iterations, rollout_depth=24)
    return HeuristicBot()


def simulate_simple_match(
    max_turns: int = 20,
    target_lore: int = 20,
    strategy: str = "heuristic",
    ismcts_iterations: int = 128,
    observed_opponent_profile: str = "balanced",
    observed_avg_cost: float | None = None,
    observed_turns: int = 1,
) -> MatchResult:
    engine = GameEngineFSM(target_lore=target_lore)
    bot_1 = _build_bot(strategy=strategy, ismcts_iterations=ismcts_iterations)
    bot_2 = _build_bot(strategy=strategy, ismcts_iterations=ismcts_iterations)
    bots = {1: bot_1, 2: bot_2}

    while engine.state.winner_player_id is None and engine.state.turn_number <= max_turns:
        active = engine.state.active_player_id
        legal_actions = engine.get_legal_actions()
        bot = bots[active]
        if isinstance(bot, ISMCTSBot):
            context = DeterminizationContext(
                root_player_id=active,
                observed_opponent_profile=observed_opponent_profile,
                observed_avg_cost=observed_avg_cost,
                observed_turns=max(1, observed_turns),
            )
            action = bot.choose_action(
                engine=engine,
                legal_actions=legal_actions,
                context_override=context,
            )
        else:
            action = bot.choose_action(legal_actions)
        engine.apply_action(action)

        if not isinstance(action, EndTurnAction):
            engine.apply_action(EndTurnAction(player_id=active))

    return MatchResult(
        winner_player_id=engine.state.winner_player_id,
        turns_played=engine.state.turn_number,
        history=engine.state.action_log,
    )
