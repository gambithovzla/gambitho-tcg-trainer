from dataclasses import dataclass
from typing import Protocol
import random

from src.domain.engine.fsm import GameEngineFSM


@dataclass(frozen=True)
class DeterminizationContext:
    root_player_id: int
    observed_opponent_profile: str = "balanced"
    observed_avg_cost: float | None = None
    observed_turns: int = 1
    known_opponent_hand_size: int | None = None
    min_opponent_hand_size: int | None = None
    max_opponent_hand_size: int | None = None
    known_opponent_combo_potential: float | None = None
    min_opponent_combo_potential: float | None = None
    max_opponent_combo_potential: float | None = None


class InformationSetSampler(Protocol):
    def determinize(
        self,
        engine: GameEngineFSM,
        context: DeterminizationContext,
        rng: random.Random,
    ) -> GameEngineFSM:
        """
        Returns a sampled concrete state consistent with the information set.
        In the current MVP engine there is no explicit hidden zone yet, so samplers
        will generally return a clone of the current state.
        """


class NoOpDeterminizationSampler:
    """
    Baseline sampler: preserves current visible state.
    This is intentionally simple until hidden-hand / deck-order models are added.
    """

    def determinize(
        self,
        engine: GameEngineFSM,
        context: DeterminizationContext,
        rng: random.Random,
    ) -> GameEngineFSM:
        _ = context
        _ = rng
        return engine.clone()


class BeliefDeterminizationSampler:
    """
    Samples hidden-opponent attributes from simple priors to approximate
    information-set branching before full hidden-hand/deck modeling exists.
    """

    def __init__(self, aggressive_prior: float = 0.55) -> None:
        self.aggressive_prior = aggressive_prior

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    @staticmethod
    def _normalize_int_range(
        min_value: int | None,
        max_value: int | None,
        fallback_min: int,
        fallback_max: int,
    ) -> tuple[int, int]:
        lower = fallback_min if min_value is None else min_value
        upper = fallback_max if max_value is None else max_value
        lower = max(0, lower)
        upper = max(lower, upper)
        return lower, upper

    @staticmethod
    def _normalize_float_range(
        min_value: float | None,
        max_value: float | None,
        fallback_min: float,
        fallback_max: float,
    ) -> tuple[float, float]:
        lower = fallback_min if min_value is None else min_value
        upper = fallback_max if max_value is None else max_value
        lower = max(0.0, min(1.0, lower))
        upper = max(lower, min(1.0, upper))
        return lower, upper

    def compute_aggressive_prior(self, context: DeterminizationContext) -> float:
        prior = self.aggressive_prior

        profile = context.observed_opponent_profile.lower().strip()
        if profile == "aggro":
            prior += 0.25
        elif profile == "control":
            prior -= 0.25

        if context.observed_avg_cost is not None:
            if context.observed_avg_cost <= 2.5:
                prior += 0.15
            elif context.observed_avg_cost >= 4.5:
                prior -= 0.15

        if context.observed_turns <= 3:
            prior += 0.05

        return max(0.05, min(0.95, prior))

    def sample_hand_size(
        self,
        context: DeterminizationContext,
        rng: random.Random,
        is_aggressive: bool,
    ) -> int:
        if context.known_opponent_hand_size is not None:
            return max(0, context.known_opponent_hand_size)

        # Early turns usually retain larger hidden hands; later turns trend downward.
        turn_decay = max(0, min(3, context.observed_turns // 3))
        if is_aggressive:
            fallback_min, fallback_max = 2, 5 - turn_decay
        else:
            fallback_min, fallback_max = 4, 7 - turn_decay
        fallback_max = max(fallback_min, fallback_max)

        low, high = self._normalize_int_range(
            min_value=context.min_opponent_hand_size,
            max_value=context.max_opponent_hand_size,
            fallback_min=fallback_min,
            fallback_max=fallback_max,
        )
        return rng.randint(low, high)

    def sample_combo_potential(
        self,
        context: DeterminizationContext,
        rng: random.Random,
        is_aggressive: bool,
    ) -> float:
        if context.known_opponent_combo_potential is not None:
            return self._clamp(context.known_opponent_combo_potential, 0.0, 1.0)

        if is_aggressive:
            fallback_min, fallback_max = 0.65, 0.95
        else:
            fallback_min, fallback_max = 0.1, 0.45

        low, high = self._normalize_float_range(
            min_value=context.min_opponent_combo_potential,
            max_value=context.max_opponent_combo_potential,
            fallback_min=fallback_min,
            fallback_max=fallback_max,
        )
        return rng.uniform(low, high)

    def determinize(
        self,
        engine: GameEngineFSM,
        context: DeterminizationContext,
        rng: random.Random,
    ) -> GameEngineFSM:
        sampled = engine.clone()
        aggressive_prior = self.compute_aggressive_prior(context)

        for player_id, player in sampled.state.players.items():
            if player_id == context.root_player_id:
                continue

            is_aggressive = rng.random() < aggressive_prior
            player.hidden_hand_size = self.sample_hand_size(
                context=context,
                rng=rng,
                is_aggressive=is_aggressive,
            )
            player.hidden_combo_potential = self.sample_combo_potential(
                context=context,
                rng=rng,
                is_aggressive=is_aggressive,
            )

        return sampled
