from dataclasses import dataclass, field
import copy

from src.domain.engine.actions import (
    ChallengeAction,
    DevelopInkAction,
    EndTurnAction,
    GameAction,
    PlayCharacterAction,
    QuestAction,
    SingSongAction,
)
from src.domain.engine.the_bag import TheBag, TriggerEvent


@dataclass
class CharacterInPlay:
    strength: int = 2
    willpower: int = 2
    lore_value: int = 1
    damage: int = 0
    exerted: bool = False
    summoning_sick: bool = True

    @property
    def is_banished(self) -> bool:
        return self.damage >= self.willpower

    @property
    def is_ready_for_actions(self) -> bool:
        return not self.exerted and not self.summoning_sick


@dataclass
class PlayerState:
    player_id: int
    lore: int = 0
    hidden_hand_size: int = 0
    hidden_combo_potential: float = 0.0
    hand_intents: list[str] = field(default_factory=list)
    hand_size: int = 7
    deck_size: int = 53
    battlefield: list[CharacterInPlay] = field(default_factory=list)
    board_ready_characters: int = 0
    board_exerted_characters: int = 0
    board_fresh_characters: int = 0
    ink_total: int = 0
    ink_available: int = 0
    ink_played_this_turn: bool = False


@dataclass
class GameState:
    active_player_id: int = 1
    turn_number: int = 1
    phase: str = "main"
    total_turns_taken: int = 0
    players: dict[int, PlayerState] = field(
        default_factory=lambda: {
            1: PlayerState(player_id=1),
            2: PlayerState(player_id=2),
        }
    )
    action_log: list[str] = field(default_factory=list)
    winner_player_id: int | None = None
    turn_protocol_version: str = "1"


