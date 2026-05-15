from typing import Literal
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.domain.engine.fsm import GameEngineFSM
from src.domain.simulation.determinization import DeterminizationContext
from src.domain.simulation.heuristic_bot import simulate_simple_match
from src.domain.simulation.intent_profile import DeckIntentCard, infer_intent_weights
from src.domain.simulation.ismcts import ISMCTSBot
from src.infra.db.postgres.card_repository import CardIntentProfile, PostgresCardRepository
from src.infra.simulation.intent_preset_store import IntentPresetStore

router = APIRouter()
STRICT_INTENT_CONTRACT_VERSION = "1"


def _catalog_fallback_mode() -> str:
    value = os.getenv("CATALOG_FALLBACK_MODE", "degraded").strip().lower()
    if value not in {"degraded", "strict"}:
        return "degraded"
    return value


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
    max_turns: int = Field(
        default=20,
        ge=1,
        le=200,
        description=(
            "Upper bound on the engine turn counter while the match loop runs (no winner). "
            "The loop continues while turn_number <= max_turns. If the lore target is not reached, "
            "the reported turns_played equals max_turns + 1 after the last allowed end_turn advance."
        ),
    )
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
    strict_intent_resolution: bool = False
    player_one_deck: list[IntentDeckCardInput] | None = None
    player_two_deck: list[IntentDeckCardInput] | None = None


class MatchResponse(BaseModel):
    winner_player_id: int | None
    turns_played: int = Field(
        description=(
            "Engine turn counter after the match stops: starts at 1, increments by 1 on each "
            "completed end_turn. If the match ends by lore, this reflects the turn counter at that "
            "moment. If it ends because max_turns was exhausted with no winner, this equals "
            "max_turns + 1."
        ),
    )
    history: list[str]
    resolved_player_one_intent_weights: dict[str, float]
    resolved_player_two_intent_weights: dict[str, float]
    resolved_weights_source: str
    strict_validation: list["StrictIntentValidationEntry"] = Field(default_factory=list)
    final_phase: str
    final_active_player_id: int
    total_turns_taken: int
    turn_protocol_version: str


class IntentProfileRequest(BaseModel):
    deck: list[IntentDeckCardInput] = Field(default_factory=list)
    strict: bool = False


class IntentProfileResponse(BaseModel):
    weights: dict[str, float]
    cards_seen: int
    cards_matched_catalog: int
    source: str
    strict_validation: list["StrictIntentValidationEntry"] = Field(default_factory=list)


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
    strict_intent_resolution: bool = False
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
    strict_validation: list["StrictIntentValidationEntry"] = Field(default_factory=list)
    turn_number: int
    phase: str
    turn_protocol_version: str


class StrictIntentValidationEntry(BaseModel):
    actor: str
    hinted_cards: int
    matched_catalog_cards: int
    total_cards: int
    source: str


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
    except Exception as exc:
        if _catalog_fallback_mode() == "strict":
            raise HTTPException(
                status_code=503,
                detail=_strict_intent_error_detail(
                    "CATALOG_REQUIRED_UNAVAILABLE",
                    f"Catalog repository unavailable while strict fallback mode is enabled: {exc}",
                    context={"fallback_mode": "strict"},
                ),
            ) from exc
        profiles = {}
        source = "input_only"

    return infer_intent_weights(deck_cards=deck_cards, catalog_profiles=profiles), len(profiles), source


def _infer_weights_from_deck(deck: list[IntentDeckCardInput] | None) -> dict[str, float] | None:
    weights, _, _ = _infer_weights_from_deck_with_metadata(deck)
    return weights


def _count_cards_with_structural_hints(deck: list[IntentDeckCardInput]) -> int:
    count = 0
    for card in deck:
        has_numeric_hint = any(
            value is not None
            for value in (card.cost, card.strength, card.willpower, card.lore)
        )
        has_type_hint = bool((card.card_type or "").strip()) or bool(card.subtypes)
        if has_numeric_hint or has_type_hint:
            count += 1
    return count


