import random

from src.domain.engine.fsm import GameEngineFSM
from src.domain.simulation.determinization import BeliefDeterminizationSampler, DeterminizationContext


def test_sampler_respects_known_hidden_values() -> None:
    sampler = BeliefDeterminizationSampler()
    engine = GameEngineFSM(target_lore=20)
    context = DeterminizationContext(
        root_player_id=1,
        known_opponent_hand_size=6,
        known_opponent_combo_potential=0.33,
    )

    sampled = sampler.determinize(engine=engine, context=context, rng=random.Random(123))

    opponent = sampled.state.players[2]
    assert opponent.hidden_hand_size == 6
    assert opponent.hidden_combo_potential == 0.33


def test_sampler_respects_hand_and_combo_ranges() -> None:
    sampler = BeliefDeterminizationSampler()
    engine = GameEngineFSM(target_lore=20)
    context = DeterminizationContext(
        root_player_id=1,
        min_opponent_hand_size=5,
        max_opponent_hand_size=5,
        min_opponent_combo_potential=0.25,
        max_opponent_combo_potential=0.25,
    )

    sampled = sampler.determinize(engine=engine, context=context, rng=random.Random(7))

    opponent = sampled.state.players[2]
    assert opponent.hidden_hand_size == 5
    assert opponent.hidden_combo_potential == 0.25


def test_sampler_uses_turn_decay_for_aggressive_profile() -> None:
    sampler = BeliefDeterminizationSampler()
    engine = GameEngineFSM(target_lore=20)
    context = DeterminizationContext(
        root_player_id=1,
        observed_opponent_profile="aggro",
        observed_turns=10,
    )

    sampled = sampler.determinize(engine=engine, context=context, rng=random.Random(1))

    opponent = sampled.state.players[2]
    # For late turns, aggressive fallback range is narrowed by decay.
    assert 2 <= opponent.hidden_hand_size <= 2


def test_sampler_applies_opponent_intent_weights_to_hidden_hand() -> None:
    sampler = BeliefDeterminizationSampler()
    engine = GameEngineFSM(target_lore=20)
    context = DeterminizationContext(
        root_player_id=1,
        known_opponent_hand_size=4,
        opponent_intent_weights={
            "tempo": 0.0,
            "aggressive": 0.0,
            "quester": 0.0,
            "defender": 0.0,
            "song": 1.0,
        },
    )

    sampled = sampler.determinize(engine=engine, context=context, rng=random.Random(5))

    opponent = sampled.state.players[2]
    assert opponent.hand_size == 4
    assert opponent.hand_intents == ["song", "song", "song", "song"]
