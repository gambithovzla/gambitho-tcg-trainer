from __future__ import annotations

import pytest

from src.domain.engine.card_model import (
    CardDefinition,
    CardInstance,
    CatalogProvider,
    CharacterInPlay,
    LocationInPlay,
)
from src.domain.engine.actions import ChallengeAction, EndTurnAction, QuestAction
from src.domain.engine.keywords import (
    apply_damage,
    apply_support_on_quest,
    can_challenge,
    can_challenge_evasive_defender,
    can_quest,
    challenger_bonus,
    extract_keywords,
    legal_challenge_defender_indices,
    reckless_must_challenge,
    resist_reduction,
)
from src.domain.engine.card_model import CardInstance, CharacterInPlay
from src.domain.engine.real_actions import SingSongFromHandAction
from src.domain.engine.real_deck import DeckEntry
from src.domain.engine.real_fsm import RealCardGameEngine, RealMatchSetup
from src.domain.engine.real_actions import (
    MoveToLocationAction,
    PlayActionFromHandAction,
    PlayCardFromHandAction,
    PlayItemFromHandAction,
    PlayLocationFromHandAction,
)
from src.domain.engine.keywords import legal_challenge_location_indices
from src.domain.simulation.real_match import simulate_real_card_match
from src.infra.db.postgres.card_repository import CatalogCard
from fastapi.testclient import TestClient

from src.api.main import app


def _catalog_card(
    card_id: str,
    *,
    name: str,
    card_type: str = "Character",
    cost: int = 2,
    strength: int = 2,
    willpower: int = 2,
    lore: int = 1,
    rules_text: str = "",
    inkwell: bool = True,
) -> CatalogCard:
    return CatalogCard(
        id=card_id,
        name=name,
        subtitle=None,
        set_id="1",
        collector_number=card_id,
        rarity="Common",
        card_type=card_type,
        cost=cost,
        strength=strength,
        willpower=willpower,
        lore=lore,
        move_cost=None,
        inkwell_inkable=inkwell,
        color_aspect=["Amber"],
        subtypes=["Storyborn"],
        rules_text=rules_text,
        image_url=None,
        image_thumbnail_url=None,
    )


class InMemoryCatalog(CatalogProvider):
    def __init__(self, cards: dict[str, CatalogCard]) -> None:
        self._cards = cards

    def get_cards(self, card_ids: list[str]) -> dict[str, CatalogCard]:
        return {card_id: self._cards[card_id] for card_id in card_ids if card_id in self._cards}


def _standard_deck(prefix: str, start_id: int = 1) -> list[DeckEntry]:
    return [
        DeckEntry(card_id=f"{prefix}-{start_id + index}", copies=4)
        for index in range(15)
    ]


def _build_test_catalog(prefix: str) -> InMemoryCatalog:
    cards: dict[str, CatalogCard] = {}
    for index in range(15):
        card_id = f"{prefix}-{index + 1}"
        rules = "Evasive" if index == 0 else ""
        cards[card_id] = _catalog_card(
            card_id,
            name=f"{prefix} Hero {index + 1}",
            cost=2 + (index % 3),
            strength=2 + (index % 2),
            willpower=3,
            lore=1 + (index % 2),
            rules_text=rules,
        )
    return InMemoryCatalog(cards)


def test_extract_keywords_finds_evasive() -> None:
    keywords = extract_keywords("Evasive (Only characters with Evasive can challenge this character.)")
    assert "Evasive" in keywords


def test_ward_does_not_block_challenge() -> None:
    """CR 9.12: Ward — opponents can't choose this character except to challenge."""
    defender = CharacterInPlay(
        instance=CardInstance(instance_id="iw", card_id="w", owner_id=2),
        definition=CardDefinition(
            card_id="w",
            name="Ward Defender",
            card_type="Character",
            cost=2,
            strength=2,
            willpower=2,
            lore=1,
            inkwell_inkable=True,
            rules_text="Ward",
            keywords=frozenset({"Ward"}),
        ),
    )
    attacker = CharacterInPlay(
        instance=CardInstance(instance_id="ia", card_id="a", owner_id=1),
        definition=CardDefinition(
            card_id="a",
            name="Attacker",
            card_type="Character",
            cost=2,
            strength=5,
            willpower=2,
            lore=1,
            inkwell_inkable=True,
            rules_text="",
            keywords=frozenset(),
        ),
    )
    assert can_challenge(attacker, defender) is True


