from dataclasses import dataclass

from src.domain.engine.actions import EndTurnAction, GainLoreAction, GameAction
from src.domain.engine.fsm import GameEngineFSM


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


def simulate_simple_match(max_turns: int = 20, target_lore: int = 20) -> MatchResult:
    engine = GameEngineFSM(target_lore=target_lore)
    bot_1 = HeuristicBot()
    bot_2 = HeuristicBot()
    bots = {1: bot_1, 2: bot_2}

    while engine.state.winner_player_id is None and engine.state.turn_number <= max_turns:
        active = engine.state.active_player_id
        legal_actions = engine.get_legal_actions()
        action = bots[active].choose_action(legal_actions)
        engine.apply_action(action)

        if not isinstance(action, EndTurnAction):
            engine.apply_action(EndTurnAction(player_id=active))

    return MatchResult(
        winner_player_id=engine.state.winner_player_id,
        turns_played=engine.state.turn_number,
        history=engine.state.action_log,
    )
