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


@dataclass(frozen=True)
class DevelopInkAction(GameAction):
    """Represents placing one card into the inkwell (once per turn in MVP model)."""

    def __init__(self, player_id: int):
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "action_type", "develop_ink")


@dataclass(frozen=True)
class PlayCharacterAction(GameAction):
    cost: int = 2
    strength: int = 2
    willpower: int = 2
    lore_value: int = 1
    archetype: str = "balanced"

    def __init__(
        self,
        player_id: int,
        cost: int = 2,
        strength: int = 2,
        willpower: int = 2,
        lore_value: int = 1,
        archetype: str = "balanced",
    ):
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "action_type", "play_character")
        object.__setattr__(self, "cost", cost)
        object.__setattr__(self, "strength", strength)
        object.__setattr__(self, "willpower", willpower)
        object.__setattr__(self, "lore_value", lore_value)
        object.__setattr__(self, "archetype", archetype)


@dataclass(frozen=True)
class QuestAction(GameAction):
    amount: int = 1

    def __init__(self, player_id: int, amount: int = 1):
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "action_type", "quest")
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True)
class SingSongAction(GameAction):
    cost: int = 1
    amount: int = 1
    uses_singer: bool = True

    def __init__(
        self,
        player_id: int,
        cost: int = 1,
        amount: int = 1,
        uses_singer: bool = True,
    ):
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "action_type", "sing_song")
        object.__setattr__(self, "cost", cost)
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "uses_singer", uses_singer)


@dataclass(frozen=True)
class ChallengeAction(GameAction):
    """
    Simplified challenge abstraction:
    one ready character challenges one exerted opposing character chosen by
    ``defender_index`` (index into the opponent's ``battlefield`` list).
    """

    defender_index: int

    def __init__(self, player_id: int, defender_index: int):
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "action_type", "challenge")
        object.__setattr__(self, "defender_index", defender_index)