def test_resist_reduces_damage() -> None:
    definition = CardDefinition(
        card_id="r",
        name="Resist Two",
        card_type="Character",
        cost=3,
        strength=2,
        willpower=5,
        lore=1,
        inkwell_inkable=True,
        rules_text="Resist +2",
        keywords=frozenset({"Resist"}),
    )
    character = CharacterInPlay(
        instance=CardInstance(instance_id="ir", card_id="r", owner_id=1),
        definition=definition,
    )
    assert resist_reduction(definition.rules_text, definition.keywords) == 2
    dealt = apply_damage(character, 4)
    assert dealt == 2
    assert character.damage == 2


def test_challenger_bonus_parsed() -> None:
    definition = CardDefinition(
        card_id="c",
        name="Challenger",
        card_type="Character",
        cost=3,
        strength=2,
        willpower=3,
        lore=1,
        inkwell_inkable=True,
        rules_text="Challenger +2",
        keywords=frozenset({"Challenger"}),
    )
    assert challenger_bonus(definition.rules_text, definition.keywords) == 2


def test_mulligan_when_no_inkable() -> None:
    class NoInkP1Catalog(CatalogProvider):
        def get_cards(self, card_ids: list[str]) -> dict[str, CatalogCard]:
            base = _merged_catalog().get_cards(card_ids)
            for card_id in card_ids:
                if card_id.startswith("p1-"):
                    source = base[card_id]
                    base[card_id] = _catalog_card(
                        card_id,
                        name=source.name,
                        card_type=source.card_type or "Character",
                        cost=source.cost or 2,
                        strength=source.strength or 2,
                        willpower=source.willpower or 2,
                        lore=source.lore or 1,
                        rules_text=source.rules_text,
                        inkwell=False,
                    )
            return base

    setup = RealMatchSetup(
        player_one_deck=_standard_deck("p1"),
        player_two_deck=_standard_deck("p2"),
        rng_seed=99,
        mulligan_no_ink=True,
    )
    engine = RealCardGameEngine(catalog=NoInkP1Catalog(), setup=setup)
    assert any("mulligan" in line.lower() for line in engine.state.action_log)


def test_song_and_action_in_legal_actions() -> None:
    catalog = InMemoryCatalog(
        {
            "song-1": _catalog_card("song-1", name="Heal Song", card_type="Song", cost=2, lore=2),
            "action-1": _catalog_card(
                "action-1",
                name="Quick Shot",
                card_type="Action",
                cost=1,
                lore=0,
                rules_text="Gain 2 lore.",
            ),
            "char-1": _catalog_card("char-1", name="Hero", cost=1, strength=2, willpower=3),
        }
    )
    deck_one = [DeckEntry(card_id="song-1", copies=20), DeckEntry(card_id="char-1", copies=40)]
    deck_two = [DeckEntry(card_id="action-1", copies=30), DeckEntry(card_id="char-1", copies=30)]
    setup = RealMatchSetup(
        player_one_deck=deck_one,
        player_two_deck=deck_two,
        mulligan_no_ink=False,
        rng_seed=1,
    )
    engine = RealCardGameEngine(catalog=catalog, setup=setup)
    for _ in range(40):
        legal = engine.get_legal_actions()
        if any(isinstance(a, SingSongFromHandAction) for a in legal):
            break
        for action in legal:
            if action.action_type in {"ink_card", "play_card"}:
                engine.apply_action(action)
                break
        else:
            engine.apply_action(legal[-1])
    assert any(isinstance(a, SingSongFromHandAction) for a in engine.get_legal_actions())