class GameEngineFSM:
    INTENT_KEYS: tuple[str, ...] = ("tempo", "aggressive", "quester", "defender", "song")
    DEFAULT_INTENT_WEIGHTS: dict[str, float] = {
        "tempo": 0.30,
        "aggressive": 0.20,
        "quester": 0.20,
        "defender": 0.15,
        "song": 0.15,
    }
    CHARACTER_TEMPLATES: tuple[dict[str, int | str], ...] = (
        {"archetype": "tempo", "cost": 2, "strength": 2, "willpower": 2, "lore_value": 1},
        {"archetype": "aggressive", "cost": 3, "strength": 3, "willpower": 2, "lore_value": 1},
        {"archetype": "quester", "cost": 3, "strength": 2, "willpower": 3, "lore_value": 2},
        {"archetype": "defender", "cost": 4, "strength": 2, "willpower": 4, "lore_value": 1},
    )

    def __init__(
        self,
        target_lore: int = 20,
        intent_weights_by_player: dict[int, dict[str, float]] | None = None,
        starting_player_id: int = 1,
    ) -> None:
        if starting_player_id not in (1, 2):
            raise ValueError("starting_player_id must be 1 or 2.")
        self.state = GameState()
        self.state.active_player_id = starting_player_id
        self.target_lore = target_lore
        self._first_turn_player_id = starting_player_id
        self.bag = TheBag()
        self._intent_weights_by_player = self._build_intent_weights_by_player(intent_weights_by_player)
        self._initialize_player_hands()
        self._start_turn(player_id=self.state.active_player_id)

    def get_legal_actions(self) -> list[GameAction]:
        active = self.state.active_player_id
        player = self.state.players[active]
        self._ensure_hand_intents_consistency(player)
        legal: list[GameAction] = []
        if self.state.phase == "main":
            if not player.ink_played_this_turn and player.hand_size > 0:
                legal.append(DevelopInkAction(player_id=active))
            legal.extend(self._playable_character_options(player_id=active))
            if self._find_ready_character(player) is not None:
                legal.append(QuestAction(player_id=active, amount=1))
            opponent_id = 1 if active == 2 else 2
            opponent = self.state.players[opponent_id]
            if self._find_ready_character(player) is not None:
                for defender_index in self._exerted_battlefield_indices(opponent):
                    defender = opponent.battlefield[defender_index]
                    legal.append(
                        ChallengeAction(
                            player_id=active,
                            defender_index=defender_index,
                            defender_strength=defender.strength,
                            defender_willpower=defender.willpower,
                            defender_lore_value=defender.lore_value,
                        )
                    )
            if "song" in player.hand_intents:
                if self._find_ready_character(player) is not None:
                    legal.append(SingSongAction(player_id=active, cost=0, amount=1, uses_singer=True))
                if player.ink_available >= 1:
                    legal.append(SingSongAction(player_id=active, cost=1, amount=1, uses_singer=False))
        legal.append(EndTurnAction(player_id=active))
        return legal

    def clone(self) -> "GameEngineFSM":
        cloned = GameEngineFSM(
            target_lore=self.target_lore,
            intent_weights_by_player=copy.deepcopy(self._intent_weights_by_player),
            starting_player_id=self._first_turn_player_id,
        )
        cloned.state = copy.deepcopy(self.state)
        cloned.bag = self.bag.clone()
        return cloned

    def apply_action(self, action: GameAction) -> None:
        if self.state.winner_player_id is not None:
            return
        if action.player_id != self.state.active_player_id:
            return
        if not self._is_action_legal(action):
            self.state.action_log.append(
                f"P{action.player_id} cannot execute illegal action '{action.action_type}'."
            )
            return

        if isinstance(action, DevelopInkAction):
            self._develop_ink(action.player_id)

        elif isinstance(action, PlayCharacterAction):
            if not self._spend_ink(action.player_id, amount=action.cost):
                self.state.action_log.append(f"P{action.player_id} cannot play character now.")
                return
            player = self.state.players[action.player_id]
            self._ensure_hand_intents_consistency(player)
            if player.hand_size <= 0:
                self.state.action_log.append(f"P{action.player_id} cannot play character (no cards in hand).")
                return
            if not self._remove_one_intent(player=player, intent=action.archetype):
                self.state.action_log.append(
                    f"P{action.player_id} cannot play {action.archetype} character (not in hand intents)."
                )
                return
            player.battlefield.append(
                CharacterInPlay(
                    strength=max(1, action.strength),
                    willpower=max(1, action.willpower),
                    lore_value=max(1, action.lore_value),
                )
            )
            self._sync_board_counts(player)
            self.state.action_log.append(
                (
                    f"P{action.player_id} plays a {action.archetype} character "
                    f"({action.strength}/{action.willpower}, lore={action.lore_value}, "
                    f"fresh={player.board_fresh_characters})."
                )
            )

        elif isinstance(action, QuestAction):
            player = self.state.players[action.player_id]
            attacker = self._find_ready_character(player)
            if attacker is None:
                self.state.action_log.append(f"P{action.player_id} cannot quest (no ready characters).")
                return
            attacker.exerted = True
            lore_gained = max(1, attacker.lore_value) * max(1, action.amount)
            player.lore += lore_gained
            self._sync_board_counts(player)
            self.state.action_log.append(
                f"P{action.player_id} quests for {lore_gained} lore (total={player.lore})."
            )
            self._apply_hidden_combo_bonus(action.player_id)
            self._enqueue_after_lore_gain(action.player_id)
            self._resolve_the_bag()
            self._check_win_condition()

        elif isinstance(action, SingSongAction):
            player = self.state.players[action.player_id]
            self._ensure_hand_intents_consistency(player)
            if "song" not in player.hand_intents:
                self.state.action_log.append(f"P{action.player_id} cannot sing song (no song intent in hand).")
                return
            singer: CharacterInPlay | None = None
            if action.uses_singer:
                singer = self._find_ready_character(player)
                if singer is None:
                    self.state.action_log.append(
                        f"P{action.player_id} cannot sing song for free (no ready characters)."
                    )
                    return
            if not self._spend_ink(action.player_id, amount=action.cost):
                self.state.action_log.append(
                    f"P{action.player_id} cannot sing song now (insufficient ink)."
                )
                return
            self._remove_one_intent(player=player, intent="song")
            if singer is not None:
                singer.exerted = True
            player.lore += action.amount
            self._sync_board_counts(player)
            mode = "for free" if action.uses_singer else f"paying {action.cost} ink"
            self.state.action_log.append(
                f"P{action.player_id} sings a song {mode} for {action.amount} lore (total={player.lore})."
            )
            self._enqueue_after_lore_gain(action.player_id)
            self._resolve_the_bag()
            self._check_win_condition()

        elif isinstance(action, ChallengeAction):
            player = self.state.players[action.player_id]
            opponent_id = 1 if action.player_id == 2 else 2
            opponent = self.state.players[opponent_id]
            attacker = self._find_ready_character(player)
            if attacker is None:
                self.state.action_log.append(f"P{action.player_id} cannot challenge (no ready characters).")
                return
            idx = action.defender_index
            if idx < 0 or idx >= len(opponent.battlefield):
                self.state.action_log.append(
                    f"P{action.player_id} cannot challenge (invalid defender index {idx})."
                )
                return
            defender = opponent.battlefield[idx]
            if not defender.exerted:
                self.state.action_log.append(
                    f"P{action.player_id} cannot challenge (defender at index {idx} is not exerted)."
                )
                return

            attacker.exerted = True
            defender.damage += attacker.strength
            attacker.damage += defender.strength
            attacker_banished = attacker.is_banished
            defender_banished = defender.is_banished
            if attacker_banished:
                player.battlefield.remove(attacker)
            if defender_banished:
                opponent.battlefield.remove(defender)
            self._sync_board_counts(player)
            self._sync_board_counts(opponent)
            self.state.action_log.append(
                (
                    f"P{action.player_id} challenges P{opponent_id} defender[{idx}]: "
                    f"attacker {attacker.strength}/{attacker.willpower} vs "
                    f"defender {defender.strength}/{defender.willpower}."
                )
            )
            if attacker_banished:
                self.state.action_log.append(f"P{action.player_id}'s attacker is banished.")
            if defender_banished:
                self.state.action_log.append(f"P{opponent_id}'s defender is banished.")

        elif isinstance(action, EndTurnAction):
            self.state.phase = "end"
            self.state.action_log.append(f"P{action.player_id} ends turn.")
            self.state.total_turns_taken += 1
            self.state.active_player_id = 1 if action.player_id == 2 else 2
            self.state.turn_number += 1
            self._start_turn(player_id=self.state.active_player_id)

    def _is_action_legal(self, action: GameAction) -> bool:
        legal_actions = self.get_legal_actions()
        requested = self._action_signature(action)
        return any(self._action_signature(candidate) == requested for candidate in legal_actions)

    @staticmethod
    def _action_signature(action: GameAction) -> tuple[str, tuple[tuple[str, object], ...]]:
        if isinstance(action, ChallengeAction):
            payload = (("defender_index", action.defender_index), ("player_id", action.player_id))
            return action.action_type, payload
        payload = tuple(sorted(vars(action).items()))
        return action.action_type, payload

    def _start_turn(self, player_id: int) -> None:
        self.state.phase = "ready"
        player = self.state.players[player_id]
        for character in player.battlefield:
            character.exerted = False
            character.summoning_sick = False
        self._sync_board_counts(player)

        self.state.action_log.append(
            f"Ready phase for P{player_id} on turn {self.state.turn_number} (ready_chars={player.board_ready_characters})."
        )

        self.state.phase = "draw"
        should_draw = not (self.state.turn_number == 1 and player_id == self._first_turn_player_id)
        if should_draw:
            if player.deck_size > 0:
                player.deck_size -= 1
                player.hand_intents.append(self._next_draw_intent(player_id, player.deck_size))
                self._sync_hand_size(player)
                self.state.action_log.append(
                    f"P{player_id} draws a card (hand={player.hand_size}, deck={player.deck_size})."
                )
            else:
                self.state.action_log.append(f"P{player_id} cannot draw (deck is empty).")
        else:
            self.state.action_log.append(f"P{self._first_turn_player_id} skips draw on the first turn.")

        self.state.phase = "main"
        player.ink_available = player.ink_total
        player.ink_played_this_turn = False
        self.state.action_log.append(
            f"Main phase start for P{player_id} (ink={player.ink_available})."
        )

    def _develop_ink(self, player_id: int) -> None:
        player = self.state.players[player_id]
        self._ensure_hand_intents_consistency(player)
        if player.ink_played_this_turn:
            self.state.action_log.append(f"P{player_id} already developed ink this turn.")
            return
        if player.hand_size <= 0:
            self.state.action_log.append(f"P{player_id} cannot develop ink (no cards in hand).")
            return
        self._remove_preferred_ink_intent(player)
        player.ink_total += 1
        player.ink_available += 1
        player.ink_played_this_turn = True
        self.state.action_log.append(
            f"P{player_id} develops ink (total={player.ink_total}, available={player.ink_available}, hand={player.hand_size})."
        )

    def _playable_character_options(self, player_id: int) -> list[PlayCharacterAction]:
        player = self.state.players[player_id]
        self._ensure_hand_intents_consistency(player)
        if player.hand_size <= 0:
            return []
        character_templates_by_name = {
            str(template["archetype"]): template for template in self.CHARACTER_TEMPLATES
        }
        options: list[PlayCharacterAction] = []
        seen_intents: set[str] = set()
        for intent in player.hand_intents:
            if intent in seen_intents:
                continue
            seen_intents.add(intent)
            template = character_templates_by_name.get(intent)
            if template is None:
                continue
            cost = int(template["cost"])
            if player.ink_available < cost:
                continue
            options.append(
                PlayCharacterAction(
                    player_id=player_id,
                    cost=cost,
                    strength=int(template["strength"]),
                    willpower=int(template["willpower"]),
                    lore_value=int(template["lore_value"]),
                    archetype=str(template["archetype"]),
                )
            )
        return options

    def _initialize_player_hands(self) -> None:
        for player_id, player in self.state.players.items():
            player.hand_intents = [
                self._intent_from_profile(player_id=player_id, sequence_index=index)
                for index in range(player.hand_size)
            ]
            self._sync_hand_size(player)

    def _next_draw_intent(self, player_id: int, current_deck_size: int) -> str:
        # Deterministic pseudo-draw from weighted profile.
        sequence_index = max(0, 53 - current_deck_size)
        return self._intent_from_profile(player_id=player_id, sequence_index=sequence_index)

    @staticmethod
    def _sync_hand_size(player: PlayerState) -> None:
        player.hand_size = len(player.hand_intents)

    def _ensure_hand_intents_consistency(self, player: PlayerState) -> None:
        if len(player.hand_intents) < player.hand_size:
            missing = player.hand_size - len(player.hand_intents)
            start_index = len(player.hand_intents)
            player.hand_intents.extend(
                self._intent_from_profile(player.player_id, start_index + offset)
                for offset in range(missing)
            )
        elif len(player.hand_intents) > player.hand_size:
            player.hand_intents = player.hand_intents[: player.hand_size]
        self._sync_hand_size(player)

    @staticmethod
    def _remove_one_intent(player: PlayerState, intent: str) -> bool:
        for index, candidate in enumerate(player.hand_intents):
            if candidate == intent:
                del player.hand_intents[index]
                player.hand_size = len(player.hand_intents)
                return True
        return False

    def _remove_preferred_ink_intent(self, player: PlayerState) -> None:
        for preferred in ("defender", "tempo", "aggressive", "quester", "song"):
            if self._remove_one_intent(player, preferred):
                return

    @classmethod
    def _normalize_intent_weights(cls, weights: dict[str, float] | None) -> dict[str, float]:
        normalized: dict[str, float] = {}
        source = weights or {}
        for key in cls.INTENT_KEYS:
            value = source.get(key, cls.DEFAULT_INTENT_WEIGHTS[key])
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = cls.DEFAULT_INTENT_WEIGHTS[key]
            normalized[key] = max(0.0, numeric)
        total = sum(normalized.values())
        if total <= 0:
            return dict(cls.DEFAULT_INTENT_WEIGHTS)
        return {key: (value / total) for key, value in normalized.items()}

    def _build_intent_weights_by_player(
        self,
        overrides: dict[int, dict[str, float]] | None,
    ) -> dict[int, dict[str, float]]:
        out: dict[int, dict[str, float]] = {}
        for player_id in (1, 2):
            candidate = None
            if overrides is not None:
                candidate = overrides.get(player_id)
            out[player_id] = self._normalize_intent_weights(candidate)
        return out

    def _intent_from_profile(self, player_id: int, sequence_index: int) -> str:
        weights = self._intent_weights_by_player[player_id]
        # Deterministic pseudo-random roll in [0, 1).
        key = (player_id * 9973 + (sequence_index + 1) * 7919 + self.target_lore * 101) % 10000
        roll = key / 10000.0
        cumulative = 0.0
        for intent in self.INTENT_KEYS:
            cumulative += weights[intent]
            if roll <= cumulative:
                return intent
        return self.INTENT_KEYS[-1]

    @staticmethod
    def _find_ready_character(player: PlayerState) -> CharacterInPlay | None:
        for character in player.battlefield:
            if character.is_ready_for_actions:
                return character
        return None

    @staticmethod
    def _exerted_battlefield_indices(player: PlayerState) -> list[int]:
        return [index for index, character in enumerate(player.battlefield) if character.exerted]

    @staticmethod
    def _sync_board_counts(player: PlayerState) -> None:
        ready = 0
        exerted = 0
        fresh = 0
        for character in player.battlefield:
            if character.summoning_sick:
                fresh += 1
            elif character.exerted:
                exerted += 1
            else:
                ready += 1
        player.board_ready_characters = ready
        player.board_exerted_characters = exerted
        player.board_fresh_characters = fresh

    def _spend_ink(self, player_id: int, amount: int) -> bool:
        player = self.state.players[player_id]
        if amount <= 0:
            return True
        if player.ink_available < amount:
            return False
        player.ink_available -= amount
        return True

    def _enqueue_after_lore_gain(self, player_id: int) -> None:
        self.bag.add(
            TriggerEvent(
                owner_player_id=player_id,
                trigger_id="on_lore_gain",
                description="Placeholder trigger for future effects.",
            )
        )

    def _resolve_the_bag(self) -> None:
        active = self.state.active_player_id

        while self.bag.has_events():
            event = self.bag.pop_next_for_player(active)
            if event is None:
                event = self.bag.pop_any()
            if event is None:
                break
            self.state.action_log.append(
                f"Resolve trigger '{event.trigger_id}' for P{event.owner_player_id}."
            )

    def _apply_hidden_combo_bonus(self, player_id: int) -> None:
        player = self.state.players[player_id]
        if player.hidden_combo_potential >= 0.75:
            player.lore += 1
            self.state.action_log.append(
                f"P{player_id} gains 1 bonus lore from sampled hidden combo potential."
            )

    def _check_win_condition(self) -> None:
        for player_id, player in self.state.players.items():
            if player.lore >= self.target_lore:
                self.state.winner_player_id = player_id
                self.state.action_log.append(f"P{player_id} wins by lore.")
                break
