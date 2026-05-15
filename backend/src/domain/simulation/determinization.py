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
            if is_aggressive:
                player.hidden_hand_size = rng.randint(2, 5)
                player.hidden_combo_potential = rng.uniform(0.65, 0.95)
            else:
                player.hidden_hand_size = rng.randint(4, 7)
                player.hidden_combo_potential = rng.uniform(0.1, 0.45)

        return sampled
