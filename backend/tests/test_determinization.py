import random

from src.domain.engine.fsm import GameEngineFSM
from src.domain.simulation.determinization import (
    BeliefDeterminizationSampler,
    DeterminizationContext,
    InformationSetSampler,
)
from src.domain.simulation.ismcts import ISMCTSBot


class CountingSampler(InformationSetSampler):
    def __init__(self) -> None:
        self.calls = 0

    def determinize(
        self,
        engine: GameEngineFSM,
        context: DeterminizationContext,
        rng: random.Random,
    ) -> GameEngineFSM:
        _ = context
        _ = rng
        self.calls += 1
        return engine.clone()


def test_ismcts_uses_sampler_every_iteration() -> None:
    engine = GameEngineFSM(target_lore=5)
    legal = engine.get_legal_actions()
    sampler = CountingSampler()
    bot = ISMCTSBot(iterations=12, rollout_depth=6, sampler=sampler, rng_seed=1)

    _ = bot.choose_action(engine=engine, legal_actions=legal)

    assert sampler.calls == 12


def test_belief_sampler_modifies_non_root_hidden_fields() -> None:
    engine = GameEngineFSM(target_lore=5)
    context = DeterminizationContext(root_player_id=1)
    sampler = BeliefDeterminizationSampler(aggressive_prior=1.0)
    rng = random.Random(9)

    sampled = sampler.determinize(engine=engine, context=context, rng=rng)

    assert sampled.state.players[1].hidden_combo_potential == 0.0
    assert sampled.state.players[1].hidden_hand_size == 0
    assert sampled.state.players[2].hidden_combo_potential >= 0.65
    assert sampled.state.players[2].hidden_hand_size >= 2


def test_aggressive_prior_increases_with_aggro_and_low_cost() -> None:
    sampler = BeliefDeterminizationSampler(aggressive_prior=0.55)
    context = DeterminizationContext(
        root_player_id=1,
        observed_opponent_profile="aggro",
        observed_avg_cost=2.0,
        observed_turns=2,
    )

    prior = sampler.compute_aggressive_prior(context)

    assert prior > 0.8


def test_aggressive_prior_decreases_with_control_and_high_cost() -> None:
    sampler = BeliefDeterminizationSampler(aggressive_prior=0.55)
    context = DeterminizationContext(
        root_player_id=1,
        observed_opponent_profile="control",
        observed_avg_cost=5.0,
        observed_turns=6,
    )

    prior = sampler.compute_aggressive_prior(context)

    assert prior < 0.3
