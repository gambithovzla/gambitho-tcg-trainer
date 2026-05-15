from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.domain.engine.fsm import GameEngineFSM
from src.domain.simulation.determinization import DeterminizationContext
from src.domain.simulation.heuristic_bot import simulate_simple_match
from src.domain.simulation.intent_profile import DeckIntentCard, infer_intent_weights
from src.domain.simulation.ismcts import ISMCTSBot
from src.infra.db.postgres.card_repository import CardIntentProfile, PostgresCardRepository
from src.infra.simulation.intent_preset_store import IntentPresetStore

router = APIRouter()


class IntentDeckCardInput(BaseModel):
    card_id: str = Field(..., min_length=1)
    copies: int = Field(default=1, ge=1, le=4)
    cost: int | None = Field(default=None, ge=0, le=20)
    strength: int | None = Field(default=None, ge=0, le=20)
    willpower: int | None = Field(default=None, ge=0, le=20)
    lore: int | None = Field(default=None, ge=0, le=20)
    card_type: str | None = None
    subtypes: list[str] = Field(default_factory=list)


class MatchRequest(BaseModel):
    max_turns: int = Field(default=20, ge=1, le=200)
    target_lore: int = Field(default=20, ge=1, le=40)
    strategy: str = Field(default="heuristic")
    ismcts_iterations: int = Field(default=128, ge=1, le=2000)
    observed_opponent_profile: str = Field(default="balanced")
    observed_avg_cost: float | None = Field(default=None, ge=0.0, le=20.0)
    observed_turns: int = Field(default=1, ge=1, le=40)
    known_opponent_hand_size: int | None = Field(default=None, ge=0, le=40)
    min_opponent_hand_size: int | None = Field(default=None, ge=0, le=40)
    max_opponent_hand_size: int | None = Field(default=None, ge=0, le=40)
    known_opponent_combo_potential: float | None = Field(default=None, ge=0.0, le=1.0)
    min_opponent_combo_potential: float | None = Field(default=None, ge=0.0, le=1.0)
    max_opponent_combo_potential: float | None = Field(default=None, ge=0.0, le=1.0)
    player_one_intent_weights: dict[str, float] | None = None
    player_two_intent_weights: dict[str, float] | None = None
    opponent_intent_weights: dict[str, float] | None = None
    player_one_intent_preset: str | None = None
    player_two_intent_preset: str | None = None
    opponent_intent_preset: str | None = None
    player_one_deck: list[IntentDeckCardInput] | None = None
    player_two_deck: list[IntentDeckCardInput] | None = None


class MatchResponse(BaseModel):
    winner_player_id: int | None
    turns_played: int
    history: list[str]
    resolved_player_one_intent_weights: dict[str, float]
    resolved_player_two_intent_weights: dict[str, float]
    resolved_weights_source: str


class IntentProfileRequest(BaseModel):
    deck: list[IntentDeckCardInput] = Field(default_factory=list)


class IntentProfileResponse(BaseModel):
    weights: dict[str, float]
    cards_seen: int
    cards_matched_catalog: int
    source: str


class IntentPresetUpsertRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    weights: dict[str, float]
    tags: list[str] = Field(default_factory=list)


class IntentPresetResponse(BaseModel):
    name: str
    weights: dict[str, float]
    tags: list[str] = Field(default_factory=list)
    updated_at: str | None = None
    created_at: str | None = None
    version: int | None = None
    history_length: int = 0
    history_preview: list["IntentPresetHistoryEntryResponse"] = Field(default_factory=list)


class IntentPresetListResponse(BaseModel):
    presets: list[IntentPresetResponse]
    total: int
    returned: int
    next_offset: int | None = None
    prev_offset: int | None = None
    has_more: bool = False


class IntentPresetDeleteResponse(BaseModel):
    name: str
    deleted: bool


class IntentPresetPatchRequest(BaseModel):
    weights: dict[str, float] | None = None
    tags: list[str] | None = None


