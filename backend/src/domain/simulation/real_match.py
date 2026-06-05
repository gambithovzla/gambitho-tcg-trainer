from __future__ import annotations

from dataclasses import dataclass

from src.domain.engine.card_model import CatalogProvider
from src.domain.engine.real_deck import DeckEntry
from src.domain.engine.real_fsm import RealCardGameEngine, RealMatchSetup
@dataclass
class RealMatchResult:
    winner_player_id: int | None
    turns_played: int
    history: list[str]
    starting_player_id: int
    engine_mode: str
    turn_protocol_version: str
    cards_referenced: list[str]


class RealHeuristicBot:
    """Greedy policy for real-card actions."""

    def choose_action(self, legal_actions: list):
        from src.domain.engine.actions import (
            ChallengeAction,
            EndTurnAction,
            QuestAction,
        )
        from src.domain.engine.real_actions import (
            InkCardFromHandAction,
            PlayActionFromHandAction,
            PlayCardFromHandAction,
            PlayItemFromHandAction,
            MoveToLocationAction,
            PlayLocationFromHandAction,
            SingSongFromHandAction,
        )

        for action in legal_actions:
            if isinstance(action, InkCardFromHandAction):
                return action

        song_options = [a for a in legal_actions if isinstance(a, SingSongFromHandAction)]
        if song_options:
            return song_options[0]

        action_cards = [a for a in legal_actions if isinstance(a, PlayActionFromHandAction)]
        if action_cards:
            return action_cards[0]

        play_options = [a for a in legal_actions if isinstance(a, PlayCardFromHandAction)]
        if play_options:
            return play_options[0]

        location_options = [a for a in legal_actions if isinstance(a, PlayLocationFromHandAction)]
        if location_options:
            return location_options[0]

        move_options = [a for a in legal_actions if isinstance(a, MoveToLocationAction)]
        if move_options:
            return move_options[0]

        item_options = [a for a in legal_actions if isinstance(a, PlayItemFromHandAction)]
        if item_options:
            return item_options[0]

        challenges = [a for a in legal_actions if isinstance(a, ChallengeAction)]
        if challenges:
            return max(
                challenges,
                key=lambda item: (
                    3 * max(0, item.defender_lore_value or 0)
                    + max(0, item.defender_strength or 0)
                    - max(0, item.defender_willpower or 0)
                    + (2 if item.defender_kind == "location" else 0)
                ),
            )

        for action in legal_actions:
            if isinstance(action, QuestAction):
                return action

        for action in legal_actions:
            if isinstance(action, EndTurnAction):
                return action

        return legal_actions[0]


def simulate_real_card_match(
    *,
    catalog: CatalogProvider,
    player_one_deck: list[DeckEntry],
    player_two_deck: list[DeckEntry],
    max_turns: int = 20,
    target_lore: int = 20,
    rng_seed: int | None = None,
    starting_player_id: int = 1,
) -> RealMatchResult:
    setup = RealMatchSetup(
        player_one_deck=player_one_deck,
        player_two_deck=player_two_deck,
        target_lore=target_lore,
        starting_player_id=starting_player_id,
        rng_seed=rng_seed,
    )
    engine = RealCardGameEngine(catalog=catalog, setup=setup)
    bot = RealHeuristicBot()
    bots = {1: bot, 2: bot}

    while engine.state.winner_player_id is None and engine.state.turn_number <= max_turns:
        active = engine.state.active_player_id
        legal = engine.get_legal_actions()
        if not legal:
            break
        action = bots[active].choose_action(legal)
        engine.apply_action(action)

    cards_referenced: list[str] = []
    seen: set[str] = set()
    for line in engine.state.action_log:
        marker = None
        for token in (
            " plays ",
            " plays location ",
            " plays item ",
            " moves ",
            " casts ",
            " sings ",
            " Set step: ",
            " challenges location ",
        ):
            if token in line:
                marker = token
                break
        if marker is None:
            continue
        fragment = line.split(marker, 1)[1]
        name = fragment.split(" (", 1)[0].split(" +", 1)[0].split(" for ", 1)[0].strip()
        if name and name not in seen:
            seen.add(name)
            cards_referenced.append(name)

    return RealMatchResult(
        winner_player_id=engine.state.winner_player_id,
        turns_played=engine.state.turn_number,
        history=engine.state.action_log,
        starting_player_id=starting_player_id,
        engine_mode=engine.state.engine_mode,
        turn_protocol_version=engine.state.turn_protocol_version,
        cards_referenced=cards_referenced,
    )
