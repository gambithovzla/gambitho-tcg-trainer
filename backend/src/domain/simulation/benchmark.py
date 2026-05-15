from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import argparse
import json
from pathlib import Path
from statistics import mean, pvariance

from src.domain.simulation.heuristic_bot import MatchResult, simulate_simple_match


ACTION_BUCKETS: tuple[tuple[str, str], ...] = (
    ("develop_ink", "develops ink"),
    ("play_character", "plays a"),
    ("quest", "quests for"),
    ("sing_song", "sings a song"),
    ("challenge", "challenges"),
    ("end_turn", "ends turn"),
)


@dataclass
class StrategyMetrics:
    strategy: str
    matches: int
    p1_winrate: float
    p2_winrate: float
    first_player_winrate: float
    second_player_winrate: float
    draw_rate: float
    p1_win_indicator_variance: float
    average_turns_played: float
    average_history_entries: float
    action_distribution: dict[str, float]


@dataclass
class BenchmarkReport:
    seeds: list[int]
    matches_per_seed: int
    mirror_start_player: bool
    max_turns: int
    target_lore: int
    ismcts_iterations: int
    rollout_policy: str
    strategies: list[StrategyMetrics]


def _action_distribution(results: list[MatchResult]) -> dict[str, float]:
    counts: Counter[str] = Counter()
    total = 0
    for result in results:
        for line in result.history:
            for action_name, marker in ACTION_BUCKETS:
                if marker in line:
                    counts[action_name] += 1
                    total += 1
                    break
    if total == 0:
        return {action_name: 0.0 for action_name, _ in ACTION_BUCKETS}
    return {action_name: counts[action_name] / total for action_name, _ in ACTION_BUCKETS}


def _summarize_results(strategy: str, results: list[MatchResult]) -> StrategyMetrics:
    if not results:
        raise ValueError("Cannot summarize empty benchmark results.")

    p1_wins = [1 if result.winner_player_id == 1 else 0 for result in results]
    p2_wins = [1 if result.winner_player_id == 2 else 0 for result in results]
    first_player_wins = [1 if result.winner_player_id == result.starting_player_id else 0 for result in results]
    second_player_wins = [
        1
        if result.winner_player_id is not None and result.winner_player_id != result.starting_player_id
        else 0
        for result in results
    ]
    draws = [1 if result.winner_player_id is None else 0 for result in results]
    turns = [result.turns_played for result in results]
    history_sizes = [len(result.history) for result in results]

    return StrategyMetrics(
        strategy=strategy,
        matches=len(results),
        p1_winrate=mean(p1_wins),
        p2_winrate=mean(p2_wins),
        first_player_winrate=mean(first_player_wins),
        second_player_winrate=mean(second_player_wins),
        draw_rate=mean(draws),
        p1_win_indicator_variance=pvariance(p1_wins),
        average_turns_played=mean(turns),
        average_history_entries=mean(history_sizes),
        action_distribution=_action_distribution(results),
    )


def run_strategy_benchmark(
    *,
    strategy: str,
    seeds: list[int],
    matches_per_seed: int,
    max_turns: int,
    target_lore: int,
    ismcts_iterations: int,
    rollout_policy: str,
    mirror_start_player: bool,
) -> StrategyMetrics:
    results: list[MatchResult] = []
    for seed in seeds:
        for match_index in range(matches_per_seed):
            # Deterministic seed stream for reproducible batches.
            run_seed = seed * 1_000_003 + match_index
            start_players = (1, 2) if mirror_start_player else (1,)
            for starting_player_id in start_players:
                results.append(
                    simulate_simple_match(
                        max_turns=max_turns,
                        target_lore=target_lore,
                        strategy=strategy,
                        ismcts_iterations=ismcts_iterations,
                        rng_seed=run_seed,
                        rollout_policy=rollout_policy,
                        starting_player_id=starting_player_id,
                    )
                )
    return _summarize_results(strategy=strategy, results=results)


def run_benchmark(
    *,
    seeds: list[int],
    matches_per_seed: int,
    max_turns: int,
    target_lore: int,
    ismcts_iterations: int,
    rollout_policy: str = "random",
    mirror_start_player: bool = False,
    strategies: list[str] | None = None,
) -> BenchmarkReport:
    requested = strategies or ["heuristic", "ismcts"]
    report = BenchmarkReport(
        seeds=seeds,
        matches_per_seed=matches_per_seed,
        mirror_start_player=mirror_start_player,
        max_turns=max_turns,
        target_lore=target_lore,
        ismcts_iterations=ismcts_iterations,
        rollout_policy=rollout_policy,
        strategies=[],
    )
    for strategy in requested:
        report.strategies.append(
            run_strategy_benchmark(
                strategy=strategy,
                seeds=seeds,
                matches_per_seed=matches_per_seed,
                max_turns=max_turns,
                target_lore=target_lore,
                ismcts_iterations=ismcts_iterations,
                rollout_policy=rollout_policy,
                mirror_start_player=mirror_start_player,
            )
        )
    return report


def _parse_seed_list(value: str) -> list[int]:
    if not value.strip():
        raise argparse.ArgumentTypeError("Seed list cannot be empty.")
    out: list[int] = []
    for raw in value.split(","):
        token = raw.strip()
        if not token:
            continue
        try:
            out.append(int(token))
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid seed '{token}'.") from exc
    if not out:
        raise argparse.ArgumentTypeError("Seed list cannot be empty.")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline benchmark runner for heuristic vs ISMCTS simulation strategies."
    )
    parser.add_argument("--seeds", type=_parse_seed_list, default=[7, 11, 19])
    parser.add_argument("--matches-per-seed", type=int, default=20)
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--target-lore", type=int, default=8)
    parser.add_argument("--ismcts-iterations", type=int, default=64)
    parser.add_argument("--rollout-policy", type=str, default="random")
    parser.add_argument("--mirror-start-player", action="store_true")
    parser.add_argument("--strategies", type=str, default="heuristic,ismcts")
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args()

    strategy_list = [token.strip() for token in args.strategies.split(",") if token.strip()]
    report = run_benchmark(
        seeds=args.seeds,
        matches_per_seed=max(1, args.matches_per_seed),
        max_turns=max(1, args.max_turns),
        target_lore=max(1, min(40, args.target_lore)),
        ismcts_iterations=max(1, args.ismcts_iterations),
        rollout_policy=args.rollout_policy.strip() or "random",
        mirror_start_player=bool(args.mirror_start_player),
        strategies=strategy_list or ["heuristic", "ismcts"],
    )
    serialized = asdict(report)

    if args.output.strip():
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")

    print(json.dumps(serialized, indent=2))


if __name__ == "__main__":
    main()