class IntentPresetHistoryEntryResponse(BaseModel):
    version: int | None = None
    updated_at: str | None = None
    weights: dict[str, float]


class IntentPresetHistoryResponse(BaseModel):
    name: str
    history: list[IntentPresetHistoryEntryResponse]


class DecisionRequest(BaseModel):
    target_lore: int = Field(default=20, ge=1, le=40)
    active_player_id: int = Field(default=1, ge=1, le=2)
    player_one_lore: int = Field(default=0, ge=0, le=40)
    player_two_lore: int = Field(default=0, ge=0, le=40)
    ismcts_iterations: int = Field(default=128, ge=1, le=2000)
    observed_opponent_profile: str = Field(default="balanced")
    observed_avg_cost: float | None = Field(default=None, ge=0.0, le=20.0)
    observed_turns: int = Field(default=1, ge=1, le=40)
    known_opponent_hand_size: int | None = Field(default=None, ge=0, le=40)
    min_opponent_hand_size: int | None = Field(default=None, ge=0, le=40)
    max_opponent_hand_size: int | None = Field(default=None, ge=0, le=40)
    known_opponent_combo_potential: float | None = Field(default=None, ge=0.0, le=1.0)
    min_opponent_combo_potential: float | None = Field(default=None, ge=0.0, le=1.0)
    max_opponent_combo_potential: float | None = Field(default=None, ge=0.0, le=1.0)
    active_player_intent_weights: dict[str, float] | None = None
    opponent_intent_weights: dict[str, float] | None = None
    active_player_intent_preset: str | None = None
    opponent_intent_preset: str | None = None
    active_player_deck: list[IntentDeckCardInput] | None = None
    opponent_deck: list[IntentDeckCardInput] | None = None


class DecisionOptionResponse(BaseModel):
    action_type: str
    player_id: int
    amount: int | None
    cost: int | None
    archetype: str | None
    visits: int
    reward_sum: float
    mean_value: float


class DecisionResponse(BaseModel):
    chosen_action_type: str
    chosen_player_id: int
    chosen_amount: int | None
    chosen_cost: int | None
    chosen_archetype: str | None
    total_iterations: int
    options: list[DecisionOptionResponse]
    resolved_active_player_intent_weights: dict[str, float]
    resolved_opponent_intent_weights: dict[str, float]
    resolved_weights_source: str


def _infer_weights_from_deck_with_metadata(
    deck: list[IntentDeckCardInput] | None,
) -> tuple[dict[str, float] | None, int, str]:
    if not deck:
        return None, 0, "none"

    deck_cards = [
        DeckIntentCard(
            card_id=card.card_id,
            copies=card.copies,
            cost=card.cost,
            strength=card.strength,
            willpower=card.willpower,
            lore=card.lore,
            card_type=card.card_type,
            subtypes=card.subtypes,
        )
        for card in deck
    ]

    profiles: dict[str, CardIntentProfile] = {}
    source = "input_only"
    try:
        repository = PostgresCardRepository()
        profiles = repository.get_intent_profiles([card.card_id for card in deck])
        if profiles:
            source = "catalog+input"
    except Exception:
        profiles = {}
        source = "input_only"

    return infer_intent_weights(deck_cards=deck_cards, catalog_profiles=profiles), len(profiles), source


def _infer_weights_from_deck(deck: list[IntentDeckCardInput] | None) -> dict[str, float] | None:
    weights, _, _ = _infer_weights_from_deck_with_metadata(deck)
    return weights


def _resolve_weights(
    *,
    explicit_weights: dict[str, float] | None,
    deck: list[IntentDeckCardInput] | None,
    preset_name: str | None,
    preset_store: IntentPresetStore,
    actor_label: str,
) -> tuple[dict[str, float], str]:
    if explicit_weights is not None:
        return GameEngineFSM._normalize_intent_weights(explicit_weights), f"{actor_label}:manual"

    deck_weights = _infer_weights_from_deck(deck)
    if deck_weights is not None:
        return GameEngineFSM._normalize_intent_weights(deck_weights), f"{actor_label}:deck"

    if preset_name:
        preset = preset_store.get_preset(preset_name)
        if preset is not None:
            return GameEngineFSM._normalize_intent_weights(preset.weights), f"{actor_label}:preset:{preset_name}"
        return GameEngineFSM._normalize_intent_weights({}), f"{actor_label}:preset_missing:{preset_name}"

    return GameEngineFSM._normalize_intent_weights({}), f"{actor_label}:default"


