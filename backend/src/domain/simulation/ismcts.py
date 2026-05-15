from dataclasses import dataclass
import math
import random

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
from src.domain.simulation.determinization import (
    BeliefDeterminizationSampler,
    DeterminizationContext,
    InformationSetSampler,
)


def _action_key(action: GameAction) -> tuple:
    attributes = tuple(sorted(vars(action).items()))
    return (action.action_type, action.player_id, attributes)


@dataclass
class ActionStats:
    action: GameAction
    visits: int = 0
    reward_sum: float = 0.0

    @property
    def mean_value(self) -> float:
        if self.visits == 0:
            return 0.0
        return self.reward_sum / self.visits


@dataclass(frozen=True)
class RootActionEvaluation:
    action_type: str
    player_id: int
    amount: int | None
    cost: int | None
    archetype: str | None
    visits: int
    reward_sum: float
    mean_value: float


@dataclass
class RootDecisionReport:
    chosen_action: GameAction
    options: list[RootActionEvaluation]
    total_iterations: int


class ISMCTSBot:
    """
    Lightweight ISMCTS-style root search for current visible state.
    Uses a pluggable determinization sampler for hidden information hypotheses.
    """

    def __init__(
        self,
        iterations: int = 128,
        rollout_depth: int = 24,
        exploration_constant: float = 1.41,
        rng_seed: int | None = None,
        rollout_policy: str = "random",
        sampler: InformationSetSampler | None = None,
    ) -> None:
        if rollout_policy not in {"random", "guided_v1"}:
            raise ValueError("rollout_policy must be one of: random, guided_v1")
        self.iterations = iterations
        self.rollout_depth = rollout_depth
        self.exploration_constant = exploration_constant
        self.rollout_policy = rollout_policy
        self._rng = random.Random(rng_seed)
        self._sampler = sampler or BeliefDeterminizationSampler()

    def choose_action(
        self,
        engine: GameEngineFSM,
        legal_actions: list[GameAction],
        context_override: DeterminizationContext | None = None,
    ) -> GameAction:
        if len(legal_actions) == 1:
            return legal_actions[0]

        report = self.evaluate_root(
            engine=engine,
            legal_actions=legal_actions,
            context_override=context_override,
        )
        return report.chosen_action

    def evaluate_root(
        self,
        engine: GameEngineFSM,
        legal_actions: list[GameAction],
        context_override: DeterminizationContext | None = None,
    ) -> RootDecisionReport:
        if len(legal_actions) == 1:
            only = legal_actions[0]
            return RootDecisionReport(
                chosen_action=only,
                options=[
                    RootActionEvaluation(
                        action_type=only.action_type,
                        player_id=only.player_id,
                        amount=getattr(only, "amount", None),
                        cost=getattr(only, "cost", None),
                        archetype=getattr(only, "archetype", None),
                        visits=0,
                        reward_sum=0.0,
                        mean_value=0.0,
                    )
                ],
                total_iterations=0,
            )

        root_player = engine.state.active_player_id
        stats: dict[tuple, ActionStats] = {
            _action_key(action): ActionStats(action=action) for action in legal_actions
        }
        context = context_override or DeterminizationContext(root_player_id=root_player)

        for _ in range(self.iterations):
            selected_stats = self._select_action(stats)
            rollout_engine = self._sampler.determinize(
                engine=engine,
                context=context,
                rng=self._rng,
            )
            self._apply_action(rollout_engine, selected_stats.action)
            reward = self._rollout(rollout_engine, root_player)
            selected_stats.visits += 1
            selected_stats.reward_sum += reward

        chosen = max(stats.values(), key=lambda s: (s.mean_value, s.visits)).action
        options = [
            RootActionEvaluation(
                action_type=s.action.action_type,
                player_id=s.action.player_id,
                amount=getattr(s.action, "amount", None),
                cost=getattr(s.action, "cost", None),
                archetype=getattr(s.action, "archetype", None),
                visits=s.visits,
                reward_sum=s.reward_sum,
                mean_value=s.mean_value,
            )
            for s in stats.values()
        ]
        options.sort(key=lambda option: (option.mean_value, option.visits), reverse=True)
        return RootDecisionReport(
            chosen_action=chosen,
            options=options,
            total_iterations=self.iterations,
        )

    def _select_action(self, stats: dict[tuple, ActionStats]) -> ActionStats:
        total_visits = sum(s.visits for s in stats.values()) + 1
        unvisited = [s for s in stats.values() if s.visits == 0]
        if unvisited:
            return self._rng.choice(unvisited)

        def ucb1(s: ActionStats) -> float:
            explore = self.exploration_constant * math.sqrt(math.log(total_visits) / s.visits)
            return s.mean_value + explore

        return max(stats.values(), key=ucb1)

    def _rollout(self, engine: GameEngineFSM, root_player: int) -> float:
        depth = 0
        while engine.state.winner_player_id is None and depth < self.rollout_depth:
            legal = engine.get_legal_actions()
            action = self._select_rollout_action(engine=engine, legal_actions=legal)
            self._apply_action(engine, action)
            depth += 1

        winner = engine.state.winner_player_id
        if winner is None:
            return self._heuristic_terminal_value(engine, root_player)
        return 1.0 if winner == root_player else 0.0

    @staticmethod
    def _apply_action(engine: GameEngineFSM, action: GameAction) -> None:
        engine.apply_action(action)

    def _select_rollout_action(
        self,
        *,
        engine: GameEngineFSM,
        legal_actions: list[GameAction],
    ) -> GameAction:
        if len(legal_actions) == 1 or self.rollout_policy == "random":
            return self._rng.choice(legal_actions)
        return self._select_rollout_action_guided_v1(engine=engine, legal_actions=legal_actions)

    def _select_rollout_action_guided_v1(
        self,
        *,
        engine: GameEngineFSM,
        legal_actions: list[GameAction],
    ) -> GameAction:
        active_player = engine.state.active_player_id
        opponent_id = 1 if active_player == 2 else 2
        active = engine.state.players[active_player]
        opponent = engine.state.players[opponent_id]
        target = max(1, engine.target_lore)
        lore_pressure = (opponent.lore - active.lore) / target
        active_to_win = max(0, target - active.lore)
        opponent_to_win = max(0, target - opponent.lore)
        has_non_end = any(not isinstance(action, EndTurnAction) for action in legal_actions)

        scored_actions: list[tuple[GameAction, float]] = []
        for action in legal_actions:
            score = self._guided_v1_rollout_action_score(
                action=action,
                engine=engine,
                lore_pressure=lore_pressure,
                active_to_win=active_to_win,
                opponent_to_win=opponent_to_win,
                has_non_end=has_non_end,
            )
            score += self._rng.random() * 1e-6
            scored_actions.append((action, score))

        min_score = min(score for _, score in scored_actions)
        actions: list[GameAction] = []
        weights: list[float] = []
        for action, score in scored_actions:
            actions.append(action)
            weights.append(0.2 + (score - min_score))
        return self._rng.choices(actions, weights=weights, k=1)[0]

    @staticmethod
    def _guided_v1_rollout_action_score(
        *,
        action: GameAction,
        engine: GameEngineFSM,
        lore_pressure: float,
        active_to_win: int,
        opponent_to_win: int,
        has_non_end: bool,
    ) -> float:
        active_player = engine.state.active_player_id
        opponent_id = 1 if active_player == 2 else 2
        active = engine.state.players[active_player]
        opponent = engine.state.players[opponent_id]

        score = 0.0
        if isinstance(action, QuestAction):
            score += 0.35 + 0.20 * max(0.0, lore_pressure)
            if active_to_win <= max(1, action.amount):
                score += 0.55
            if opponent_to_win <= 2:
                score += 0.05
            return score

        if isinstance(action, SingSongAction):
            score += 0.30 + 0.10 * action.amount
            if not action.uses_singer:
                score -= 0.05 * max(0, action.cost)
            if active_to_win <= max(1, action.amount):
                score += 0.45
            if lore_pressure > 0.20:
                score += 0.10
            return score

        if isinstance(action, PlayCharacterAction):
            score += 0.18
            score += 0.08 * max(1, action.lore_value)
            score += 0.03 * max(1, action.strength)
            score += 0.02 * max(1, action.willpower)
            score -= 0.03 * max(0, action.cost)
            score += 0.06 * max(0.0, lore_pressure)
            return score

        if isinstance(action, ChallengeAction):
            score += 0.14
            attacker = GameEngineFSM._find_ready_character(active)
            if attacker is None:
                return score - 0.2
            if 0 <= action.defender_index < len(opponent.battlefield):
                defender = opponent.battlefield[action.defender_index]
                defender_trade = attacker.strength - max(0, defender.willpower - defender.damage)
                retaliation_pressure = max(0, defender.strength - max(0, attacker.willpower - attacker.damage))
                score += 0.04 * defender_trade
                score -= 0.03 * retaliation_pressure
                if opponent_to_win <= 2:
                    score += 0.18
                if lore_pressure > 0.15:
                    score += 0.20 * lore_pressure
            return score

        if isinstance(action, DevelopInkAction):
            score += 0.10
            score -= 0.12 * max(0.0, lore_pressure)
            if active_to_win <= 2:
                score -= 0.22
            elif active_to_win <= 4:
                score -= 0.08
            if opponent_to_win <= 2:
                score -= 0.12
            return score

        if isinstance(action, EndTurnAction):
            score -= 0.05
            if has_non_end:
                score -= 0.70
            if active_to_win <= 2:
                score -= 0.10
            if opponent_to_win <= 2:
                score -= 0.10
            return score

        return score

    @staticmethod
    def _heuristic_terminal_value(engine: GameEngineFSM, root_player: int) -> float:
        own = engine.state.players[root_player].lore
        opp_id = 1 if root_player == 2 else 2
        opp_player = engine.state.players[opp_id]
        opp = opp_player.lore

        hidden_pressure = opp_player.hidden_combo_potential * 0.5 + opp_player.hidden_hand_size * 0.03
        diff = own - (opp + hidden_pressure)
        return max(0.0, min(1.0, 0.5 + diff / (2 * max(1, engine.target_lore))))
