"""Golden Fase A: a full bot-vs-bot match using only catalog cards, end to end.

Closes the ISSUE-008 criterion "partida mínima con 2 mazos del catálogo y al menos
5 keywords verificados en log/estado": the match must reach a winner, reference only
catalog cards, exercise >= 5 distinct P0 keywords, and engage combat (a keyword-affected
subsystem), all deterministically under a fixed seed.
"""

from __future__ import annotations

import re

from src.domain.engine.card_model import CatalogProvider
from src.domain.engine.real_deck import DeckEntry
from src.domain.simulation.real_match import simulate_real_card_match
from src.infra.db.postgres.card_repository import CatalogCard

# (suffix, name, cost, strength, willpower, lore, rules_text)
# Kept cheap (cost 1-2) so the one-ink-per-turn bots actually cast every keyword
# carrier within a match, instead of leaving the 3-4 drops stranded in hand.
_KEYWORD_CARDS: list[tuple[str, str, int, int, int, int, str]] = [
    ("eva", "Evasive Scout", 1, 2, 3, 2, "Evasive"),
    ("rush", "Rushing Knight", 2, 3, 3, 1, "Rush"),
    ("guard", "Loyal Guard", 2, 2, 5, 1, "Bodyguard"),
    ("sup", "Helpful Ally", 2, 3, 4, 1, "Support"),
    ("res", "Stoic Tank", 2, 2, 6, 1, "Resist +1"),
    ("cha", "Bold Challenger", 1, 2, 3, 1, "Challenger +2"),
    ("ward", "Warded Sage", 1, 2, 3, 2, "Ward"),
]

_EXPECTED_KEYWORDS = {"Evasive", "Rush", "Bodyguard", "Support", "Resist", "Challenger", "Ward"}


def _card(
    card_id: str,
    *,
    name: str,
    cost: int,
    strength: int,
    willpower: int,
    lore: int,
    rules_text: str,
) -> CatalogCard:
    return CatalogCard(
        id=card_id,
        name=name,
        subtitle=None,
        set_id="1",
        collector_number=card_id,
        rarity="Common",
        card_type="Character",
        cost=cost,
        strength=strength,
        willpower=willpower,
        lore=lore,
        move_cost=None,
        inkwell_inkable=True,
        color_aspect=["Amber"],
        subtypes=["Storyborn"],
        rules_text=rules_text,
        image_url=None,
        image_thumbnail_url=None,
    )


def _build_deck(prefix: str, cards: dict[str, CatalogCard]) -> list[DeckEntry]:
    """15 unique ids x 4 copies = 60: 7 keyword carriers + 8 cheap vanilla questers."""
    entries: list[DeckEntry] = []
    for suffix, name, cost, strength, willpower, lore, rules_text in _KEYWORD_CARDS:
        card_id = f"{prefix}-{suffix}"
        cards[card_id] = _card(
            card_id,
            name=name,
            cost=cost,
            strength=strength,
            willpower=willpower,
            lore=lore,
            rules_text=rules_text,
        )
        entries.append(DeckEntry(card_id=card_id, copies=4))
    for index in range(8):
        card_id = f"{prefix}-q{index}"
        cards[card_id] = _card(
            card_id,
            name=f"Questing Villager {prefix}{index}",
            cost=1 + (index % 3),
            strength=1 + (index % 2),
            willpower=2,
            lore=2,
            rules_text="",
        )
        entries.append(DeckEntry(card_id=card_id, copies=4))
    return entries


class _GoldenCatalog(CatalogProvider):
    def __init__(self) -> None:
        self._cards: dict[str, CatalogCard] = {}
        self.deck_one = _build_deck("p1", self._cards)
        self.deck_two = _build_deck("p2", self._cards)

    def get_cards(self, card_ids: list[str]) -> dict[str, CatalogCard]:
        return {cid: self._cards[cid] for cid in card_ids if cid in self._cards}


def _keywords_seen(history: list[str]) -> set[str]:
    seen: set[str] = set()
    for line in history:
        match = re.search(r"keywords=([^)]*)\)", line)
        if not match:
            continue
        for token in match.group(1).split(","):
            token = token.strip()
            if token and token != "none":
                seen.add(token)
    return seen


def test_golden_real_match_reaches_winner_with_keywords_and_combat() -> None:
    catalog = _GoldenCatalog()
    result = simulate_real_card_match(
        catalog=catalog,
        player_one_deck=catalog.deck_one,
        player_two_deck=catalog.deck_two,
        max_turns=60,
        target_lore=18,
        rng_seed=18,
    )

    # The match runs entirely on catalog cards and terminates with a winner.
    assert result.engine_mode == "real_cards"
    assert result.turn_protocol_version == "real-5"
    assert result.winner_player_id in (1, 2)

    # Only catalog cards are referenced.
    catalog_names = {card.name for card in catalog._cards.values()}
    assert result.cards_referenced
    assert set(result.cards_referenced).issubset(catalog_names)

    # At least 5 distinct P0 keywords were exercised during the game.
    keywords = _keywords_seen(result.history)
    assert keywords.issubset(_EXPECTED_KEYWORDS)
    assert len(keywords) >= 5, f"only saw keywords {sorted(keywords)}"

    # Combat (a keyword-affected subsystem) actually engaged.
    assert any("challenges" in line for line in result.history)
