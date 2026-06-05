from __future__ import annotations

import copy
import random
import re
from dataclasses import dataclass

from src.domain.engine.actions import ChallengeAction, EndTurnAction, GameAction, QuestAction
from src.domain.engine.card_model import (
    BagEntry,
    CardDefinition,
    CatalogProvider,
    CharacterInPlay,
    ItemInPlay,
    LocationInPlay,
    RealGameState,
    RealPlayerState,
)
from src.domain.engine.keywords import (
    apply_damage,
    apply_support_on_quest,
    can_quest,
    challenger_bonus,
    apply_damage_to_location,
    legal_challenge_defender_indices,
    legal_challenge_location_indices,
    location_move_cost,
    location_set_step_lore,
    reckless_must_challenge,
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
from src.domain.engine.real_deck import DeckEntry, draw_cards, expand_deck_entries, shuffle_deck
from src.domain.linter.lorcana_linter import LorcanaDeckLinter


@dataclass(frozen=True)
class RealMatchSetup:
    player_one_deck: list[DeckEntry]
    player_two_deck: list[DeckEntry]
    target_lore: int = 20
    starting_player_id: int = 1
    opening_hand_size: int = 7
    rng_seed: int | None = None
    mulligan_no_ink: bool = True


class RealCardGameEngine:
    def __init__(self, catalog: CatalogProvider, setup: RealMatchSetup) -> None:
        if setup.starting_player_id not in (1, 2):
            raise ValueError("starting_player_id must be 1 or 2.")
        self.catalog = catalog
        self.target_lore = setup.target_lore
        self._first_turn_player_id = setup.starting_player_id
        self._rng = random.Random(setup.rng_seed)
        self.state = RealGameState()
        self._load_decks(setup)
        self._opening_hands(setup.opening_hand_size)
        if setup.mulligan_no_ink:
            for player_id in (1, 2):
                self._mulligan_if_no_ink(player_id)
        self.state.active_player_id = setup.starting_player_id
        self._start_turn(self.state.active_player_id)

    def _all_card_ids(self, setup: RealMatchSetup) -> list[str]:
        ids: list[str] = []
        for entries in (setup.player_one_deck, setup.player_two_deck):
            for entry in entries:
                ids.append(entry.card_id)
        return list(dict.fromkeys(ids))

    def _load_decks(self, setup: RealMatchSetup) -> None:
        catalog_cards = self.catalog.get_cards(self._all_card_ids(setup))
        definitions = {
            card_id: CardDefinition.from_catalog(catalog_cards[card_id])
            for card_id in catalog_cards
        }
        missing = [card_id for card_id in self._all_card_ids(setup) if card_id not in definitions]
        if missing:
            raise ValueError(f"Cards not found in catalog: {', '.join(missing[:5])}")

        self.state.definitions = definitions
        self.state.instances = {}

        for player_id, entries in ((1, setup.player_one_deck), (2, setup.player_two_deck)):
            deck_ids, instances = expand_deck_entries(
                entries,
                owner_id=player_id,
                definitions=definitions,
            )
            if len(deck_ids) != LorcanaDeckLinter.DECK_SIZE:
                raise ValueError(
                    f"Player {player_id} deck must have {LorcanaDeckLinter.DECK_SIZE} cards, got {len(deck_ids)}."
                )
            self.state.instances.update(instances)
            shuffled = shuffle_deck(deck_ids, self._rng)
            self.state.players[player_id] = RealPlayerState(player_id=player_id, deck=shuffled)

    def _opening_hands(self, hand_size: int) -> None:
        for player_id in (1, 2):
            player = self.state.players[player_id]
            draw_cards(player.deck, player.hand, hand_size)
            self.state.action_log.append(
                f"P{player_id} opening hand: {hand_size} cards (deck={len(player.deck)})."
            )

    def _hand_has_inkable(self, player: RealPlayerState) -> bool:
        return any(
            self._definition_for_instance(instance_id).inkwell_inkable
            for instance_id in player.hand
        )

    def _mulligan_if_no_ink(self, player_id: int) -> None:
        player = self.state.players[player_id]
        if self._hand_has_inkable(player):
            return
        returned = len(player.hand)
        while player.hand:
            player.deck.insert(0, player.hand.pop())
        player.deck = shuffle_deck(player.deck, self._rng)
        draw_cards(player.deck, player.hand, 7)
        self.state.action_log.append(
            f"P{player_id} mulligan (no inkable): returned {returned}, new hand={len(player.hand)}."
        )

    def get_legal_actions(self) -> list[GameAction]:
        active = self.state.active_player_id
        player = self.state.players[active]
        legal: list[GameAction] = []

        if self.state.phase != "main":
            return legal

        if not player.inked_this_turn:
            for index, instance_id in enumerate(player.hand):
                definition = self._definition_for_instance(instance_id)
                if definition.inkwell_inkable:
                    legal.append(InkCardFromHandAction(player_id=active, hand_index=index))

        for index, instance_id in enumerate(player.hand):
            definition = self._definition_for_instance(instance_id)
            if definition.card_type == "Character" and self._can_pay_cost(player, definition.cost):
                legal.append(
                    PlayCardFromHandAction(player_id=active, hand_index=index, enter_exerted=False)
                )
                if definition.has_keyword("Bodyguard"):
                    legal.append(
                        PlayCardFromHandAction(
                            player_id=active, hand_index=index, enter_exerted=True
                        )
                    )
            elif definition.card_type == "Location" and self._can_pay_cost(player, definition.cost):
                legal.append(PlayLocationFromHandAction(player_id=active, hand_index=index))
            elif definition.card_type == "Item" and self._can_pay_cost(player, definition.cost):
                legal.append(PlayItemFromHandAction(player_id=active, hand_index=index))
            elif definition.card_type == "Action" and self._can_pay_cost(player, definition.cost):
                legal.append(PlayActionFromHandAction(player_id=active, hand_index=index))
            elif definition.card_type == "Song":
                for singer_index, singer in enumerate(player.battlefield):
                    if not singer.is_ready_for_quest:
                        continue
                    legal.append(
                        SingSongFromHandAction(
                            player_id=active,
                            hand_index=index,
                            singer_index=singer_index,
                        )
                    )
                if self._can_pay_cost(player, definition.cost):
                    legal.append(
                        SingSongFromHandAction(
                            player_id=active,
                            hand_index=index,
                            singer_index=-1,
                        )
                    )

        opponent_id = 2 if active == 1 else 1
        opponent = self.state.players[opponent_id]
        must_challenge = reckless_must_challenge(
            player.battlefield, opponent.battlefield, opponent.locations
        )

        for character_index, character in enumerate(player.battlefield):
            if character.is_banished:
                continue
            for location_index, location in enumerate(player.locations):
                if location.is_banished:
                    continue
                if character.at_location_index == location_index:
                    continue
                move_cost = location_move_cost(location.definition)
                if not self._can_pay_cost(player, move_cost):
                    continue
                legal.append(
                    MoveToLocationAction(
                        player_id=active,
                        character_index=character_index,
                        location_index=location_index,
                    )
                )

        if self._find_ready_quester(player) is not None and not must_challenge:
            legal.append(QuestAction(player_id=active, amount=1))

        for attacker_index, attacker in enumerate(player.battlefield):
            if not attacker.is_ready_for_quest:
                continue
            for defender_index in legal_challenge_defender_indices(
                attacker, opponent.battlefield
            ):
                defender = opponent.battlefield[defender_index]
                legal.append(
                    ChallengeAction(
                        player_id=active,
                        defender_index=defender_index,
                        defender_strength=defender.strength,
                        defender_willpower=defender.willpower,
                        defender_lore_value=defender.lore_value,
                        attacker_index=attacker_index,
                        defender_kind="character",
                    )
                )
            for location_index in legal_challenge_location_indices(opponent.locations):
                location = opponent.locations[location_index]
                legal.append(
                    ChallengeAction(
                        player_id=active,
                        defender_index=location_index,
                        defender_willpower=location.willpower,
                        defender_lore_value=location.lore_value,
                        attacker_index=attacker_index,
                        defender_kind="location",
                    )
                )

        if not must_challenge:
            legal.append(EndTurnAction(player_id=active))
        return legal

    def apply_action(self, action: GameAction) -> None:
        if self.state.winner_player_id is not None:
            return
        if action.player_id != self.state.active_player_id:
            return
        if not self._is_action_legal(action):
            self.state.action_log.append(
                f"P{action.player_id} illegal '{action.action_type}' rejected."
            )
            return

        if isinstance(action, InkCardFromHandAction):
            self._ink_from_hand(action.player_id, action.hand_index)
        elif isinstance(action, PlayCardFromHandAction):
            self._play_character_from_hand(
                action.player_id, action.hand_index, enter_exerted=action.enter_exerted
            )
        elif isinstance(action, PlayLocationFromHandAction):
            self._play_location_from_hand(action.player_id, action.hand_index)
        elif isinstance(action, MoveToLocationAction):
            self._move_to_location(
                action.player_id, action.character_index, action.location_index
            )
        elif isinstance(action, PlayItemFromHandAction):
            self._play_item_from_hand(action.player_id, action.hand_index)
        elif isinstance(action, PlayActionFromHandAction):
            self._play_action_from_hand(action.player_id, action.hand_index)
        elif isinstance(action, SingSongFromHandAction):
            self._sing_song_from_hand(
                action.player_id,
                action.hand_index,
                action.singer_index,
            )
        elif isinstance(action, QuestAction):
            self._quest(action.player_id, action.amount)
        elif isinstance(action, ChallengeAction):
            self._challenge(action)
        elif isinstance(action, EndTurnAction):
            self._end_turn(action.player_id)
        self._resolve_bag()

    def _ink_from_hand(self, player_id: int, hand_index: int) -> None:
        player = self.state.players[player_id]
        instance_id = self._hand_card(player, hand_index)
        if instance_id is None:
            return
        definition = self._definition_for_instance(instance_id)
        if not definition.inkwell_inkable:
            return
        player.hand.pop(hand_index)
        player.ink_total += 1
        player.ink_available += 1
        player.inked_this_turn = True
        self.state.action_log.append(
            f"P{player_id} inks {definition.name} ({definition.card_id})."
        )

    def _play_character_from_hand(
        self, player_id: int, hand_index: int, *, enter_exerted: bool = False
    ) -> None:
        player = self.state.players[player_id]
        instance_id = self._hand_card(player, hand_index)
        if instance_id is None:
            return
        instance = self.state.instances[instance_id]
        definition = self.state.definitions[instance.card_id]
        if definition.card_type != "Character":
            return
        if enter_exerted and not definition.has_keyword("Bodyguard"):
            return
        if not self._spend_ink(player, definition.cost):
            return

        player.hand.pop(hand_index)
        keywords = definition.keywords
        character = CharacterInPlay(
            instance=instance,
            definition=definition,
            summoning_sick=not definition.has_keyword("Rush"),
            exerted=enter_exerted,
        )
        player.battlefield.append(character)
        exerted_note = ", enters exerted (Bodyguard choice)" if enter_exerted else ""
        self.state.action_log.append(
            f"P{player_id} plays {definition.name} ({definition.strength}/{definition.willpower}, "
            f"lore={definition.lore}, keywords={','.join(sorted(keywords)) or 'none'}{exerted_note})."
        )

    def _play_location_from_hand(self, player_id: int, hand_index: int) -> None:
        player = self.state.players[player_id]
        instance_id = self._hand_card(player, hand_index)
        if instance_id is None:
            return
        instance = self.state.instances[instance_id]
        definition = self.state.definitions[instance.card_id]
        if definition.card_type != "Location":
            return
        if not self._spend_ink(player, definition.cost):
            return

        player.hand.pop(hand_index)
        location = LocationInPlay(instance=instance, definition=definition)
        player.locations.append(location)
        self.state.action_log.append(
            f"P{player_id} plays location {definition.name} "
            f"(lore={definition.lore}, willpower={definition.willpower})."
        )

    def _play_item_from_hand(self, player_id: int, hand_index: int) -> None:
        player = self.state.players[player_id]
        instance_id = self._hand_card(player, hand_index)
        if instance_id is None:
            return
        instance = self.state.instances[instance_id]
        definition = self.state.definitions[instance.card_id]
        if definition.card_type != "Item":
            return
        if not self._spend_ink(player, definition.cost):
            return

        player.hand.pop(hand_index)
        player.items.append(ItemInPlay(instance=instance, definition=definition))
        self.state.action_log.append(
            f"P{player_id} plays item {definition.name} (cost={definition.cost})."
        )
        self._queue_item_play_effects(player_id, definition)

    def _play_action_from_hand(self, player_id: int, hand_index: int) -> None:
        player = self.state.players[player_id]
        instance_id = self._hand_card(player, hand_index)
        if instance_id is None:
            return
        definition = self._definition_for_instance(instance_id)
        if definition.card_type != "Action":
            return
        if not self._spend_ink(player, definition.cost):
            return

        player.hand.pop(hand_index)
        player.discard.append(instance_id)
        if definition.lore and definition.lore > 0:
            self._push_bag(
                effect_type="gain_lore",
                player_id=player_id,
                payload={"amount": definition.lore, "source": definition.name},
            )
        self._queue_rules_text_effects(
            player_id=player_id,
            definition=definition,
            requires_when_play=False,
        )
        self.state.action_log.append(
            f"P{player_id} casts {definition.name}."
        )

    def _sing_song_from_hand(self, player_id: int, hand_index: int, singer_index: int) -> None:
        player = self.state.players[player_id]
        instance_id = self._hand_card(player, hand_index)
        if instance_id is None:
            return
        definition = self._definition_for_instance(instance_id)
        if definition.card_type != "Song":
            return

        if singer_index >= 0:
            if singer_index >= len(player.battlefield):
                return
            singer = player.battlefield[singer_index]
            if not singer.is_ready_for_quest:
                return
            singer.exerted = True
        elif not self._spend_ink(player, definition.cost):
            return

        player.hand.pop(hand_index)
        player.discard.append(instance_id)
        lore_gain = max(1, definition.lore or 0)
        player.lore += lore_gain
        mode = "with singer" if singer_index >= 0 else f"paying {definition.cost} ink"
        self.state.action_log.append(
            f"P{player_id} sings {definition.name} {mode} for {lore_gain} lore (total={player.lore})."
        )
        self._check_win()

    def _quest(self, player_id: int, amount: int) -> None:
        player = self.state.players[player_id]
        quester = self._find_ready_quester(player)
        if quester is None or not can_quest(quester):
            return
        quester.exerted = True
        support_target = apply_support_on_quest(quester, player.battlefield)
        lore_gained = max(1, quester.lore_value) * max(1, amount)
        player.lore += lore_gained
        support_note = ""
        if support_target is not None:
            ally = player.battlefield[support_target]
            support_note = f", Support → {ally.definition.name} (+{quester.strength}¤)"
        self.state.action_log.append(
            f"P{player_id} quests with {quester.definition.name} for {lore_gained} lore"
            f"{support_note} (total={player.lore})."
        )
        self._check_win()

    def _apply_location_set_step_lore(self, player_id: int) -> None:
        """CR 4.2.2.2 / 6.5.6 — lore from locations at Set step via Bag."""
        player = self.state.players[player_id]
        for location in player.locations:
            if location.is_banished:
                continue
            amount = location_set_step_lore(location.definition.lore)
            if amount <= 0:
                continue
            self._push_bag(
                effect_type="location_set_lore",
                player_id=player_id,
                payload={
                    "amount": amount,
                    "source": location.definition.name,
                },
            )
        self._resolve_bag()

    def _queue_item_play_effects(self, player_id: int, definition: CardDefinition) -> None:
        self._queue_rules_text_effects(
            player_id=player_id,
            definition=definition,
            requires_when_play=True,
        )

    def _queue_rules_text_effects(
        self,
        *,
        player_id: int,
        definition: CardDefinition,
        requires_when_play: bool,
    ) -> None:
        rules_text = definition.rules_text or ""
        if requires_when_play and "when you play" not in rules_text.lower():
            return

        effects: list[tuple[int, str, int]] = []
        for match in re.finditer(r"gain\s+(\d+)\s+lore", rules_text, flags=re.IGNORECASE):
            effects.append((match.start(), "gain_lore", int(match.group(1))))
        for match in re.finditer(r"draw\s+(a|an|\d+)\s+cards?", rules_text, flags=re.IGNORECASE):
            raw_amount = match.group(1).lower()
            amount = 1 if raw_amount in {"a", "an"} else int(raw_amount)
            effects.append((match.start(), "draw_card", amount))

        for _, effect_type, amount in sorted(effects, key=lambda item: item[0]):
            self._push_bag(
                effect_type=effect_type,
                player_id=player_id,
                payload={"amount": amount, "source": definition.name},
            )

    def _push_bag(self, *, effect_type: str, player_id: int, payload: dict[str, object]) -> None:
        self.state.bag.append(BagEntry(effect_type=effect_type, player_id=player_id, payload=payload))
        source = payload.get("source")
        source_note = f" ({source})" if source else ""
        self.state.action_log.append(f"Bag push: {effect_type}{source_note}.")

    def _resolve_bag(self) -> None:
        while self.state.bag:
            entry = self.state.bag.pop()
            source = entry.payload.get("source")
            source_note = f" ({source})" if source else ""
            self.state.action_log.append(f"Bag resolve: {entry.effect_type}{source_note}.")
            if entry.effect_type in {"gain_lore", "location_set_lore"}:
                self._resolve_gain_lore(entry)
            elif entry.effect_type == "draw_card":
                self._resolve_draw_card(entry)

    def _resolve_gain_lore(self, entry: BagEntry) -> None:
        player = self.state.players[entry.player_id]
        amount = max(0, int(entry.payload.get("amount", 0)))
        if amount <= 0:
            return
        player.lore += amount
        source = entry.payload.get("source") or "effect"
        self.state.action_log.append(
            f"P{entry.player_id} gains {amount} lore from {source} (total={player.lore})."
        )
        self._check_win()

    def _resolve_draw_card(self, entry: BagEntry) -> None:
        player = self.state.players[entry.player_id]
        amount = max(0, int(entry.payload.get("amount", 0)))
        if amount <= 0 or not player.deck:
            return
        draw_cards(player.deck, player.hand, amount)
        source = entry.payload.get("source") or "effect"
        self.state.action_log.append(
            f"P{entry.player_id} draws {amount} from {source} (hand={len(player.hand)})."
        )

    def _move_to_location(
        self, player_id: int, character_index: int, location_index: int
    ) -> None:
        player = self.state.players[player_id]
        if character_index < 0 or character_index >= len(player.battlefield):
            return
        if location_index < 0 or location_index >= len(player.locations):
            return
        character = player.battlefield[character_index]
        location = player.locations[location_index]
        if character.is_banished or location.is_banished:
            return
        if character.at_location_index == location_index:
            return
        move_cost = location_move_cost(location.definition)
        if not self._spend_ink(player, move_cost):
            return
        character.at_location_index = location_index
        self.state.action_log.append(
            f"P{player_id} moves {character.definition.name} to {location.definition.name} "
            f"(move cost {move_cost})."
        )

    def _detach_characters_from_location(self, player: RealPlayerState, location_index: int) -> None:
        for character in player.battlefield:
            if character.at_location_index == location_index:
                character.at_location_index = None

    def _remove_banished_location(self, player: RealPlayerState, location: LocationInPlay) -> None:
        if location not in player.locations:
            return
        index = player.locations.index(location)
        self._detach_characters_from_location(player, index)
        player.locations.remove(location)
        for character in player.battlefield:
            if character.at_location_index is not None and character.at_location_index > index:
                character.at_location_index -= 1

    def _challenge(self, action: ChallengeAction) -> None:
        if action.defender_kind == "location":
            self._challenge_location(action)
        else:
            self._challenge_character(action)

    def _challenge_character(self, action: ChallengeAction) -> None:
        player = self.state.players[action.player_id]
        opponent_id = 2 if action.player_id == 1 else 1
        opponent = self.state.players[opponent_id]
        attacker = self._resolve_attacker(player, action.attacker_index)
        if attacker is None:
            return
        if action.defender_index < 0 or action.defender_index >= len(opponent.battlefield):
            return
        defender = opponent.battlefield[action.defender_index]
        legal_targets = legal_challenge_defender_indices(attacker, opponent.battlefield)
        if action.defender_index not in legal_targets:
            self.state.action_log.append(
                f"P{action.player_id} cannot challenge {defender.definition.name} "
                f"(illegal target)."
            )
            return

        attacker.exerted = True
        attack_power = attacker.strength + challenger_bonus(
            attacker.definition.rules_text,
            attacker.definition.keywords,
        )
        dealt_to_defender = apply_damage(defender, attack_power)
        dealt_to_attacker = apply_damage(attacker, defender.strength)
        self.state.action_log.append(
            f"P{action.player_id} {attacker.definition.name} challenges "
            f"P{opponent_id} {defender.definition.name} "
            f"({dealt_to_defender} to defender, {dealt_to_attacker} to attacker)."
        )
        if attacker.is_banished:
            player.battlefield.remove(attacker)
            self.state.action_log.append(f"{attacker.definition.name} banished.")
        if defender.is_banished:
            opponent.battlefield.remove(defender)
            self.state.action_log.append(f"{defender.definition.name} banished.")

    def _challenge_location(self, action: ChallengeAction) -> None:
        player = self.state.players[action.player_id]
        opponent_id = 2 if action.player_id == 1 else 1
        opponent = self.state.players[opponent_id]
        attacker = self._resolve_attacker(player, action.attacker_index)
        if attacker is None:
            return
        if action.defender_index < 0 or action.defender_index >= len(opponent.locations):
            return
        location = opponent.locations[action.defender_index]
        legal_targets = legal_challenge_location_indices(opponent.locations)
        if action.defender_index not in legal_targets:
            self.state.action_log.append(
                f"P{action.player_id} cannot challenge location {location.definition.name}."
            )
            return

        attacker.exerted = True
        attack_power = attacker.strength + challenger_bonus(
            attacker.definition.rules_text,
            attacker.definition.keywords,
        )
        dealt = apply_damage_to_location(location, attack_power)
        self.state.action_log.append(
            f"P{action.player_id} {attacker.definition.name} challenges location "
            f"{location.definition.name} ({dealt} damage, location deals 0 back)."
        )
        if location.is_banished:
            self._remove_banished_location(opponent, location)
            self.state.action_log.append(f"{location.definition.name} banished.")

    def _end_turn(self, player_id: int) -> None:
        self.state.action_log.append(f"P{player_id} ends turn.")
        self.state.total_turns_taken += 1
        self.state.active_player_id = 2 if player_id == 1 else 1
        self.state.turn_number += 1
        self._start_turn(self.state.active_player_id)

    def _start_turn(self, player_id: int) -> None:
        player = self.state.players[player_id]
        for character in player.battlefield:
            character.exerted = False
            character.summoning_sick = False
            character.strength_bonus_this_turn = 0
        self._apply_location_set_step_lore(player_id)
        player.inked_this_turn = False
        player.ink_available = player.ink_total

        should_draw = not (self.state.turn_number == 1 and player_id == self._first_turn_player_id)
        if should_draw and player.deck:
            draw_cards(player.deck, player.hand, 1)
            self.state.action_log.append(f"P{player_id} draws 1 (hand={len(player.hand)}).")
        elif should_draw and not player.deck:
            self.state.action_log.append(f"P{player_id} cannot draw (deck empty).")

        self.state.phase = "main"
        self.state.action_log.append(f"Main phase P{player_id} turn {self.state.turn_number}.")

    def _check_win(self) -> None:
        for player_id, player in self.state.players.items():
            if player.lore >= self.target_lore:
                self.state.winner_player_id = player_id
                self.state.action_log.append(f"P{player_id} wins at {player.lore} lore.")

    def _definition_for_instance(self, instance_id: str) -> CardDefinition:
        instance = self.state.instances[instance_id]
        return self.state.definitions[instance.card_id]

    @staticmethod
    def _hand_card(player: RealPlayerState, hand_index: int) -> str | None:
        if hand_index < 0 or hand_index >= len(player.hand):
            return None
        return player.hand[hand_index]

    @staticmethod
    def _can_pay_cost(player: RealPlayerState, cost: int) -> bool:
        return player.ink_available >= max(0, cost)

    @staticmethod
    def _spend_ink(player: RealPlayerState, cost: int) -> bool:
        if player.ink_available < cost:
            return False
        player.ink_available -= cost
        return True

    @staticmethod
    def _find_ready_quester(player: RealPlayerState) -> CharacterInPlay | None:
        for character in player.battlefield:
            if character.is_ready_for_quest and can_quest(character):
                return character
        return None

    @staticmethod
    def _resolve_attacker(
        player: RealPlayerState, attacker_index: int
    ) -> CharacterInPlay | None:
        if attacker_index >= 0:
            if attacker_index >= len(player.battlefield):
                return None
            attacker = player.battlefield[attacker_index]
            if not attacker.is_ready_for_quest:
                return None
            return attacker
        for character in player.battlefield:
            if character.is_ready_for_quest:
                return character
        return None

    def _is_action_legal(self, action: GameAction) -> bool:
        signature = self._action_signature(action)
        return any(self._action_signature(item) == signature for item in self.get_legal_actions())

    @staticmethod
    def _action_signature(action: GameAction) -> tuple[str, tuple[tuple[str, object], ...]]:
        if isinstance(action, ChallengeAction):
            payload = (
                ("attacker_index", action.attacker_index),
                ("defender_index", action.defender_index),
                ("defender_kind", action.defender_kind),
                ("player_id", action.player_id),
            )
            return action.action_type, payload
        if isinstance(action, MoveToLocationAction):
            payload = (
                ("character_index", action.character_index),
                ("location_index", action.location_index),
                ("player_id", action.player_id),
            )
            return action.action_type, payload
        if isinstance(action, SingSongFromHandAction):
            payload = (
                ("hand_index", action.hand_index),
                ("player_id", action.player_id),
                ("singer_index", action.singer_index),
            )
            return action.action_type, payload
        if isinstance(action, PlayCardFromHandAction):
            payload = (
                ("enter_exerted", action.enter_exerted),
                ("hand_index", action.hand_index),
                ("player_id", action.player_id),
            )
            return action.action_type, payload
        if isinstance(
            action,
            (
                PlayActionFromHandAction,
                PlayLocationFromHandAction,
                PlayItemFromHandAction,
                InkCardFromHandAction,
            ),
        ):
            payload = (("hand_index", action.hand_index), ("player_id", action.player_id))
            return action.action_type, payload
        payload = tuple(sorted(vars(action).items()))
        return action.action_type, payload

    def clone(self) -> RealCardGameEngine:
        cloned = object.__new__(RealCardGameEngine)
        cloned.catalog = self.catalog
        cloned.target_lore = self.target_lore
        cloned._first_turn_player_id = self._first_turn_player_id
        cloned._rng = random.Random()
        cloned.state = copy.deepcopy(self.state)
        return cloned
