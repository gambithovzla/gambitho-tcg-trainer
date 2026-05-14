from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.domain.linter.lorcana_linter import DeckValidationResult, LorcanaDeckLinter

router = APIRouter()


class DeckCardInput(BaseModel):
    card_id: str = Field(..., min_length=1)
    copies: int = Field(..., ge=1, le=4)
    colors: list[str] = Field(default_factory=list, max_length=2)


class DeckValidationRequest(BaseModel):
    cards: list[DeckCardInput]


class DeckValidationResponse(BaseModel):
    is_legal: bool
    errors: list[str]
    warnings: list[str]
    total_cards: int


@router.post("/validate", response_model=DeckValidationResponse)
def validate_deck(payload: DeckValidationRequest) -> DeckValidationResponse:
    linter = LorcanaDeckLinter()
    result: DeckValidationResult = linter.validate(
        deck=[(card.card_id, card.copies, card.colors) for card in payload.cards]
    )
    return DeckValidationResponse(
        is_legal=result.is_legal,
        errors=result.errors,
        warnings=result.warnings,
        total_cards=result.total_cards,
    )
