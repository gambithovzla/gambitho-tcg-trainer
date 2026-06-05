from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuleSection:
    id: str
    title: str
    text: str


@dataclass(frozen=True)
class KeywordRule:
    id: str
    reminder_text: str | None = None
    comprehensive_text: str | None = None
    section_id: str | None = None
    keyword_value_number: int | None = None
    treats_as_evasive_for_challenge: bool = False


@dataclass(frozen=True)
class ChallengeEngineRules:
    evasive_defender_requires_attacker_keywords: tuple[str, ...] = ("Evasive", "Alert")
    ward_blocks_targeting_not_challenge: bool = True


@dataclass(frozen=True)
class LocationEngineRules:
    passive_lore_at_set_step: bool = True
    never_ready_or_exerted: bool = True
    challenge_location_any_time: bool = True
    location_deals_no_challenge_damage: bool = True


@dataclass(frozen=True)
class RulesBundle:
    format_version: str
    generated_at: str
    sources: list[str]
    keywords: tuple[KeywordRule, ...]
    sections: tuple[RuleSection, ...]
    challenge_engine: ChallengeEngineRules
    location_engine: LocationEngineRules = field(default_factory=LocationEngineRules)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RulesBundle:
        challenge_raw = payload.get("challenge_engine") or {}
        location_raw = payload.get("location_engine") or {}
        keywords: list[KeywordRule] = []
        for item in payload.get("keywords") or []:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            keywords.append(
                KeywordRule(
                    id=str(item["id"]),
                    reminder_text=item.get("reminder_text"),
                    comprehensive_text=item.get("comprehensive_text"),
                    section_id=item.get("section_id"),
                    keyword_value_number=item.get("keyword_value_number"),
                    treats_as_evasive_for_challenge=bool(item.get("treats_as_evasive_for_challenge")),
                )
            )
        sections = tuple(
            RuleSection(
                id=str(section["id"]),
                title=str(section.get("title") or ""),
                text=str(section.get("text") or ""),
            )
            for section in (payload.get("sections") or [])
            if isinstance(section, dict) and section.get("id")
        )
        return cls(
            format_version=str(payload.get("format_version") or "1"),
            generated_at=str(payload.get("generated_at") or ""),
            sources=[str(source) for source in (payload.get("sources") or [])],
            keywords=tuple(keywords),
            sections=sections,
            challenge_engine=ChallengeEngineRules(
                evasive_defender_requires_attacker_keywords=tuple(
                    challenge_raw.get("evasive_defender_requires_attacker_keywords")
                    or ("Evasive", "Alert")
                ),
                ward_blocks_targeting_not_challenge=bool(
                    challenge_raw.get("ward_blocks_targeting_not_challenge", True)
                ),
            ),
            location_engine=LocationEngineRules(
                passive_lore_at_set_step=bool(
                    location_raw.get("passive_lore_at_set_step", True)
                ),
                never_ready_or_exerted=bool(location_raw.get("never_ready_or_exerted", True)),
                challenge_location_any_time=bool(
                    location_raw.get("challenge_location_any_time", True)
                ),
                location_deals_no_challenge_damage=bool(
                    location_raw.get("location_deals_no_challenge_damage", True)
                ),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "generated_at": self.generated_at,
            "sources": list(self.sources),
            "keywords": [
                {
                    "id": keyword.id,
                    "reminder_text": keyword.reminder_text,
                    "comprehensive_text": keyword.comprehensive_text,
                    "section_id": keyword.section_id,
                    "keyword_value_number": keyword.keyword_value_number,
                    "treats_as_evasive_for_challenge": keyword.treats_as_evasive_for_challenge,
                }
                for keyword in self.keywords
            ],
            "sections": [
                {"id": section.id, "title": section.title, "text": section.text}
                for section in self.sections
            ],
            "challenge_engine": {
                "evasive_defender_requires_attacker_keywords": list(
                    self.challenge_engine.evasive_defender_requires_attacker_keywords
                ),
                "ward_blocks_targeting_not_challenge": (
                    self.challenge_engine.ward_blocks_targeting_not_challenge
                ),
            },
            "location_engine": {
                "passive_lore_at_set_step": self.location_engine.passive_lore_at_set_step,
                "never_ready_or_exerted": self.location_engine.never_ready_or_exerted,
                "challenge_location_any_time": self.location_engine.challenge_location_any_time,
                "location_deals_no_challenge_damage": (
                    self.location_engine.location_deals_no_challenge_damage
                ),
            },
        }