def test_alert_can_challenge_evasive_defender() -> None:
    defender = CharacterInPlay(
        instance=CardInstance(instance_id="id", card_id="d", owner_id=2),
        definition=CardDefinition(
            card_id="d",
            name="Evasive Defender",
            card_type="Character",
            cost=3,
            strength=2,
            willpower=4,
            lore=2,
            inkwell_inkable=True,
            rules_text="Evasive",
            keywords=frozenset({"Evasive"}),
        ),
    )
    alert_attacker = CharacterInPlay(
        instance=CardInstance(instance_id="ia", card_id="a", owner_id=1),
        definition=CardDefinition(
            card_id="a",
            name="Alert Scout",
            card_type="Character",
            cost=2,
            strength=3,
            willpower=2,
            lore=1,
            inkwell_inkable=True,
            rules_text="Alert (This character can challenge as if they had Evasive.)",
            keywords=frozenset({"Alert"}),
        ),
    )
    assert can_challenge_evasive_defender(alert_attacker) is True
    assert can_challenge(alert_attacker, defender) is True
    assert alert_attacker.has_keyword("Evasive") is False


def test_bodyguard_optional_enter_exerted_on_play() -> None:
    catalog = InMemoryCatalog(
        {
            "guard-1": _catalog_card(
                "guard-1",
                name="Guard",
                rules_text="Bodyguard",
            ),
            "filler-1": _catalog_card("filler-1", name="Filler", cost=1),
        }
    )
    engine = RealCardGameEngine(
        catalog=catalog,
        setup=RealMatchSetup(
            player_one_deck=[DeckEntry(card_id="guard-1", copies=30), DeckEntry(card_id="filler-1", copies=30)],
            player_two_deck=[DeckEntry(card_id="filler-1", copies=60)],
            mulligan_no_ink=False,
            rng_seed=3,
        ),
    )
    p1 = engine.state.players[1]
    guard_index = next(
        index
        for index, instance_id in enumerate(p1.hand)
        if engine.state.instances[instance_id].card_id == "guard-1"
    )
    p1.ink_available = 10
    p1.ink_total = 10

    legal = engine.get_legal_actions()
    play_opts = [
        action
        for action in legal
        if isinstance(action, PlayCardFromHandAction) and action.hand_index == guard_index
    ]
    assert len(play_opts) == 2
    assert {action.enter_exerted for action in play_opts} == {False, True}

    engine.apply_action(
        PlayCardFromHandAction(player_id=1, hand_index=guard_index, enter_exerted=False)
    )
    assert len(p1.battlefield) == 1
    assert p1.battlefield[0].exerted is False

    engine.apply_action(
        PlayCardFromHandAction(player_id=1, hand_index=guard_index, enter_exerted=True)
    )
    assert p1.battlefield[-1].exerted is True


def test_bodyguard_restricts_challenge_targets() -> None:
    bodyguard = CharacterInPlay(
        instance=CardInstance(instance_id="ib", card_id="b", owner_id=2),
        definition=CardDefinition(
            card_id="b",
            name="Guard",
            card_type="Character",
            cost=2,
            strength=2,
            willpower=4,
            lore=1,
            inkwell_inkable=True,
            rules_text="Bodyguard",
            keywords=frozenset({"Bodyguard"}),
        ),
        exerted=True,
    )
    vanilla = CharacterInPlay(
        instance=CardInstance(instance_id="iv", card_id="v", owner_id=2),
        definition=CardDefinition(
            card_id="v",
            name="Vanilla",
            card_type="Character",
            cost=2,
            strength=2,
            willpower=2,
            lore=2,
            inkwell_inkable=True,
            rules_text="",
            keywords=frozenset(),
        ),
        exerted=True,
    )
    attacker = CharacterInPlay(
        instance=CardInstance(instance_id="ia", card_id="a", owner_id=1),
        definition=CardDefinition(
            card_id="a",
            name="Attacker",
            card_type="Character",
            cost=2,
            strength=3,
            willpower=2,
            lore=1,
            inkwell_inkable=True,
            rules_text="",
            keywords=frozenset(),
        ),
    )
    defenders = [vanilla, bodyguard]
    assert legal_challenge_defender_indices(attacker, defenders) == [1]


