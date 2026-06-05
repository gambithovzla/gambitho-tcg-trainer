from dataclasses import dataclass

from src.domain.engine.actions import GameAction


@dataclass(frozen=True)
class PlayCardFromHandAction(GameAction):
    hand_index: int
    enter_exerted: bool = False

    def __init__(self, player_id: int, hand_index: int, *, enter_exerted: bool = False):
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "action_type", "play_card")
        object.__setattr__(self, "hand_index", hand_index)
        object.__setattr__(self, "enter_exerted", enter_exerted)


@dataclass(frozen=True)
class InkCardFromHandAction(GameAction):
    hand_index: int

    def __init__(self, player_id: int, hand_index: int):
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "action_type", "ink_card")
        object.__setattr__(self, "hand_index", hand_index)


@dataclass(frozen=True)
class PlayLocationFromHandAction(GameAction):
    hand_index: int

    def __init__(self, player_id: int, hand_index: int):
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "action_type", "play_location")
        object.__setattr__(self, "hand_index", hand_index)


@dataclass(frozen=True)
class PlayItemFromHandAction(GameAction):
    hand_index: int

    def __init__(self, player_id: int, hand_index: int):
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "action_type", "play_item")
        object.__setattr__(self, "hand_index", hand_index)


@dataclass(frozen=True)
class MoveToLocationAction(GameAction):
    character_index: int
    location_index: int

    def __init__(self, player_id: int, character_index: int, location_index: int):
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "action_type", "move_to_location")
        object.__setattr__(self, "character_index", character_index)
        object.__setattr__(self, "location_index", location_index)


@dataclass(frozen=True)
class PlayActionFromHandAction(GameAction):
    hand_index: int

    def __init__(self, player_id: int, hand_index: int):
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "action_type", "play_action")
        object.__setattr__(self, "hand_index", hand_index)


@dataclass(frozen=True)
class SingSongFromHandAction(GameAction):
    hand_index: int
    singer_index: int

    def __init__(self, player_id: int, hand_index: int, singer_index: int):
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "action_type", "sing_song")
        object.__setattr__(self, "hand_index", hand_index)
        object.__setattr__(self, "singer_index", singer_index)
