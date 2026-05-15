from dataclasses import dataclass

from src.domain.engine.actions import (
    ChallengeAction,
    DevelopInkAction,
    EndTurnAction,
    GameAction,
    PlayCharacterAction,
    QuestAction,
    SingSongAction,
)
from src.domain.engine.fsm import GameEngineFSM
from src.domain.simulation.determinization import DeterminizationContext
from src.domain.simulation.ismcts import ISMCTSBot


@dataclass
class MatchResult:
    winner_player_id: int | None
    turns_played: int
    history: list[str]
    starting_player_id: int


class HeuristicBot:
    """Simple policy: develop ink, play character, challenge, quest, sing song, then end turn."""

    def choose_action(self, legal_actions: list[GameAction]) -> GameAction:
        for action in legal_actions:
            if isinstance(action, DevelopInkAction):
                return action
        play_options = [action for action in legal_actions if isinstance(action, PlayCharacterAction)]
        if play_options:
            return max(
                play_options,
                key=lambda action: (2 * action.lore_value + action.strength + action.willpower - action.cost),
            )
        for action in legal_actions:
            if isinstance(action, ChallengeAction):
                return action
        for action in legal_actions:
            if isinstance(action, QuestAction):
                return action
        for action in legal_actions:
            if isinstance(action, SingSongAction):
                return action
        for action in legal_actions:
            if isinstance(action, EndTurnAction):
                return action
        return legal_actions[0]


def _build_bot(
    strategy: str,
    ismcts_iterations: int,
    rng_seed: int | None = None,
    rollout_policy: str = "random",
):
    if strategy == "ismcts":
        return ISMCTSBot(
            iterations=ismcts_iterations,
            rollout_depth=24,
            rng_seed=rng_seed,
            rollout_policy=rollout_policy,
        )
    return HeuristicBot()


def simulate_simple_match(
    max_turns: int = 20,
    target_lore: int = 20,
    strategy: str = "heuristic",
    ismcts_iterations: int = 128,
    observed_opponent_profile: str = "balanced",
    observed_avg_cost: float | None = None,
    observed_turns: int = 1,
    known_opponent_hand_size: int | None = None,
    min_opponent_hand_size: int | None = None,
    max_opponent_hand_size: int | None = None,
    known_opponent_combo_potential: float | None = None,
    min_opponent_combo_potential: float | None = None,
    max_opponent_combo_potential: float | None = None,
    player_one_intent_weights: dict[str, float] | None = None,
    player_two_intent_weights: dict[str, float] | None = None,
    opponent_intent_weights: dict[str, float] | None = None,
    rng_seed: int | None = None,
    rollout_policy: str = "random",
    starting_player_id: int = 1,
) -> MatchResult:
    """Run a full match until a lore win or the turn budget is exhausted.

    The main loop runs while ``engine.state.turn_number <= max_turns`` and there is no winner.
    Each ``end_turn`` advances ``turn_number`` by one. If no player reaches ``target_lore`` before
    the budget is hit, ``turns_played`` (``turn_number``) is ``max_turns + 1`` on exit.
    """
    intent_weights_by_player = {
        1: player_one_intent_weights or {},
        2: player_two_intent_weights or {},
    }
    engine = GameEngineFSM(
        target_lore=target_lore,
        intent_weights_by_player=intent_weights_by_player,
        starting_player_id=starting_player_id,
    )
    bot_1_seed = None if rng_seed is None else rng_seed
    bot_2_seed = None if rng_seed is None else rng_seed + 1
    bot_1 = _build_bot(
        strategy=strategy,
        ismcts_iterations=ismcts_iterations,
        rng_seed=bot_1_seed,
        rollout_policy=rollout_policy,
    )
    bot_2 = _build_bot(
        strategy=strategy,
        ismcts_iterations=ismcts_iterations,
        rng_seed=bot_2_seed,
        rollout_policy=rollout_policy,
    )
    bots = {1: bot_1, 2: bot_2}

    while engine.state.winner_player_id is None and engine.state.turn_number <= max_turns:
        active = engine.state.active_player_id
        legal_actions = engine.get_legal_actions()
        bot = bots[active]
        if isinstance(bot, ISMCTSBot):
            context = DeterminizationContext(
                root_player_id=active,
                observed_opponent_profile=observed_opponent_profile,
                observed_avg_cost=observed_avg_cost,
                observed_turns=max(1, observed_turns),
                known_opponent_hand_size=known_opponent_hand_size,
                min_opponent_hand_size=min_opponent_hand_size,
                max_opponent_hand_size=max_opponent_hand_size,
                known_opponent_combo_potential=known_opponent_combo_potential,
                min_opponent_combo_potential=min_opponent_combo_potential,
                max_opponent_combo_potential=max_opponent_combo_potential,
                opponent_intent_weights=opponent_intent_weights
                or intent_weights_by_player[1 if active == 2 else 2],
            )
            action = bot.choose_action(
                engine=engine,
                legal_actions=legal_actions,
                context_override=context,
            )
        else:
            action = bot.choose_action(legal_actions)
        engine.apply_action(action)

    return MatchResult(
        winner_player_id=engine.state.winner_player_id,
        turns_played=engine.state.turn_number,
        history=engine.state.action_log,
        starting_player_id=starting_player_id,
    )