def _strict_intent_error_detail(
    error_code: str,
    message: str,
    *,
    context: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "contract_version": STRICT_INTENT_CONTRACT_VERSION,
        "error_code": error_code,
        "message": message,
        "context": context or {},
    }


def _build_strict_validation_entry(
    actor_label: str,
    deck: list[IntentDeckCardInput],
) -> StrictIntentValidationEntry:
    hinted_cards = _count_cards_with_structural_hints(deck)
    _, matched_catalog, source = _infer_weights_from_deck_with_metadata(deck)
    return StrictIntentValidationEntry(
        actor=actor_label,
        hinted_cards=hinted_cards,
        matched_catalog_cards=matched_catalog,
        total_cards=len(deck),
        source=source,
    )


def _enforce_strict_deck_inference(
    actor_label: str,
    deck: list[IntentDeckCardInput] | None,
    *,
    matched_catalog: int | None = None,
    source: str | None = None,
    hinted_cards: int | None = None,
) -> None:
    if not deck:
        raise HTTPException(
            status_code=422,
            detail=_strict_intent_error_detail(
                "STRICT_INTENT_INPUT_REQUIRED",
                f"Strict intent resolution requires {actor_label} deck data or explicit weights/preset.",
                context={"actor": actor_label},
            ),
        )

    resolved_matched_catalog = matched_catalog
    resolved_source = source
    if resolved_matched_catalog is None or resolved_source is None:
        _, resolved_matched_catalog, resolved_source = _infer_weights_from_deck_with_metadata(deck)

    if resolved_matched_catalog is None:
        resolved_matched_catalog = 0
    if resolved_source is None:
        resolved_source = "none"

    resolved_hinted_cards = hinted_cards
    if resolved_hinted_cards is None:
        resolved_hinted_cards = _count_cards_with_structural_hints(deck)

    if resolved_source == "catalog+input":
        return

    if resolved_hinted_cards < len(deck):
        raise HTTPException(
            status_code=422,
            detail=_strict_intent_error_detail(
                "STRICT_INTENT_HINTS_INSUFFICIENT",
                (
                    f"Strict intent resolution for {actor_label} failed: "
                    f"{resolved_hinted_cards}/{len(deck)} deck cards have usable hints and catalog matched "
                    f"{resolved_matched_catalog}/{len(deck)}. Provide card hints (type/stats) or ingest catalog."
                ),
                context={
                    "actor": actor_label,
                    "hinted_cards": resolved_hinted_cards,
                    "matched_catalog_cards": resolved_matched_catalog,
                    "total_cards": len(deck),
                    "source": resolved_source,
                },
            ),
        )


def _resolve_weights(
    *,
    explicit_weights: dict[str, float] | None,
    deck: list[IntentDeckCardInput] | None,
    preset_name: str | None,
    preset_store: IntentPresetStore,
    actor_label: str,
) -> tuple[dict[str, float], str, str | None]:
    if explicit_weights is not None:
        return GameEngineFSM._normalize_intent_weights(explicit_weights), f"{actor_label}:manual", None

    deck_weights = _infer_weights_from_deck(deck)
    if deck_weights is not None:
        return GameEngineFSM._normalize_intent_weights(deck_weights), f"{actor_label}:deck", None

    if preset_name:
        preset = preset_store.get_preset(preset_name)
        if preset is not None:
            return (
                GameEngineFSM._normalize_intent_weights(preset.weights),
                f"{actor_label}:preset:{preset_name}",
                None,
            )
        return (
            GameEngineFSM._normalize_intent_weights({}),
            f"{actor_label}:preset_missing:{preset_name}",
            preset_name,
        )

    return GameEngineFSM._normalize_intent_weights({}), f"{actor_label}:default", None


