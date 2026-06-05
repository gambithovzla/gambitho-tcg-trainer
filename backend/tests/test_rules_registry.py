import json
from pathlib import Path

import pytest

from src.infra.rules.models import ChallengeEngineRules, KeywordRule, RuleSection, RulesBundle
from src.infra.rules.registry import RulesRegistry, set_rules_registry
from src.domain.engine import keywords as engine_keywords


@pytest.fixture(autouse=True)
def _rules_bundle(tmp_path: Path):
    bundle = RulesBundle(
        format_version="test",
        generated_at="2026-01-01T00:00:00+00:00",
        sources=["test"],
        keywords=(
            KeywordRule(
                id="Evasive",
                comprehensive_text="CR Evasive text",
                section_id="9.4",
            ),
            KeywordRule(
                id="Alert",
                reminder_text="challenge as if they had Evasive",
                treats_as_evasive_for_challenge=True,
            ),
            KeywordRule(
                id="Resist",
                keyword_value_number=2,
            ),
            KeywordRule(
                id="Challenger",
                keyword_value_number=2,
            ),
        ),
        sections=(
            RuleSection(id="9.4", title="Evasive", text="CR Evasive text"),
        ),
        challenge_engine=ChallengeEngineRules(
            evasive_defender_requires_attacker_keywords=("Evasive", "Alert"),
        ),
    )
    path = tmp_path / "rules_bundle.json"
    path.write_text(json.dumps(bundle.to_dict()), encoding="utf-8")
    set_rules_registry(RulesRegistry.load(path))
    yield
    set_rules_registry(None)


def test_extract_keywords_from_rules_text() -> None:
    found = engine_keywords.extract_keywords("Evasive and Challenger +2")
    assert "Evasive" in found
    assert "Challenger" in found


def test_can_challenge_uses_bundle_config() -> None:
    from src.domain.engine.card_model import CardDefinition, CardInstance, CharacterInPlay

    def character(keyword_names: list[str]) -> CharacterInPlay:
        return CharacterInPlay(
            instance=CardInstance(instance_id="i", card_id="c", owner_id=1),
            definition=CardDefinition(
                card_id="c",
                name="Test",
                card_type="Character",
                cost=1,
                strength=1,
                willpower=1,
                lore=1,
                inkwell_inkable=True,
                rules_text=" ".join(keyword_names),
                keywords=frozenset(keyword_names),
            ),
        )

    assert engine_keywords.can_challenge(character(["Alert"]), character(["Evasive"])) is True
    assert engine_keywords.can_challenge(character([]), character(["Evasive"])) is False


def test_resist_uses_bundle_default() -> None:
    reduction = engine_keywords.resist_reduction("Resist +2", frozenset({"Resist"}))
    assert reduction == 2


def test_location_set_step_lore_from_bundle() -> None:
    assert engine_keywords.location_set_step_lore(2) == 2
    assert engine_keywords.location_set_step_lore(0) == 0
    assert engine_keywords.location_set_step_lore(None) == 0