@router.post("/intent-profile", response_model=IntentProfileResponse)
def infer_intent_profile(payload: IntentProfileRequest) -> IntentProfileResponse:
    weights, matched_catalog, source = _infer_weights_from_deck_with_metadata(payload.deck)
    return IntentProfileResponse(
        weights=weights or {},
        cards_seen=len(payload.deck),
        cards_matched_catalog=matched_catalog,
        source=source,
    )


@router.get("/intent-presets", response_model=IntentPresetListResponse)
def list_intent_presets(
    include_history: bool = False,
    history_limit: int = 3,
    q: str | None = None,
    sort_by: Literal["name", "updated_at", "version"] = "name",
    order: Literal["asc", "desc"] = "asc",
    limit: int = 100,
    offset: int = 0,
) -> IntentPresetListResponse:
    store = IntentPresetStore()
    presets = store.list_presets()
    safe_limit = max(1, min(20, history_limit))
    serialized: list[IntentPresetResponse] = []
    matching: list[tuple[str, object]] = []
    query = (q or "").strip().lower()
    for name, preset in sorted(presets.items()):
        if query:
            name_match = query in name.lower()
            tags = preset.tags or []
            tag_match = any(query in tag for tag in tags)
            if not (name_match or tag_match):
                continue
        matching.append((name, preset))

    reverse = order == "desc"
    if sort_by == "name":
        matching.sort(key=lambda item: item[0].lower(), reverse=reverse)
    elif sort_by == "updated_at":
        matching.sort(key=lambda item: (getattr(item[1], "updated_at", "") or ""), reverse=reverse)
    else:
        matching.sort(key=lambda item: int(getattr(item[1], "version", 0) or 0), reverse=reverse)

    safe_offset = max(0, offset)
    safe_page_size = max(1, min(500, limit))
    page = matching[safe_offset : safe_offset + safe_page_size]

    for name, preset in page:
        preview: list[IntentPresetHistoryEntryResponse] = []
        if include_history and preset.history:
            tail = preset.history[-safe_limit:]
            preview = [
                IntentPresetHistoryEntryResponse(
                    version=entry.get("version") if isinstance(entry.get("version"), int) else None,
                    updated_at=str(entry.get("updated_at")) if entry.get("updated_at") else None,
                    weights=GameEngineFSM._normalize_intent_weights(
                        entry.get("weights", {}) if isinstance(entry.get("weights"), dict) else {}
                    ),
                )
                for entry in tail
            ]
        serialized.append(
            IntentPresetResponse(
                name=name,
                weights=preset.weights,
                tags=preset.tags or [],
                updated_at=preset.updated_at,
                created_at=preset.created_at,
                version=preset.version,
                history_length=len(preset.history or []),
                history_preview=preview,
            )
        )
    returned = len(serialized)
    total = len(matching)
    has_more = safe_offset + returned < total
    next_offset = safe_offset + returned if has_more else None
    prev_offset = max(0, safe_offset - safe_page_size) if safe_offset > 0 else None
    return IntentPresetListResponse(
        presets=serialized,
        total=total,
        returned=returned,
        next_offset=next_offset,
        prev_offset=prev_offset,
        has_more=has_more,
    )


@router.get("/intent-presets/{name}", response_model=IntentPresetResponse)
def get_intent_preset(name: str) -> IntentPresetResponse:
    store = IntentPresetStore()
    preset = store.get_preset(name)
    if preset is None:
        return IntentPresetResponse(name=name, weights={})
    return IntentPresetResponse(
        name=name,
        weights=preset.weights,
        tags=preset.tags or [],
        updated_at=preset.updated_at,
        created_at=preset.created_at,
        version=preset.version,
        history_length=len(preset.history or []),
        history_preview=[],
    )


