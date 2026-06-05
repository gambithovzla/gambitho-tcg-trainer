from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from src.infra.rules.models import (
    ChallengeEngineRules,
    KeywordRule,
    LocationEngineRules,
    RuleSection,
    RulesBundle,
)

LORCANAJSON_ALL_CARDS_URL = "https://lorcanajson.org/files/current/en/allCards.json"
DEFAULT_BUNDLE_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "lorcana_rules" / "rules_bundle.json"
)
SEED_SECTIONS_PATH = Path(__file__).resolve().parent / "data" / "comprehensive_sections.json"

# Map CR section titles to keyword ids used on cards.
SECTION_TITLE_TO_KEYWORD: dict[str, str] = {
    "Bodyguard": "Bodyguard",
    "Challenger": "Challenger",
    "Evasive": "Evasive",
    "Reckless": "Reckless",
    "Resist": "Resist",
    "Rush": "Rush",
    "Shift": "Shift",
    "Singer": "Singer",
    "Song": "Song",
    "Support": "Support",
    "Ward": "Ward",
}


def _load_seed() -> dict[str, Any]:
    return json.loads(SEED_SECTIONS_PATH.read_text(encoding="utf-8"))


def _fetch_lorcanajson_cards(*, language: str = "en", timeout: float = 300.0) -> list[dict[str, Any]]:
    url = LORCANAJSON_ALL_CARDS_URL.replace("/en/", f"/{language}/")
    headers = {"User-Agent": "gambitho-tcg-trainer/0.1"}
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        payload = response.json()
    if isinstance(payload, dict) and isinstance(payload.get("cards"), list):
        return payload["cards"]
    if isinstance(payload, list):
        return payload
    raise ValueError("Unexpected LorcanaJSON allCards payload shape.")


def _extract_keywords_from_cards(cards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    collected: dict[str, dict[str, Any]] = {}
    for card in cards:
        for ability in card.get("abilities") or []:
            if not isinstance(ability, dict):
                continue
            keyword_id = str(ability.get("keyword") or "").strip()
            if not keyword_id:
                continue
            reminder = (ability.get("reminderText") or ability.get("fullText") or "").strip() or None
            value_number = ability.get("keywordValueNumber")
            entry = collected.get(keyword_id) or {"id": keyword_id}
            if reminder and len(reminder) > len(entry.get("reminder_text") or ""):
                entry["reminder_text"] = reminder
            if value_number is not None and entry.get("keyword_value_number") is None:
                entry["keyword_value_number"] = value_number
            treats_as_evasive = _keyword_grants_challenge_as_evasive(keyword_id, reminder or "")
            if treats_as_evasive:
                entry["treats_as_evasive_for_challenge"] = True
            collected[keyword_id] = entry
    return collected


def _keyword_grants_challenge_as_evasive(keyword_id: str, reminder: str) -> bool:
    if keyword_id.lower() == "alert":
        return True
    return "challenge as if they had evasive" in reminder.lower()


def _merge_seed_sections(seed: dict[str, Any]) -> tuple[list[RuleSection], dict[str, KeywordRule]]:
    sections: list[RuleSection] = []
    by_id: dict[str, KeywordRule] = {}
    for raw in seed.get("sections") or []:
        if not isinstance(raw, dict):
            continue
        section = RuleSection(
            id=str(raw["id"]),
            title=str(raw.get("title") or ""),
            text=str(raw.get("text") or ""),
        )
        sections.append(section)
        keyword_name = SECTION_TITLE_TO_KEYWORD.get(section.title)
        if keyword_name:
            existing = by_id.get(keyword_name)
            by_id[keyword_name] = KeywordRule(
                id=keyword_name,
                comprehensive_text=section.text,
                section_id=section.id,
                reminder_text=existing.reminder_text if existing else None,
            )
    return sections, by_id


def _location_engine_from_seed(seed: dict[str, Any]) -> LocationEngineRules:
    raw = seed.get("location_engine") or {}
    return LocationEngineRules(
        passive_lore_at_set_step=bool(raw.get("passive_lore_at_set_step", True)),
        never_ready_or_exerted=bool(raw.get("never_ready_or_exerted", True)),
        challenge_location_any_time=bool(raw.get("challenge_location_any_time", True)),
        location_deals_no_challenge_damage=bool(
            raw.get("location_deals_no_challenge_damage", True)
        ),
    )


def _challenge_engine_from_seed(seed: dict[str, Any]) -> ChallengeEngineRules:
    raw = seed.get("challenge_engine") or {}
    return ChallengeEngineRules(
        evasive_defender_requires_attacker_keywords=tuple(
            raw.get("evasive_defender_requires_attacker_keywords") or ("Evasive", "Alert")
        ),
        ward_blocks_targeting_not_challenge=bool(raw.get("ward_blocks_targeting_not_challenge", True)),
    )


def sync_rules_bundle(
    *,
    language: str = "en",
    output_path: Path | None = None,
) -> RulesBundle:
    """Download card data and merge with bundled comprehensive-rule sections."""
    seed = _load_seed()
    cards = _fetch_lorcanajson_cards(language=language)
    card_keywords = _extract_keywords_from_cards(cards)

    sections, keyword_from_seed = _merge_seed_sections(seed)
    merged_keywords: dict[str, KeywordRule] = dict(keyword_from_seed)

    for keyword_id, raw in card_keywords.items():
        existing = merged_keywords.get(keyword_id)
        merged_keywords[keyword_id] = KeywordRule(
            id=keyword_id,
            reminder_text=raw.get("reminder_text") or (existing.reminder_text if existing else None),
            comprehensive_text=existing.comprehensive_text if existing else None,
            section_id=existing.section_id if existing else None,
            keyword_value_number=raw.get("keyword_value_number")
            if raw.get("keyword_value_number") is not None
            else (existing.keyword_value_number if existing else None),
            treats_as_evasive_for_challenge=bool(raw.get("treats_as_evasive_for_challenge"))
            or (existing.treats_as_evasive_for_challenge if existing else False),
        )

    challenge_engine = _challenge_engine_from_seed(seed)
    location_engine = _location_engine_from_seed(seed)
    required = set(challenge_engine.evasive_defender_requires_attacker_keywords)
    for keyword in merged_keywords.values():
        if keyword.treats_as_evasive_for_challenge:
            required.add(keyword.id)
    challenge_engine = ChallengeEngineRules(
        evasive_defender_requires_attacker_keywords=tuple(sorted(required)),
        ward_blocks_targeting_not_challenge=challenge_engine.ward_blocks_targeting_not_challenge,
    )

    bundle = RulesBundle(
        format_version="2",
        generated_at=datetime.now(timezone.utc).isoformat(),
        sources=[
            f"lorcanajson:{language}:allCards.json",
            "comprehensive_sections_seed",
        ],
        keywords=tuple(sorted(merged_keywords.values(), key=lambda item: item.id.lower())),
        sections=tuple(sections),
        challenge_engine=challenge_engine,
        location_engine=location_engine,
    )

    path = output_path or DEFAULT_BUNDLE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return bundle


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Sync Lorcana rules bundle from official sources.")
    parser.add_argument("--language", default="en")
    parser.add_argument("--output", default=str(DEFAULT_BUNDLE_PATH))
    args = parser.parse_args()

    bundle = sync_rules_bundle(language=args.language, output_path=Path(args.output))
    print(
        json.dumps(
            {
                "path": args.output,
                "keywords": len(bundle.keywords),
                "sections": len(bundle.sections),
                "generated_at": bundle.generated_at,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
