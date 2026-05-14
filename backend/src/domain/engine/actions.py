from dataclasses import dataclass


@dataclass(frozen=True)
class GameAction:
    player_id: int
    action_type: str


@dataclass(frozen=True)
class GainLoreAction(GameAction):
    amount: int = 1

    def __init__(self, player_id: int, amount: int = 1):
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "action_type", "gain_lore")
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True)
class EndTurnAction(GameAction):
    def __init__(self, player_id: int):
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "action_type", "end_turn")
