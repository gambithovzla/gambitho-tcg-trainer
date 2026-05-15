from src.domain.simulation.benchmark import run_benchmark
from src.domain.simulation.heuristic_bot import simulate_simple_match


def test_ismcts_match_reproducible_with_rng_seed() -> None:
    one = simulate_simple_match(
        max_turns=10,
        target_lore=7,
        strategy="ismcts",
        ismcts_iterations=20,
        rng_seed=1234,
    )
    two = simulate_simple_match(
        max_turns=10,
        target_lore=7,
        strategy="ismcts",
        ismcts_iterations=20,
        rng_seed=1234,
    )

    assert one.winner_player_id == two.winner_player_id
    assert one.turns_played == two.turns_played
    assert one.history == two.history
    assert one.starting_player_id == two.starting_player_id == 1


def test_offline_benchmark_report_contains_required_metrics() -> None:
    report = run_benchmark(
        seeds=[3],
        matches_per_seed=2,
        max_turns=8,
        target_lore=6,
        ismcts_iterations=12,
        rollout_policy="random",
        strategies=["heuristic", "ismcts"],
    )

    assert report.matches_per_seed == 2
    assert report.seeds == [3]
    assert report.rollout_policy == "random"
    assert report.mirror_start_player is False
    assert len(report.strategies) == 2
    for strategy_metrics in report.strategies:
        assert strategy_metrics.matches == 2
        assert 0.0 <= strategy_metrics.p1_winrate <= 1.0
        assert 0.0 <= strategy_metrics.p2_winrate <= 1.0
        assert 0.0 <= strategy_metrics.first_player_winrate <= 1.0
        assert 0.0 <= strategy_metrics.second_player_winrate <= 1.0
        assert 0.0 <= strategy_metrics.draw_rate <= 1.0
        assert strategy_metrics.average_turns_played >= 1.0
        assert strategy_metrics.average_history_entries >= 1.0
        assert set(strategy_metrics.action_distribution.keys()) == {
            "develop_ink",
            "play_character",
            "quest",
            "sing_song",
            "challenge",
            "end_turn",
        }


def test_offline_benchmark_accepts_guided_rollout_policy() -> None:
    report = run_benchmark(
        seeds=[7],
        matches_per_seed=1,
        max_turns=6,
        target_lore=5,
        ismcts_iterations=8,
        rollout_policy="guided_v1",
        strategies=["ismcts"],
    )

    assert report.rollout_policy == "guided_v1"
    assert len(report.strategies) == 1
    assert report.strategies[0].strategy == "ismcts"


def test_offline_benchmark_mirror_mode_doubles_matches() -> None:
    report = run_benchmark(
        seeds=[7],
        matches_per_seed=1,
        max_turns=6,
        target_lore=5,
        ismcts_iterations=8,
        rollout_policy="random",
        mirror_start_player=True,
        strategies=["ismcts"],
    )

    assert report.mirror_start_player is True
    assert len(report.strategies) == 1
    metrics = report.strategies[0]
    assert metrics.matches == 2
    assert abs(
        (metrics.first_player_winrate + metrics.second_player_winrate + metrics.draw_rate) - 1.0
    ) < 1e-9
