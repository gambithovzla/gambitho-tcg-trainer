from src.domain.engine.fsm import GameEngineFSM
from src.domain.simulation.heuristic_bot import simulate_simple_match
from src.domain.simulation.ismcts import ISMCTSBot


def test_ismcts_bot_returns_legal_action() -> None:
    engine = GameEngineFSM(target_lore=5)
    bot = ISMCTSBot(iterations=16, rollout_depth=6, rng_seed=7)
    legal = engine.get_legal_actions()

    action = bot.choose_action(engine=engine, legal_actions=legal)

    assert any(action == candidate for candidate in legal)


def test_simulation_supports_ismcts_strategy() -> None:
    result = simulate_simple_match(
        max_turns=12,
        target_lore=5,
        strategy="ismcts",
        ismcts_iterations=24,
    )

    assert result.turns_played >= 1
    assert isinstance(result.history, list)


def test_heuristic_simulation_can_take_multiple_actions_before_end_turn() -> None:
    result = simulate_simple_match(
        max_turns=5,
        target_lore=6,
        strategy="heuristic",
        ismcts_iterations=12,
    )

    p1_play_idx = next(i for i, line in enumerate(result.history) if "P1 plays a" in line and "character" in line)
    p1_develop_idx = max(
        i for i, line in enumerate(result.history) if "P1 develops ink" in line and i < p1_play_idx
    )
    p1_end_idx = next(i for i, line in enumerate(result.history) if "P1 ends turn" in line and i > p1_play_idx)
    assert p1_develop_idx < p1_play_idx < p1_end_idx


def test_ismcts_evaluate_root_reports_ranked_options() -> None:
    engine = GameEngineFSM(target_lore=5)
    bot = ISMCTSBot(iterations=20, rollout_depth=8, rng_seed=13)
    legal = engine.get_legal_actions()

    report = bot.evaluate_root(engine=engine, legal_actions=legal)

    assert len(report.options) == len(legal)
    assert sum(option.visits for option in report.options) == 20
    assert report.options[0].mean_value >= report.options[-1].mean_value
