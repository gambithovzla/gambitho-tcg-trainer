from __future__ import annotations

import random
import uuid
from dataclasses import dataclass

from src.domain.engine.card_model import CardDefinition, CardInstance


@dataclass(frozen=True)
class DeckEntry:
    card_id: str
    copies: int = 1


def expand_deck_entries(
    entries: list[DeckEntry],
    *,
    owner_id: int,
    definitions: dict[str, CardDefinition],
) -> tuple[list[str], dict[str, CardInstance]]:
    deck_order: list[str] = []
    instances: dict[str, CardInstance] = {}

    for entry in entries:
        if entry.card_id not in definitions:
            raise ValueError(f"Unknown card_id in deck: {entry.card_id}")
        for _ in range(entry.copies):
            instance_id = f"p{owner_id}-{uuid.uuid4().hex[:12]}"
            instances[instance_id] = CardInstance(
                instance_id=instance_id,
                card_id=entry.card_id,
                owner_id=owner_id,
            )
            deck_order.append(instance_id)

    return deck_order, instances


def shuffle_deck(deck: list[str], rng: random.Random) -> list[str]:
    shuffled = list(deck)
    rng.shuffle(shuffled)
    return shuffled


def draw_cards(deck: list[str], hand: list[str], count: int) -> None:
    for _ in range(count):
        if not deck:
            return
        hand.append(deck.pop(0))