@router.post("/intent-profile", response_model=IntentProfileResponse)
def infer_intent_profile(payload: IntentProfileRequest) -> IntentProfileResponse:
    weights, matched_catalog, source = _infer_weights_from_deck_with_metadata(payload.deck)
    strict_validation: list[StrictIntentValidationEntry] = []
    if payload.strict:
        entry = _build_strict_validation_entry("intent_profile", payload.deck)
        _enforce_strict_deck_inference(
            "intent_profile",
            payload.deck,
            matched_catalog=entry.matched_catalog_cards,
            source=entry.source,
            hinted_cards=entry.hinted_cards,
        )
        strict_validation.append(entry)
    return IntentProfileResponse(
        weights=weights or {},
        cards_seen=len(payload.deck),
        cards_matched_catalog=matched_catalog,
        source=source,
        strict_validation=strict_validation,
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
    player_one_weights, p1_source, p1_missing = _resolve_weights(
        explicit_weights=payload.player_one_intent_weights,
        deck=payload.player_one_deck,
        preset_name=payload.player_one_intent_preset,
        preset_store=store,
        actor_label="p1",
    )
    player_two_weights, p2_source, p2_missing = _resolve_weights(
        explicit_weights=payload.player_two_intent_weights,
        deck=payload.player_two_deck,
        preset_name=payload.player_two_intent_preset,
        preset_store=store,
        actor_label="p2",
    )
    opponent_weights, opp_source, opp_missing = _resolve_weights(
        explicit_weights=payload.opponent_intent_weights,
        deck=payload.player_two_deck,
        preset_name=payload.opponent_intent_preset or payload.player_two_intent_preset,
        preset_store=store,
        actor_label="opp",
    )
    if (
        payload.opponent_intent_weights is None
        and payload.opponent_intent_preset is None
        and payload.player_two_intent_preset is None
        and payload.player_two_deck is None
    ):
        opponent_weights = player_two_weights
        opp_source = "opp:p2_resolved"

    strict_validation: list[StrictIntentValidationEntry] = []
    if payload.strict_intent_resolution:
        missing = [name for name in (p1_missing, p2_missing, opp_missing) if name]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=_strict_intent_error_detail(
                    "STRICT_INTENT_PRESET_MISSING",
                    f"Missing intent preset(s): {', '.join(sorted(set(missing)))}",
                    context={"missing_presets": sorted(set(missing))},
                ),
            )
        if p1_source.endswith(":default"):
            raise HTTPException(
                status_code=422,
                detail=_strict_intent_error_detail(
                    "STRICT_INTENT_INPUT_REQUIRED",
                    "Strict intent resolution requires explicit intent weights, a preset, or deck data for player one.",
                    context={"actor": "p1"},
                ),
            )
        if p2_source.endswith(":default"):
            raise HTTPException(
                status_code=422,
                detail=_strict_intent_error_detail(
                    "STRICT_INTENT_INPUT_REQUIRED",
                    "Strict intent resolution requires explicit intent weights, a preset, or deck data for player two.",
                    context={"actor": "p2"},
                ),
            )
        if opp_source.endswith(":default"):
            raise HTTPException(
                status_code=422,
                detail=_strict_intent_error_detail(
                    "STRICT_INTENT_INPUT_REQUIRED",
                    "Strict intent resolution requires explicit intent weights, a preset, or deck data for the opponent model.",
                    context={"actor": "opponent"},
                ),
            )
        if opp_source == "opp:p2_resolved" and p2_source.endswith(":default"):
            raise HTTPException(
                status_code=422,
                detail=_strict_intent_error_detail(
                    "STRICT_INTENT_INPUT_REQUIRED",
                    "Strict intent resolution requires explicit intent for player two before the opponent can inherit it.",
                    context={"actor": "p2"},
                ),
            )
        if p1_source.endswith(":deck"):
            p1_entry = _build_strict_validation_entry("p1", payload.player_one_deck or [])
            _enforce_strict_deck_inference(
                "p1",
                payload.player_one_deck,
                matched_catalog=p1_entry.matched_catalog_cards,
                source=p1_entry.source,
                hinted_cards=p1_entry.hinted_cards,
            )
            strict_validation.append(p1_entry)
        if p2_source.endswith(":deck"):
            p2_entry = _build_strict_validation_entry("p2", payload.player_two_deck or [])
            _enforce_strict_deck_inference(
                "p2",
                payload.player_two_deck,
                matched_catalog=p2_entry.matched_catalog_cards,
                source=p2_entry.source,
                hinted_cards=p2_entry.hinted_cards,
            )
            strict_validation.append(p2_entry)
        if opp_source.endswith(":deck"):
            opp_entry = _build_strict_validation_entry("opponent", payload.player_two_deck or [])
            _enforce_strict_deck_inference(
                "opponent",
                payload.player_two_deck,
                matched_catalog=opp_entry.matched_catalog_cards,
                source=opp_entry.source,
                hinted_cards=opp_entry.hinted_cards,
            )
            strict_validation.append(opp_entry)

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
        strict_validation=strict_validation,
        final_phase=result.final_phase,
        final_active_player_id=result.final_active_player_id,
        total_turns_taken=result.total_turns_taken,
        turn_protocol_version=result.turn_protocol_version,
    )


