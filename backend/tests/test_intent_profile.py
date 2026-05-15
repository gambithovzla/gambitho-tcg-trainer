from src.domain.simulation.intent_profile import DeckIntentCard, infer_intent_weights
from src.infra.db.postgres.card_repository import CardIntentProfile


def test_infer_intent_weights_prefers_song_when_song_cards_dominate() -> None:
    deck = [
        DeckIntentCard(card_id="song_1", copies=4, card_type="Song", subtypes=["Song"]),
        DeckIntentCard(card_id="song_2", copies=4, card_type="Song", subtypes=["Song"]),
        DeckIntentCard(card_id="char_1", copies=2, card_type="Character", cost=3, strength=2, willpower=2, lore=1),
    ]

    weights = infer_intent_weights(deck)

    assert weights["song"] > weights["aggressive"]
    assert weights["song"] > weights["defender"]


def test_infer_intent_weights_uses_catalog_profile_when_available() -> None:
    deck = [DeckIntentCard(card_id="c1", copies=4, card_type="Action", cost=1)]
    catalog = {
        "c1": CardIntentProfile(
            card_id="c1",
            cost=3,
            strength=2,
            willpower=5,
            lore=2,
            card_type="Character",
            subtypes=["Dreamborn"],
        )
    }

    weights = infer_intent_weights(deck, catalog_profiles=catalog)

    assert weights["quester"] > 0.2
    assert weights["defender"] > 0.15
