from fastapi import APIRouter, HTTPException, Query

from pydantic import BaseModel, Field

from src.infra.db.postgres.card_repository import CatalogCard, PostgresCardRepository

router = APIRouter()


class CatalogCardResponse(BaseModel):
    id: str
    name: str
    subtitle: str | None = None
    set_id: str | None = None
    collector_number: str | None = None
    rarity: str | None = None
    card_type: str | None = None
    cost: int | None = None
    strength: int | None = None
    willpower: int | None = None
    lore: int | None = None
    move_cost: int | None = None
    inkwell_inkable: bool | None = None
    color_aspect: list[str] = Field(default_factory=list)
    subtypes: list[str] = Field(default_factory=list)
    rules_text: str = ""
    image_url: str | None = None
    image_thumbnail_url: str | None = None


class CatalogListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    cards: list[CatalogCardResponse]


def _to_response(card: CatalogCard) -> CatalogCardResponse:
    return CatalogCardResponse(
        id=card.id,
        name=card.name,
        subtitle=card.subtitle,
        set_id=card.set_id,
        collector_number=card.collector_number,
        rarity=card.rarity,
        card_type=card.card_type,
        cost=card.cost,
        strength=card.strength,
        willpower=card.willpower,
        lore=card.lore,
        move_cost=card.move_cost,
        inkwell_inkable=card.inkwell_inkable,
        color_aspect=card.color_aspect,
        subtypes=card.subtypes,
        rules_text=card.rules_text,
        image_url=card.image_url,
        image_thumbnail_url=card.image_thumbnail_url,
    )


@router.get("/cards", response_model=CatalogListResponse)
def list_cards(
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=48, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CatalogListResponse:
    repository = PostgresCardRepository()
    cards, total = repository.list_catalog_cards(search=search, limit=limit, offset=offset)
    return CatalogListResponse(
        total=total,
        limit=limit,
        offset=offset,
        cards=[_to_response(card) for card in cards],
    )


@router.get("/cards/{card_id}", response_model=CatalogCardResponse)
def get_card(card_id: str) -> CatalogCardResponse:
    repository = PostgresCardRepository()
    card = repository.get_catalog_card(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"Card '{card_id}' not found.")
    return _to_response(card)