def test_reckless_cannot_quest_and_must_challenge() -> None:
    reckless = CharacterInPlay(
        instance=CardInstance(instance_id="ir", card_id="r", owner_id=1),
        definition=CardDefinition(
            card_id="r",
            name="Reckless Fighter",
            card_type="Character",
            cost=2,
            strength=4,
            willpower=3,
            lore=2,
            inkwell_inkable=True,
            rules_text="Reckless",
            keywords=frozenset({"Reckless"}),
        ),
        summoning_sick=False,
    )
    defender = CharacterInPlay(
        instance=CardInstance(instance_id="id", card_id="d", owner_id=2),
        definition=CardDefinition(
            card_id="d",
            name="Target",
            card_type="Character",
            cost=2,
            strength=1,
            willpower=2,
            lore=1,
            inkwell_inkable=True,
            rules_text="",
            keywords=frozenset(),
        ),
        exerted=True,
    )
    assert can_quest(reckless) is False
    assert reckless_must_challenge([reckless], [defender], []) is True

    catalog = InMemoryCatalog(
        {
            "reckless-1": _catalog_card(
                "reckless-1",
                name="Reckless Fighter",
                rules_text="Reckless",
            ),
            "target-1": _catalog_card("target-1", name="Target", strength=1, willpower=2),
        }
    )
    deck_r = [DeckEntry(card_id="reckless-1", copies=30), DeckEntry(card_id="target-1", copies=30)]
    deck_t = [DeckEntry(card_id="target-1", copies=30), DeckEntry(card_id="reckless-1", copies=30)]
    engine = RealCardGameEngine(
        catalog=catalog,
        setup=RealMatchSetup(
            player_one_deck=deck_r,
            player_two_deck=deck_t,
            mulligan_no_ink=False,
            rng_seed=5,
        ),
    )
    p1 = engine.state.players[1]
    p2 = engine.state.players[2]
    p1.battlefield = [
        CharacterInPlay(
            instance=CardInstance(instance_id="r1", card_id="reckless-1", owner_id=1),
            definition=engine.state.definitions["reckless-1"],
            summoning_sick=False,
        )
    ]
    p2.battlefield = [
        CharacterInPlay(
            instance=CardInstance(instance_id="d1", card_id="target-1", owner_id=2),
            definition=engine.state.definitions["target-1"],
            exerted=True,
            summoning_sick=False,
        )
    ]
    legal = engine.get_legal_actions()
    assert not any(isinstance(a, QuestAction) for a in legal)
    assert not any(isinstance(a, EndTurnAction) for a in legal)
    assert any(isinstance(a, ChallengeAction) for a in legal)


def test_support_grants_strength_bonus_on_quest() -> None:
    supporter = CharacterInPlay(
        instance=CardInstance(instance_id="is", card_id="s", owner_id=1),
        definition=CardDefinition(
            card_id="s",
            name="Helper",
            card_type="Character",
            cost=3,
            strength=3,
            willpower=4,
            lore=1,
            inkwell_inkable=True,
            rules_text="Support",
            keywords=frozenset({"Support"}),
        ),
    )
    ally = CharacterInPlay(
        instance=CardInstance(instance_id="ia", card_id="a", owner_id=1),
        definition=CardDefinition(
            card_id="a",
            name="Ally",
            card_type="Character",
            cost=2,
            strength=2,
            willpower=3,
            lore=2,
            inkwell_inkable=True,
            rules_text="",
            keywords=frozenset(),
        ),
    )
    battlefield = [supporter, ally]
    index = apply_support_on_quest(supporter, battlefield, support_target_index=1)
    assert index == 1
    assert ally.strength_bonus_this_turn == 3
    assert ally.strength == 5


def test_can_challenge_requires_evasive_or_alert_attacker() -> None:
    from src.domain.engine.card_model import CardInstance, CharacterInPlay

    definition_attacker = CardDefinition(
        card_id="a",
        name="Attacker",
        card_type="Character",
        cost=2,
        strength=2,
        willpower=2,
        lore=1,
        inkwell_inkable=True,
        rules_text="",
        keywords=frozenset(),
    )
    definition_defender = CardDefinition(
        card_id="d",
        name="Defender",
        card_type="Character",
        cost=2,
        strength=2,
        willpower=2,
        lore=1,
        inkwell_inkable=True,
        rules_text="Evasive",
        keywords=frozenset({"Evasive"}),
    )
    instance_a = CardInstance(instance_id="ia", card_id="a", owner_id=1)
    instance_d = CardInstance(instance_id="id", card_id="d", owner_id=2)
    attacker = CharacterInPlay(instance=instance_a, definition=definition_attacker)
    defender = CharacterInPlay(instance=instance_d, definition=definition_defender)

    assert can_challenge(attacker, defender) is False

    definition_evasive_attacker = CardDefinition(
        card_id="ae",
        name="Evasive Attacker",
        card_type="Character",
        cost=2,
        strength=2,
        willpower=2,
        lore=1,
        inkwell_inkable=True,
        rules_text="Evasive",
        keywords=frozenset({"Evasive"}),
    )
    evasive_attacker = CharacterInPlay(
        instance=CardInstance(instance_id="ie", card_id="ae", owner_id=1),
        definition=definition_evasive_attacker,
    )
    assert can_challenge(evasive_attacker, defender) is True