@router.post("/intent-presets", response_model=IntentPresetResponse)
def upsert_intent_preset(payload: IntentPresetUpsertRequest) -> IntentPresetResponse:
    store = IntentPresetStore()
    preset = store.upsert_preset(payload.name, payload.weights, tags=payload.tags)
    return IntentPresetResponse(
        name=payload.name,
        weights=preset.weights,
        tags=preset.tags or [],
        updated_at=preset.updated_at,
        created_at=preset.created_at,
        version=preset.version,
        history_length=len(preset.history or []),
        history_preview=[],
    )


@router.patch("/intent-presets/{name}", response_model=IntentPresetResponse)
def patch_intent_preset(name: str, payload: IntentPresetPatchRequest) -> IntentPresetResponse:
    store = IntentPresetStore()
    preset = store.patch_preset(name, payload.weights, tags=payload.tags)
    if preset is None:
        return IntentPresetResponse(name=name, weights={})
    return IntentPresetResponse(
        name=name,
        weights=preset.weights,
        tags=preset.tags or [],
        updated_at=preset.updated_at,
        created_at=preset.created_at,
        version=preset.version,
        history_length=len(preset.history or []),
        history_preview=[],
    )


@router.get("/intent-presets/{name}/history", response_model=IntentPresetHistoryResponse)
def get_intent_preset_history(name: str) -> IntentPresetHistoryResponse:
    store = IntentPresetStore()
    raw_history = store.get_preset_history(name)
    history = [
        IntentPresetHistoryEntryResponse(
            version=entry.get("version") if isinstance(entry.get("version"), int) else None,
            updated_at=str(entry.get("updated_at")) if entry.get("updated_at") else None,
            weights=GameEngineFSM._normalize_intent_weights(
                entry.get("weights", {}) if isinstance(entry.get("weights"), dict) else {}
            ),
        )
        for entry in raw_history
    ]
    return IntentPresetHistoryResponse(name=name, history=history)


@router.delete("/intent-presets/{name}", response_model=IntentPresetDeleteResponse)
def delete_intent_preset(name: str) -> IntentPresetDeleteResponse:
    store = IntentPresetStore()
    deleted = store.delete_preset(name)
    return IntentPresetDeleteResponse(name=name, deleted=deleted)


@router.post("/match", response_model=MatchResponse)
def run_match(payload: MatchRequest) -> MatchResponse:
    if payload.strategy not in {"heuristic", "ismcts"}:
        payload.strategy = "heuristic"

    store = IntentPresetStore()
    player_one_weights, p1_source = _resolve_weights(
        explicit_weights=payload.player_one_intent_weights,
        deck=payload.player_one_deck,
        preset_name=payload.player_one_intent_preset,
        preset_store=store,
        actor_label="p1",
    )
    player_two_weights, p2_source = _resolve_weights(
        explicit_weights=payload.player_two_intent_weights,
        deck=payload.player_two_deck,
        preset_name=payload.player_two_intent_preset,
        preset_store=store,
        actor_label="p2",
    )
    opponent_weights, opp_source = _resolve_weights(
        explicit_weights=payload.opponent_intent_weights,
        deck=payload.player_two_deck,
        preset_name=payload.opponent_intent_preset or payload.player_two_intent_preset,
        preset_store=store,
        actor_label="opp",
    )
    if payload.opponent_intent_weights is None and payload.opponent_intent_preset is None and payload.player_two_intent_preset is None and payload.player_two_deck is None:
        opponent_weights = player_two_weights
        opp_source = "opp:p2_resolved"

    result = simulate_simple_match(
        max_turns=payload.max_turns,
        target_lore=payload.target_lore,
        strategy=payload.strategy,
        ismcts_iterations=payload.ismcts_iterations,
        observed_opponent_profile=payload.observed_opponent_profile,
        observed_avg_cost=payload.observed_avg_cost,
        observed_turns=payload.observed_turns,
        known_opponent_hand_size=payload.known_opponent_hand_size,
        min_opponent_hand_size=payload.min_opponent_hand_size,
        max_opponent_hand_size=payload.max_opponent_hand_size,
        known_opponent_combo_potential=payload.known_opponent_combo_potential,
        min_opponent_combo_potential=payload.min_opponent_combo_potential,
        max_opponent_combo_potential=payload.max_opponent_combo_potential,
        player_one_intent_weights=player_one_weights,
        player_two_intent_weights=player_two_weights,
        opponent_intent_weights=opponent_weights,
    )
    return MatchResponse(
        winner_player_id=result.winner_player_id,
        turns_played=result.turns_played,
        history=result.history,
        resolved_player_one_intent_weights=player_one_weights,
        resolved_player_two_intent_weights=player_two_weights,
        resolved_weights_source=";".join((p1_source, p2_source, opp_source)),
    )


