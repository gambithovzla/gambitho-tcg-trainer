from dataclasses import dataclass, field
import copy

from src.domain.engine.actions import EndTurnAction, GainLoreAction, GameAction
from src.domain.engine.the_bag import TheBag, TriggerEvent


@dataclass
class PlayerState:
    player_id: int
    lore: int = 0
    hidden_hand_size: int = 0
    hidden_combo_potential: float = 0.0


@dataclass
class GameState:
    active_player_id: int = 1
    turn_number: int = 1
    players: dict[int, PlayerState] = field(
        default_factory=lambda: {
            1: PlayerState(player_id=1),
            2: PlayerState(player_id=2),
        }
    )
    action_log: list[str] = field(default_factory=list)
    winner_player_id: int | None = None


class GameEngineFSM:
    def __init__(self, target_lore: int = 20) -> None:
        self.state = GameState()
        self.target_lore = target_lore
        self.bag = TheBag()

    def get_legal_actions(self) -> list[GameAction]:
        active = self.state.active_player_id
        return [
            GainLoreAction(player_id=active, amount=1),
            EndTurnAction(player_id=active),
        ]

    def clone(self) -> "GameEngineFSM":
        cloned = GameEngineFSM(target_lore=self.target_lore)
        cloned.state = copy.deepcopy(self.state)
        cloned.bag = self.bag.clone()
        return cloned

    def apply_action(self, action: GameAction) -> None:
        if self.state.winner_player_id is not None:
            return

        if isinstance(action, GainLoreAction):
            player = self.state.players[action.player_id]
            player.lore += action.amount
            self.state.action_log.append(
                f"P{action.player_id} gains {action.amount} lore (total={player.lore})."
            )
            self._apply_hidden_combo_bonus(action.player_id)
            self._enqueue_after_lore_gain(action.player_id)
            self._resolve_the_bag()
            self._check_win_condition()

        elif isinstance(action, EndTurnAction):
            self.state.action_log.append(f"P{action.player_id} ends turn.")
            self.state.active_player_id = 1 if action.player_id == 2 else 2
            self.state.turn_number += 1

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