def _merged_catalog() -> CatalogProvider:
    class MergedCatalog(CatalogProvider):
        def get_cards(self, card_ids: list[str]) -> dict[str, CatalogCard]:
            merged = _build_test_catalog("p1").get_cards(card_ids)
            merged.update(_build_test_catalog("p2").get_cards(card_ids))
            return merged

    return MergedCatalog()


def test_play_location_and_quest_for_lore() -> None:
    catalog = InMemoryCatalog(
        {
            "loc-1": _catalog_card(
                "loc-1",
                name="Castle",
                card_type="Location",
                cost=2,
                lore=2,
                willpower=5,
            ),
            "filler-1": _catalog_card("filler-1", name="Filler", cost=1),
        }
    )
    engine = RealCardGameEngine(
        catalog=catalog,
        setup=RealMatchSetup(
            player_one_deck=[DeckEntry(card_id="loc-1", copies=30), DeckEntry(card_id="filler-1", copies=30)],
            player_two_deck=[DeckEntry(card_id="filler-1", copies=60)],
            mulligan_no_ink=False,
            rng_seed=11,
        ),
    )
    p1 = engine.state.players[1]
    loc_index = next(
        index
        for index, instance_id in enumerate(p1.hand)
        if engine.state.instances[instance_id].card_id == "loc-1"
    )
    p1.ink_available = 10
    p1.ink_total = 10

    engine.apply_action(PlayLocationFromHandAction(player_id=1, hand_index=loc_index))
    assert len(p1.locations) == 1
    assert p1.lore == 0
    assert not hasattr(p1.locations[0], "exerted")

    legal = engine.get_legal_actions()
    assert not any(action.action_type == "quest_location" for action in legal)

    engine.apply_action(EndTurnAction(player_id=1))
    engine.apply_action(EndTurnAction(player_id=2))
    assert p1.lore == 2
    assert any("Bag push: location_set_lore" in line for line in engine.state.action_log)
    assert any("Bag resolve: location_set_lore" in line for line in engine.state.action_log)


def test_bag_is_lifo_for_location_set_lore() -> None:
    catalog = InMemoryCatalog(
        {
            "loc-a": _catalog_card(
                "loc-a", name="A-Location", card_type="Location", cost=2, lore=1, willpower=4
            ),
            "loc-b": _catalog_card(
                "loc-b", name="B-Location", card_type="Location", cost=2, lore=2, willpower=4
            ),
            "filler-1": _catalog_card("filler-1", name="Filler", cost=1),
        }
    )
    engine = RealCardGameEngine(
        catalog=catalog,
        setup=RealMatchSetup(
            player_one_deck=[
                DeckEntry(card_id="loc-a", copies=20),
                DeckEntry(card_id="loc-b", copies=20),
                DeckEntry(card_id="filler-1", copies=20),
            ],
            player_two_deck=[DeckEntry(card_id="filler-1", copies=60)],
            mulligan_no_ink=False,
            rng_seed=31,
        ),
    )
    p1 = engine.state.players[1]
    p1.locations = [
        LocationInPlay(
            instance=CardInstance(instance_id="la", card_id="loc-a", owner_id=1),
            definition=engine.state.definitions["loc-a"],
        ),
        LocationInPlay(
            instance=CardInstance(instance_id="lb", card_id="loc-b", owner_id=1),
            definition=engine.state.definitions["loc-b"],
        ),
    ]
    p1.lore = 0
    engine.apply_action(EndTurnAction(player_id=1))
    engine.apply_action(EndTurnAction(player_id=2))
    resolves = [line for line in engine.state.action_log if "Bag resolve: location_set_lore" in line]
    assert len(resolves) >= 2
    assert "B-Location" in resolves[-2]
    assert "A-Location" in resolves[-1]
    assert p1.lore == 3