@router.post("/decision", response_model=DecisionResponse)
def explain_decision(payload: DecisionRequest) -> DecisionResponse:
    store = IntentPresetStore()
    active_weights, active_source = _resolve_weights(
        explicit_weights=payload.active_player_intent_weights,
        deck=payload.active_player_deck,
        preset_name=payload.active_player_intent_preset,
        preset_store=store,
        actor_label="active",
    )
    opponent_weights, opponent_source = _resolve_weights(
        explicit_weights=payload.opponent_intent_weights,
        deck=payload.opponent_deck,
        preset_name=payload.opponent_intent_preset,
        preset_store=store,
        actor_label="opponent",
    )
    if payload.active_player_id == 1:
        by_player = {1: active_weights, 2: opponent_weights}
    else:
        by_player = {1: opponent_weights, 2: active_weights}
    engine = GameEngineFSM(target_lore=payload.target_lore, intent_weights_by_player=by_player)
    engine.state.active_player_id = payload.active_player_id
    engine.state.players[1].lore = payload.player_one_lore
    engine.state.players[2].lore = payload.player_two_lore

    legal_actions = engine.get_legal_actions()
    bot = ISMCTSBot(iterations=payload.ismcts_iterations, rollout_depth=24)
    context = DeterminizationContext(
        root_player_id=payload.active_player_id,
        observed_opponent_profile=payload.observed_opponent_profile,
        observed_avg_cost=payload.observed_avg_cost,
        observed_turns=payload.observed_turns,
        known_opponent_hand_size=payload.known_opponent_hand_size,
        min_opponent_hand_size=payload.min_opponent_hand_size,
        max_opponent_hand_size=payload.max_opponent_hand_size,
        known_opponent_combo_potential=payload.known_opponent_combo_potential,
        min_opponent_combo_potential=payload.min_opponent_combo_potential,
        max_opponent_combo_potential=payload.max_opponent_combo_potential,
        opponent_intent_weights=payload.opponent_intent_weights,
    )
    report = bot.evaluate_root(
        engine=engine,
        legal_actions=legal_actions,
        context_override=context,
    )

    chosen = report.chosen_action
    return DecisionResponse(
        chosen_action_type=chosen.action_type,
        chosen_player_id=chosen.player_id,
        chosen_amount=getattr(chosen, "amount", None),
        chosen_cost=getattr(chosen, "cost", None),
        chosen_archetype=getattr(chosen, "archetype", None),
        total_iterations=report.total_iterations,
        options=[
            DecisionOptionResponse(
                action_type=option.action_type,
                player_id=option.player_id,
                amount=option.amount,
                cost=option.cost,
                archetype=option.archetype,
                visits=option.visits,
                reward_sum=option.reward_sum,
                mean_value=option.mean_value,
            )
            for option in report.options
        ],
        resolved_active_player_intent_weights=GameEngineFSM._normalize_intent_weights(active_weights),
        resolved_opponent_intent_weights=GameEngineFSM._normalize_intent_weights(opponent_weights),
        resolved_weights_source=";".join((active_source, opponent_source)),
    )
