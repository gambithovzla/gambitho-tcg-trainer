from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from src.infra.db.postgres.card_repository import CatalogCard


@dataclass(frozen=True)
class CardDefinition:
    card_id: str
    name: str
    card_type: str | None
    cost: int
    strength: int | None
    willpower: int | None
    lore: int | None
    inkwell_inkable: bool
    rules_text: str
    keywords: frozenset[str]
    move_cost: int | None = None
    subtypes: tuple[str, ...] = ()

    def has_keyword(self, keyword: str) -> bool:
        target = keyword.lower()
        return any(item.lower() == target for item in self.keywords)

    @classmethod
    def from_catalog(cls, card: CatalogCard) -> CardDefinition:
        from src.domain.engine.keywords import extract_keywords

        return cls(
            card_id=card.id,
            name=card.name,
            card_type=card.card_type,
            cost=max(0, card.cost or 0),
            strength=card.strength,
            willpower=card.willpower,
            lore=card.lore,
            move_cost=card.move_cost,
            inkwell_inkable=bool(card.inkwell_inkable),
            rules_text=card.rules_text or "",
            keywords=extract_keywords(card.rules_text or ""),
            subtypes=tuple(card.subtypes or ()),
        )


@dataclass
class CardInstance:
    instance_id: str
    card_id: str
    owner_id: int


@dataclass
class CharacterInPlay:
    instance: CardInstance
    definition: CardDefinition
    damage: int = 0
    exerted: bool = False
    summoning_sick: bool = True
    strength_bonus_this_turn: int = 0
    at_location_index: int | None = None

    @property
    def strength(self) -> int:
        base = max(1, self.definition.strength or 1)
        return base + max(0, self.strength_bonus_this_turn)

    @property
    def willpower(self) -> int:
        return max(1, self.definition.willpower or 1)

    @property
    def lore_value(self) -> int:
        return max(0, self.definition.lore or 0)

    @property
    def is_banished(self) -> bool:
        return self.damage >= self.willpower

    @property
    def is_ready_for_quest(self) -> bool:
        return not self.exerted and not self.summoning_sick

    def has_keyword(self, keyword: str) -> bool:
        return keyword.lower() in {item.lower() for item in self.definition.keywords}


@dataclass
class LocationInPlay:
    """CR 6.5: locations are never ready or exerted; lore is gained at Set step."""

    instance: CardInstance
    definition: CardDefinition
    damage: int = 0

    @property
    def willpower(self) -> int:
        return max(1, self.definition.willpower or 1)

    @property
    def lore_value(self) -> int:
        return max(0, self.definition.lore or 0)

    @property
    def is_banished(self) -> bool:
        return self.damage >= self.willpower


@dataclass
class ItemInPlay:
    instance: CardInstance
    definition: CardDefinition
    exerted: bool = False


@dataclass
class BagEntry:
    effect_type: str
    player_id: int
    payload: dict[str, object] = field(default_factory=dict)


@dataclass
class RealPlayerState:
    player_id: int
    lore: int = 0
    deck: list[str] = field(default_factory=list)
    hand: list[str] = field(default_factory=list)
    discard: list[str] = field(default_factory=list)
    battlefield: list[CharacterInPlay] = field(default_factory=list)
    locations: list[LocationInPlay] = field(default_factory=list)
    items: list[ItemInPlay] = field(default_factory=list)
    ink_total: int = 0
    ink_available: int = 0
    inked_this_turn: bool = False


@dataclass
class RealGameState:
    active_player_id: int = 1
    turn_number: int = 1
    phase: str = "main"
    total_turns_taken: int = 0
    winner_player_id: int | None = None
    action_log: list[str] = field(default_factory=list)
    turn_protocol_version: str = "real-5"
    engine_mode: str = "real_cards"
    players: dict[int, RealPlayerState] = field(default_factory=dict)
    instances: dict[str, CardInstance] = field(default_factory=dict)
    definitions: dict[str, CardDefinition] = field(default_factory=dict)
    bag: list[BagEntry] = field(default_factory=list)


class CatalogProvider(Protocol):
    def get_cards(self, card_ids: list[str]) -> dict[str, CatalogCard]: ...