def test_challenge_location_deals_damage_without_retaliation() -> None:
    castle = LocationInPlay(
        instance=CardInstance(instance_id="il", card_id="loc", owner_id=2),
        definition=CardDefinition(
            card_id="loc",
            name="Castle",
            card_type="Location",
            cost=3,
            strength=None,
            willpower=4,
            lore=2,
            inkwell_inkable=True,
            rules_text="",
            keywords=frozenset(),
            move_cost=1,
        ),
    )
    attacker = CharacterInPlay(
        instance=CardInstance(instance_id="ia", card_id="atk", owner_id=1),
        definition=CardDefinition(
            card_id="atk",
            name="Fighter",
            card_type="Character",
            cost=2,
            strength=5,
            willpower=3,
            lore=1,
            inkwell_inkable=True,
            rules_text="",
            keywords=frozenset(),
        ),
        summoning_sick=False,
    )
    assert legal_challenge_location_indices([castle]) == [0]

    catalog = InMemoryCatalog(
        {
            "loc-1": _catalog_card(
                "loc-1",
                name="Castle",
                card_type="Location",
                cost=2,
                lore=1,
                willpower=4,
            ),
            "atk-1": _catalog_card("atk-1", name="Fighter", strength=5, willpower=3),
            "filler-1": _catalog_card("filler-1", name="Filler", cost=1),
        }
    )
    engine = RealCardGameEngine(
        catalog=catalog,
        setup=RealMatchSetup(
            player_one_deck=[DeckEntry(card_id="atk-1", copies=30), DeckEntry(card_id="filler-1", copies=30)],
            player_two_deck=[DeckEntry(card_id="loc-1", copies=30), DeckEntry(card_id="filler-1", copies=30)],
            mulligan_no_ink=False,
            rng_seed=20,
        ),
    )
    p1 = engine.state.players[1]
    p2 = engine.state.players[2]
    p1.battlefield = [
        CharacterInPlay(
            instance=CardInstance(instance_id="a1", card_id="atk-1", owner_id=1),
            definition=engine.state.definitions["atk-1"],
            summoning_sick=False,
        )
    ]
    p2.locations = [
        LocationInPlay(
            instance=CardInstance(instance_id="l1", card_id="loc-1", owner_id=2),
            definition=engine.state.definitions["loc-1"],
        )
    ]
    engine.apply_action(
        ChallengeAction(
            player_id=1,
            defender_index=0,
            attacker_index=0,
            defender_kind="location",
        )
    )
    assert p1.battlefield[0].damage == 0
    assert len(p2.locations) == 0
    assert any("challenges location" in line for line in engine.state.action_log)
    assert any("Castle banished" in line for line in engine.state.action_log)


