from fastapi import APIRouter, Query

from pydantic import BaseModel

from src.infra.rules.registry import RulesRegistry, get_rules_registry, set_rules_registry
from src.infra.rules.sync import DEFAULT_BUNDLE_PATH, sync_rules_bundle

router = APIRouter()


class KeywordRuleResponse(BaseModel):
    id: str
    reminder_text: str | None = None
    comprehensive_text: str | None = None
    section_id: str | None = None
    keyword_value_number: int | None = None
    treats_as_evasive_for_challenge: bool = False


class RuleSectionResponse(BaseModel):
    id: str
    title: str
    text: str


class RulesBundleResponse(BaseModel):
    format_version: str
    generated_at: str
    sources: list[str]
    keywords: list[KeywordRuleResponse]
    sections: list[RuleSectionResponse]
    challenge_engine: dict[str, object]


class RulesSyncResponse(BaseModel):
    path: str
    keywords: int
    sections: int
    generated_at: str


@router.get("/bundle", response_model=RulesBundleResponse)
def get_rules_bundle() -> RulesBundleResponse:
    registry = get_rules_registry()
    bundle = registry.bundle
    return RulesBundleResponse(
        format_version=bundle.format_version,
        generated_at=bundle.generated_at,
        sources=list(bundle.sources),
        keywords=[
            KeywordRuleResponse(
                id=keyword.id,
                reminder_text=keyword.reminder_text,
                comprehensive_text=keyword.comprehensive_text,
                section_id=keyword.section_id,
                keyword_value_number=keyword.keyword_value_number,
                treats_as_evasive_for_challenge=keyword.treats_as_evasive_for_challenge,
            )
            for keyword in bundle.keywords
        ],
        sections=[
            RuleSectionResponse(id=section.id, title=section.title, text=section.text)
            for section in bundle.sections
        ],
        challenge_engine={
            "evasive_defender_requires_attacker_keywords": list(
                bundle.challenge_engine.evasive_defender_requires_attacker_keywords
            ),
            "ward_blocks_targeting_not_challenge": (
                bundle.challenge_engine.ward_blocks_targeting_not_challenge
            ),
        },
    )


@router.post("/sync", response_model=RulesSyncResponse)
def sync_rules(
    language: str = Query(default="en", min_length=2, max_length=8),
) -> RulesSyncResponse:
    bundle = sync_rules_bundle(language=language)
    set_rules_registry(RulesRegistry.load())
    return RulesSyncResponse(
        path=str(DEFAULT_BUNDLE_PATH),
        keywords=len(bundle.keywords),
        sections=len(bundle.sections),
        generated_at=bundle.generated_at,
    )
