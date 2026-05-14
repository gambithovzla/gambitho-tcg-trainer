from src.domain.engine.actions import EndTurnAction, GainLoreAction
from src.domain.engine.fsm import GameEngineFSM


def test_gain_lore_updates_state_and_resolves_bag() -> None:
    engine = GameEngineFSM(target_lore=2)

    engine.apply_action(GainLoreAction(player_id=1, amount=1))

    assert engine.state.players[1].lore == 1
    assert any("Resolve trigger" in log for log in engine.state.action_log)


def test_end_turn_switches_active_player() -> None:
    engine = GameEngineFSM()

    engine.apply_action(EndTurnAction(player_id=1))

    assert engine.state.active_player_id == 2