def test_move_to_location_pays_move_cost() -> None:
    catalog = InMemoryCatalog(
        {
            "loc-1": _catalog_card(
                "loc-1",
                name="Castle",
                card_type="Location",
                cost=2,
                lore=1,
                willpower=5,
            ),
            "hero-1": _catalog_card("hero-1", name="Hero", cost=1, strength=2, willpower=3),
            "filler-1": _catalog_card("filler-1", name="Filler", cost=1),
        }
    )
    class CatalogWithMove(CatalogProvider):
        def get_cards(self, card_ids: list[str]) -> dict[str, CatalogCard]:
            out = catalog.get_cards(card_ids)
            if "loc-1" in out:
                base = out["loc-1"]
                out["loc-1"] = CatalogCard(
                    id=base.id,
                    name=base.name,
                    subtitle=base.subtitle,
                    set_id=base.set_id,
                    collector_number=base.collector_number,
                    rarity=base.rarity,
                    card_type=base.card_type,
                    cost=base.cost,
                    strength=base.strength,
                    willpower=base.willpower,
                    lore=base.lore,
                    move_cost=2,
                    inkwell_inkable=base.inkwell_inkable,
                    color_aspect=base.color_aspect,
                    subtypes=base.subtypes,
                    rules_text=base.rules_text,
                    image_url=base.image_url,
                    image_thumbnail_url=base.image_thumbnail_url,
                )
            return out

    engine = RealCardGameEngine(
        catalog=CatalogWithMove(),
        setup=RealMatchSetup(
            player_one_deck=[DeckEntry(card_id="hero-1", copies=30), DeckEntry(card_id="loc-1", copies=15), DeckEntry(card_id="filler-1", copies=15)],
            player_two_deck=[DeckEntry(card_id="filler-1", copies=60)],
            mulligan_no_ink=False,
            rng_seed=21,
        ),
    )
    p1 = engine.state.players[1]
    p1.battlefield = [
        CharacterInPlay(
            instance=CardInstance(instance_id="h1", card_id="hero-1", owner_id=1),
            definition=engine.state.definitions["hero-1"],
            summoning_sick=False,
        )
    ]
    p1.locations = [
        LocationInPlay(
            instance=CardInstance(instance_id="l1", card_id="loc-1", owner_id=1),
            definition=engine.state.definitions["loc-1"],
        )
    ]
    p1.ink_available = 5
    p1.ink_total = 5
    engine.apply_action(MoveToLocationAction(player_id=1, character_index=0, location_index=0))
    assert p1.battlefield[0].at_location_index == 0
    assert p1.ink_available == 3
    assert any("moves Hero to Castle" in line for line in engine.state.action_log)


def test_play_item_stays_in_play() -> None:
    catalog = InMemoryCatalog(
        {
            "item-1": _catalog_card("item-1", name="Dagger", card_type="Item", cost=1),
            "filler-1": _catalog_card("filler-1", name="Filler", cost=1),
        }
    )
    engine = RealCardGameEngine(
        catalog=catalog,
        setup=RealMatchSetup(
            player_one_deck=[DeckEntry(card_id="item-1", copies=30), DeckEntry(card_id="filler-1", copies=30)],
            player_two_deck=[DeckEntry(card_id="filler-1", copies=60)],
            mulligan_no_ink=False,
            rng_seed=12,
        ),
    )
    p1 = engine.state.players[1]
    item_index = next(
        index
        for index, instance_id in enumerate(p1.hand)
        if engine.state.instances[instance_id].card_id == "item-1"
    )
    p1.ink_available = 10
    engine.apply_action(PlayItemFromHandAction(player_id=1, hand_index=item_index))
    assert len(p1.items) == 1
    assert p1.items[0].definition.name == "Dagger"
    assert not any(action.action_type == "quest_location" for action in engine.get_legal_actions())


def test_item_rules_text_effects_queue_to_bag() -> None:
    catalog = InMemoryCatalog(
        {
            "item-1": _catalog_card(
                "item-1",
                name="Lucky Charm",
                card_type="Item",
                cost=1,
                rules_text="When you play this item, gain 2 lore. Draw a card.",
            ),
            "filler-1": _catalog_card("filler-1", name="Filler", cost=1),
        }
    )
    engine = RealCardGameEngine(
        catalog=catalog,
        setup=RealMatchSetup(
            player_one_deck=[DeckEntry(card_id="item-1", copies=30), DeckEntry(card_id="filler-1", copies=30)],
            player_two_deck=[DeckEntry(card_id="filler-1", copies=60)],
            mulligan_no_ink=False,
            rng_seed=17,
        ),
    )
    p1 = engine.state.players[1]
    start_hand = len(p1.hand)
    item_index = next(
        index
        for index, instance_id in enumerate(p1.hand)
        if engine.state.instances[instance_id].card_id == "item-1"
    )
    p1.ink_available = 10
    engine.apply_action(PlayItemFromHandAction(player_id=1, hand_index=item_index))
    assert p1.lore == 2
    assert len(p1.hand) == start_hand
    assert any("Bag push: gain_lore (Lucky Charm)." in line for line in engine.state.action_log)
    assert any("Bag push: draw_card (Lucky Charm)." in line for line in engine.state.action_log)
    assert any("Bag resolve: draw_card (Lucky Charm)." in line for line in engine.state.action_log)
    assert any("Bag resolve: gain_lore (Lucky Charm)." in line for line in engine.state.action_log)


