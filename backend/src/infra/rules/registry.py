from __future__ import annotations

import json
import re
from pathlib import Path

from src.infra.rules.models import KeywordRule, RulesBundle
from src.infra.rules.sync import DEFAULT_BUNDLE_PATH, sync_rules_bundle

_REGISTRY: RulesRegistry | None = None


class RulesRegistry:
    def __init__(self, bundle: RulesBundle) -> None:
        self.bundle = bundle
        self._keyword_ids = tuple(keyword.id for keyword in bundle.keywords)
        self._keyword_by_id = {keyword.id: keyword for keyword in bundle.keywords}
        self._may_challenge_evasive = bundle.challenge_engine.evasive_defender_requires_attacker_keywords

    @classmethod
    def load(cls, path: Path | None = None) -> RulesRegistry:
        bundle_path = path or DEFAULT_BUNDLE_PATH
        if not bundle_path.is_file():
            sync_rules_bundle(output_path=bundle_path)
        payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        return cls(RulesBundle.from_dict(payload))

    def reload(self, *, sync_remote: bool = False) -> None:
        if sync_remote:
            self.bundle = sync_rules_bundle(output_path=DEFAULT_BUNDLE_PATH)
        else:
            self.bundle = RulesBundle.from_dict(
                json.loads(DEFAULT_BUNDLE_PATH.read_text(encoding="utf-8"))
            )
        self._keyword_ids = tuple(keyword.id for keyword in self.bundle.keywords)
        self._keyword_by_id = {keyword.id: keyword for keyword in self.bundle.keywords}
        self._may_challenge_evasive = self.bundle.challenge_engine.evasive_defender_requires_attacker_keywords

    def extract_keywords(self, rules_text: str) -> frozenset[str]:
        if not rules_text:
            return frozenset()
        found: set[str] = set()
        for keyword_id in self._keyword_ids:
            if re.search(rf"\b{re.escape(keyword_id)}\b", rules_text, flags=re.IGNORECASE):
                found.add(self._keyword_by_id[keyword_id].id)
        return frozenset(found)

    def resist_reduction(self, rules_text: str, keywords: frozenset[str]) -> int:
        if not any(item for item in keywords if item.lower() == "resist"):
            return 0
        match = re.search(r"Resist\s*\+\s*(\d+)", rules_text or "", flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
        rule = self._keyword_by_id.get("Resist")
        if rule and rule.keyword_value_number is not None:
            return int(rule.keyword_value_number)
        return 1

    def challenger_bonus(self, rules_text: str, keywords: frozenset[str]) -> int:
        if not any(item for item in keywords if item.lower() == "challenger"):
            return 0
        match = re.search(r"Challenger\s*\+\s*(\d+)", rules_text or "", flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
        rule = self._keyword_by_id.get("Challenger")
        if rule and rule.keyword_value_number is not None:
            return int(rule.keyword_value_number)
        return 1

    def can_challenge_evasive_defender(self, attacker_keywords: frozenset[str]) -> bool:
        allowed = {item.lower() for item in self._may_challenge_evasive}
        return any(keyword.lower() in allowed for keyword in attacker_keywords)

    def location_passive_lore(self, lore_value: int | None) -> int:
        if not self.bundle.location_engine.passive_lore_at_set_step:
            return 0
        return max(0, lore_value or 0)

    def can_challenge(self, attacker_keywords: frozenset[str], defender_keywords: frozenset[str]) -> bool:
        defender_has_evasive = any(item.lower() == "evasive" for item in defender_keywords)
        if not defender_has_evasive:
            return True
        return self.can_challenge_evasive_defender(attacker_keywords)

    def get_keyword(self, keyword_id: str) -> KeywordRule | None:
        return self._keyword_by_id.get(keyword_id)


def get_rules_registry() -> RulesRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = RulesRegistry.load()
    return _REGISTRY


def set_rules_registry(registry: RulesRegistry | None) -> None:
    global _REGISTRY
    _REGISTRY = registry
