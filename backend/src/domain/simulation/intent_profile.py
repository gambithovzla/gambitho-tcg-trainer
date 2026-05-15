from dataclasses import dataclass

from src.infra.db.postgres.card_repository import CardIntentProfile


INTENT_KEYS: tuple[str, ...] = ("tempo", "aggressive", "quester", "defender", "song")


@dataclass(frozen=True)
class DeckIntentCard:
    card_id: str
    copies: int
    cost: int | None = None
    strength: int | None = None
    willpower: int | None = None
    lore: int | None = None
    card_type: str | None = None
    subtypes: list[str] | None = None


def infer_intent_weights(
    deck_cards: list[DeckIntentCard],
    catalog_profiles: dict[str, CardIntentProfile] | None = None,
) -> dict[str, float]:
    scores: dict[str, float] = {key: 0.0 for key in INTENT_KEYS}
    profiles = catalog_profiles or {}

    for card in deck_cards:
        if card.copies <= 0:
            continue
        profile = profiles.get(card.card_id)

        cost = profile.cost if profile and profile.cost is not None else card.cost
        strength = profile.strength if profile and profile.strength is not None else card.strength
        willpower = profile.willpower if profile and profile.willpower is not None else card.willpower
        lore = profile.lore if profile and profile.lore is not None else card.lore
        card_type = profile.card_type if profile and profile.card_type is not None else card.card_type
        subtypes = profile.subtypes if profile and profile.subtypes else (card.subtypes or [])

        card_scores = _intent_scores_for_card(
            cost=cost,
            strength=strength,
            willpower=willpower,
            lore=lore,
            card_type=card_type,
            subtypes=subtypes,
        )
        for intent, value in card_scores.items():
            scores[intent] += value * card.copies

    total = sum(max(0.0, value) for value in scores.values())
    if total <= 0.0:
        return {
            "tempo": 0.30,
            "aggressive": 0.20,
            "quester": 0.20,
            "defender": 0.15,
            "song": 0.15,
        }
    return {intent: max(0.0, value) / total for intent, value in scores.items()}


def _intent_scores_for_card(
    *,
    cost: int | None,
    strength: int | None,
    willpower: int | None,
    lore: int | None,
    card_type: str | None,
    subtypes: list[str],
) -> dict[str, float]:
    c = max(0, cost or 0)
    s = max(0, strength or 0)
    w = max(0, willpower or 0)
    l = max(0, lore or 0)

    subtypes_lower = {value.lower() for value in subtypes}
    card_type_lower = (card_type or "").lower()
    is_song = "song" in subtypes_lower or card_type_lower == "song"
    is_character = card_type_lower == "character"

    scores = {key: 0.0 for key in INTENT_KEYS}

    if is_song:
        scores["song"] += 3.0
        scores["tempo"] += 0.5
        return scores

    # Generic baseline for all cards.
    scores["tempo"] += 1.0 + (0.5 if c <= 3 else 0.0)
    if c >= 4:
        scores["defender"] += 0.5

    if is_character:
        scores["aggressive"] += s + max(0.0, 3.0 - c) * 0.5
        scores["defender"] += w + max(0.0, c - 2.0) * 0.5
        scores["quester"] += l * 2.0 + max(0.0, w - 2.0) * 0.3
        scores["tempo"] += max(0.0, 3.0 - c) * 0.8
    elif card_type_lower in {"action", "item", "location"}:
        scores["tempo"] += 1.2
        if l > 0:
            scores["quester"] += 0.7 * l
    else:
        scores["tempo"] += 0.8

    return scores
