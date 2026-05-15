from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import os

from src.domain.linter.lorcana_linter import (
    DeckRepairResult,
    DeckValidationResult,
    LorcanaDeckLinter,
)
from src.infra.db.postgres.card_repository import PostgresCardRepository

router = APIRouter()


def _catalog_fallback_mode() -> str:
    value = os.getenv("CATALOG_FALLBACK_MODE", "degraded").strip().lower()
    if value not in {"degraded", "strict"}:
        return "degraded"
    return value


class DeckCardInput(BaseModel):
    card_id: str = Field(..., min_length=1)
    copies: int = Field(..., ge=1, le=4)
    colors: list[str] = Field(default_factory=list, max_length=2)


class DeckCardRepairInput(BaseModel):
    card_id: str = Field(..., min_length=1)
    copies: int = Field(..., ge=0, le=999)
    colors: list[str] = Field(default_factory=list)


class DeckValidationRequest(BaseModel):
    cards: list[DeckCardInput]
    strict_catalog: bool = True


class DeckRepairRequest(BaseModel):
    cards: list[DeckCardRepairInput]
    strict_catalog: bool = True


class DeckIssueResponse(BaseModel):
    code: str
    message: str
    card_id: str | None = None
    expected: str | None = None
    actual: str | None = None


class DeckValidationResponse(BaseModel):
    is_legal: bool
    errors: list[str]
    warnings: list[str]
    total_cards: int
    issues: list[DeckIssueResponse]


class DeckRepairResponse(BaseModel):
    repaired_cards: list[DeckCardInput]
    notes: list[str]
    validation: DeckValidationResponse


@router.post("/validate", response_model=DeckValidationResponse)
def validate_deck(payload: DeckValidationRequest) -> DeckValidationResponse:
    linter = LorcanaDeckLinter()
    deck_tuples = [(card.card_id, card.copies, card.colors) for card in payload.cards]
    existing_card_ids: set[str] | None = None
    warnings: list[str] = []

    if payload.strict_catalog:
        try:
            repository = PostgresCardRepository()
            existing_card_ids = repository.get_existing_card_ids(
                [card.card_id for card in payload.cards]
            )
        except Exception as exc:
            if _catalog_fallback_mode() == "strict":
                raise HTTPException(
                    status_code=503,
                    detail=f"Catalog validation required but repository is unavailable: {exc}",
                ) from exc
            warnings.append(f"Catalog validation skipped: {exc}")

    result: DeckValidationResult = linter.validate(
        deck=deck_tuples,
        existing_card_ids=existing_card_ids,
    )
    result.warnings.extend(warnings)
    return DeckValidationResponse(
        is_legal=result.is_legal,
        errors=result.errors,
        warnings=result.warnings,
        total_cards=result.total_cards,
        issues=[
            {
                "code": issue.code,
                "message": issue.message,
                "card_id": issue.card_id,
                "expected": issue.expected,
                "actual": issue.actual,
            }
            for issue in result.issues
        ],
    )


@router.post("/repair", response_model=DeckRepairResponse)
def repair_deck(payload: DeckRepairRequest) -> DeckRepairResponse:
    linter = LorcanaDeckLinter()
    deck_tuples = [(card.card_id, card.copies, card.colors) for card in payload.cards]
    existing_card_ids: set[str] | None = None
    warnings: list[str] = []

    if payload.strict_catalog:
        try:
            repository = PostgresCardRepository()
            existing_card_ids = repository.get_existing_card_ids(
                [card.card_id for card in payload.cards]
            )
        except Exception as exc:
            if _catalog_fallback_mode() == "strict":
                raise HTTPException(
                    status_code=503,
                    detail=f"Catalog validation required but repository is unavailable: {exc}",
                ) from exc
            warnings.append(f"Catalog validation skipped: {exc}")

    repaired: DeckRepairResult = linter.repair(deck_tuples, existing_card_ids=existing_card_ids)
    validation: DeckValidationResult = linter.validate(
        repaired.repaired_deck,
        existing_card_ids=existing_card_ids,
    )
    validation.warnings.extend(warnings)
    repaired_cards = [
        DeckCardInput(card_id=card_id, copies=copies, colors=colors)
        for card_id, copies, colors in repaired.repaired_deck
    ]

    return DeckRepairResponse(
        repaired_cards=repaired_cards,
        notes=repaired.notes,
        validation=DeckValidationResponse(
            is_legal=validation.is_legal,
            errors=validation.errors,
            warnings=validation.warnings,
            total_cards=validation.total_cards,
            issues=[
                {
                    "code": issue.code,
                    "message": issue.message,
                    "card_id": issue.card_id,
                    "expected": issue.expected,
                    "actual": issue.actual,
                }
                for issue in validation.issues
            ],
        ),
    )