def test_action_rules_text_effects_queue_to_bag_lifo() -> None:
    catalog = InMemoryCatalog(
        {
            "act-1": _catalog_card(
                "act-1",
                name="Strategic Plan",
                card_type="Action",
                cost=1,
                    lore=0,
                rules_text="Gain 2 lore. Draw a card.",
            ),
            "filler-1": _catalog_card("filler-1", name="Filler", cost=1),
        }
    )
    engine = RealCardGameEngine(
        catalog=catalog,
        setup=RealMatchSetup(
            player_one_deck=[DeckEntry(card_id="act-1", copies=30), DeckEntry(card_id="filler-1", copies=30)],
            player_two_deck=[DeckEntry(card_id="filler-1", copies=60)],
            mulligan_no_ink=False,
            rng_seed=29,
        ),
    )
    p1 = engine.state.players[1]
    start_hand = len(p1.hand)
    action_index = next(
        index
        for index, instance_id in enumerate(p1.hand)
        if engine.state.instances[instance_id].card_id == "act-1"
    )
    p1.ink_available = 10
    engine.apply_action(PlayActionFromHandAction(player_id=1, hand_index=action_index))
    assert p1.lore == 2
    assert len(p1.hand) == start_hand
    resolve_lines = [
        line
        for line in engine.state.action_log
        if "Bag resolve:" in line and "Strategic Plan" in line
    ]
    assert resolve_lines[0].endswith("draw_card (Strategic Plan).")
    assert resolve_lines[1].endswith("gain_lore (Strategic Plan).")


def test_real_engine_plays_character_from_catalog() -> None:
    catalog = _merged_catalog()
    deck = _standard_deck("p1")
    setup = RealMatchSetup(
        player_one_deck=deck,
        player_two_deck=_standard_deck("p2"),
        target_lore=20,
        rng_seed=7,
    )
    engine = RealCardGameEngine(catalog=catalog, setup=setup)

    player = engine.state.players[1]
    assert len(player.hand) == 7

    for _ in range(30):
        legal = engine.get_legal_actions()
        play_actions = [action for action in legal if isinstance(action, PlayCardFromHandAction)]
        if play_actions:
            engine.apply_action(play_actions[0])
            break
        ink_actions = [action for action in legal if action.action_type == "ink_card"]
        if ink_actions:
            engine.apply_action(ink_actions[0])
        else:
            engine.apply_action(legal[-1])

    assert any(" plays " in line for line in engine.state.action_log)


def test_simulate_real_match_references_card_names() -> None:
    result = simulate_real_card_match(
        catalog=_merged_catalog(),
        player_one_deck=_standard_deck("p1"),
        player_two_deck=_standard_deck("p2"),
        max_turns=8,
        target_lore=6,
        rng_seed=42,
    )

    assert result.engine_mode == "real_cards"
    assert result.turn_protocol_version == "real-5"
    assert len(result.history) > 0
    assert len(result.cards_referenced) > 0


def test_real_match_api_with_fake_catalog(monkeypatch) -> None:
    merged = _build_test_catalog("p1")
    cards = merged.get_cards([f"p1-{i}" for i in range(1, 16)])
    cards.update(_build_test_catalog("p2").get_cards([f"p2-{i}" for i in range(1, 16)]))

    class FakeCatalog:
        def get_cards(self, card_ids: list[str]) -> dict[str, CatalogCard]:
            return {card_id: cards[card_id] for card_id in card_ids if card_id in cards}

    monkeypatch.setattr(
        "src.api.routes.real_simulation.PostgresCatalogProvider",
        lambda: FakeCatalog(),
    )

    client = TestClient(app)
    deck_payload = [{"card_id": f"p1-{i}", "copies": 4} for i in range(1, 16)]
    deck_payload_p2 = [{"card_id": f"p2-{i}", "copies": 4} for i in range(1, 16)]
    response = client.post(
        "/simulate/match/real",
        json={
            "player_one_deck": deck_payload,
            "player_two_deck": deck_payload_p2,
            "max_turns": 6,
            "target_lore": 5,
            "rng_seed": 99,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["engine_mode"] == "real_cards"
    assert body["turn_protocol_version"] == "real-5"
    assert body["cards_referenced"]
