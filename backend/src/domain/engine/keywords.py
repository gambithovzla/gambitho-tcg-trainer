from __future__ import annotations

from src.infra.rules.registry import get_rules_registry


def extract_keywords(rules_text: str) -> frozenset[str]:
    return get_rules_registry().extract_keywords(rules_text)


def resist_reduction(rules_text: str, keywords: frozenset[str]) -> int:
    return get_rules_registry().resist_reduction(rules_text, keywords)


def challenger_bonus(rules_text: str, keywords: frozenset[str]) -> int:
    return get_rules_registry().challenger_bonus(rules_text, keywords)


def can_challenge_evasive_defender(attacker: object) -> bool:
    return get_rules_registry().can_challenge_evasive_defender(_entity_keywords(attacker))


def can_challenge(attacker: object, defender: object) -> bool:
    return get_rules_registry().can_challenge(
        _entity_keywords(attacker),
        _entity_keywords(defender),
    )


def can_quest(character: object) -> bool:
    return not _has_keyword(character, "Reckless")


def legal_challenge_defender_indices(attacker: object, defenders: list[object]) -> list[int]:
    """Exerted defenders legal to challenge, applying Bodyguard (CR 9.2)."""
    legal: list[int] = []
    for index, defender in enumerate(defenders):
        if getattr(defender, "exerted", False) is False:
            continue
        if not can_challenge(attacker, defender):
            continue
        legal.append(index)
    bodyguards = [index for index in legal if _has_keyword(defenders[index], "Bodyguard")]
    if bodyguards:
        return bodyguards
    return legal


def legal_challenge_location_indices(opponent_locations: list[object]) -> list[int]:
    """CR 4.3.5.21 — locations can be challenged any time (not exert-gated)."""
    if not get_rules_registry().bundle.location_engine.challenge_location_any_time:
        return []
    return [
        index
        for index, location in enumerate(opponent_locations)
        if not getattr(location, "is_banished", False)
    ]


def reckless_must_challenge(
    active_battlefield: list[object],
    opponent_battlefield: list[object],
    opponent_locations: list[object] | None = None,
) -> bool:
    """True if any ready Reckless character can legally challenge (CR 9.5)."""
    locations = opponent_locations or []
    for attacker in active_battlefield:
        if not _is_ready_for_quest(attacker):
            continue
        if not _has_keyword(attacker, "Reckless"):
            continue
        if legal_challenge_defender_indices(attacker, opponent_battlefield):
            return True
        if legal_challenge_location_indices(locations):
            return True
    return False


def apply_damage_to_location(location: object, amount: int) -> int:
    dealt = max(0, amount)
    location.damage = getattr(location, "damage", 0) + dealt
    return dealt


def location_move_cost(definition: object) -> int:
    move_cost = getattr(definition, "move_cost", None)
    if move_cost is not None:
        return max(0, move_cost)
    return 0


def apply_support_on_quest(
    quester: object,
    allies: list[object],
    *,
    support_target_index: int | None = None,
) -> int | None:
    """Grant quester's current S to an ally for this turn (CR 9.11). Returns target index."""
    if not _has_keyword(quester, "Support"):
        return None
    candidates = [
        (index, ally)
        for index, ally in enumerate(allies)
        if ally is not quester and not getattr(ally, "is_banished", False)
    ]
    if not candidates:
        return None
    if support_target_index is not None:
        if support_target_index < 0 or support_target_index >= len(allies):
            return None
        target = allies[support_target_index]
        if target is quester:
            return None
        chosen_index = support_target_index
    else:
        chosen_index, target = max(
            candidates,
            key=lambda item: (getattr(item[1], "lore_value", 0), -item[0]),
        )
    target.strength_bonus_this_turn = getattr(quester, "strength", 1)
    return chosen_index


def location_set_step_lore(lore_value: int | None) -> int:
    return get_rules_registry().location_passive_lore(lore_value)


def apply_damage(character: object, amount: int) -> int:
    """Returns actual damage applied after Resist."""
    definition = getattr(character, "definition", None)
    if definition is None:
        dealt = max(0, amount)
    else:
        reduced = max(
            0,
            amount - resist_reduction(definition.rules_text, definition.keywords),
        )
        dealt = reduced
    character.damage = getattr(character, "damage", 0) + dealt
    return dealt


def _entity_keywords(entity: object) -> frozenset[str]:
    definition = getattr(entity, "definition", None)
    if definition is None:
        return frozenset()
    return definition.keywords


def _has_keyword(entity: object, keyword: str) -> bool:
    if hasattr(entity, "has_keyword"):
        return bool(entity.has_keyword(keyword))
    return keyword.lower() in {item.lower() for item in _entity_keywords(entity)}


def _is_ready_for_quest(entity: object) -> bool:
    if hasattr(entity, "is_ready_for_quest"):
        return bool(entity.is_ready_for_quest)
    return not getattr(entity, "exerted", True) and not getattr(entity, "summoning_sick", True)