@router.post("/decision", response_model=DecisionResponse)
def explain_decision(payload: DecisionRequest) -> DecisionResponse:
    store = IntentPresetStore()
    active_weights, active_source, active_missing = _resolve_weights(
        explicit_weights=payload.active_player_intent_weights,
        deck=payload.active_player_deck,
        preset_name=payload.active_player_intent_preset,
        preset_store=store,
        actor_label="active",
    )
    opponent_weights, opponent_source, opponent_missing = _resolve_weights(
        explicit_weights=payload.opponent_intent_weights,
        deck=payload.opponent_deck,
        preset_name=payload.opponent_intent_preset,
        preset_store=store,
        actor_label="opponent",
    )
    strict_validation: list[StrictIntentValidationEntry] = []
    if payload.strict_intent_resolution:
        missing = [name for name in (active_missing, opponent_missing) if name]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=_strict_intent_error_detail(
                    "STRICT_INTENT_PRESET_MISSING",
                    f"Missing intent preset(s): {', '.join(sorted(set(missing)))}",
                    context={"missing_presets": sorted(set(missing))},
                ),
            )
        if active_source.endswith(":default"):
            raise HTTPException(
                status_code=422,
                detail=_strict_intent_error_detail(
                    "STRICT_INTENT_INPUT_REQUIRED",
                    "Strict intent resolution requires explicit intent weights, a preset, or deck data for the active player.",
                    context={"actor": "active_player"},
                ),
            )
        if opponent_source.endswith(":default"):
            raise HTTPException(
                status_code=422,
                detail=_strict_intent_error_detail(
                    "STRICT_INTENT_INPUT_REQUIRED",
                    "Strict intent resolution requires explicit intent weights, a preset, or deck data for the opponent.",
                    context={"actor": "opponent"},
                ),
            )
        if active_source.endswith(":deck"):
            active_entry = _build_strict_validation_entry("active_player", payload.active_player_deck or [])
            _enforce_strict_deck_inference(
                "active_player",
                payload.active_player_deck,
                matched_catalog=active_entry.matched_catalog_cards,
                source=active_entry.source,
                hinted_cards=active_entry.hinted_cards,
            )
            strict_validation.append(active_entry)
        if opponent_source.endswith(":deck"):
            opponent_entry = _build_strict_validation_entry("opponent", payload.opponent_deck or [])
            _enforce_strict_deck_inference(
                "opponent",
                payload.opponent_deck,
                matched_catalog=opponent_entry.matched_catalog_cards,
                source=opponent_entry.source,
                hinted_cards=opponent_entry.hinted_cards,
            )
            strict_validation.append(opponent_entry)
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
        strict_validation=strict_validation,
        turn_number=engine.state.turn_number,
        phase=engine.state.phase,
        turn_protocol_version=engine.state.turn_protocol_version,
    )
