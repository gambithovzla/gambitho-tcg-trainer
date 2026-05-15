from src.infra.ingestion.lorcana_ingestor import LorcanaIngestor


def test_extract_cards_injects_setcode_from_lorcanajson_setdata() -> None:
    payload = {
        "code": "1",
        "hasAllCards": True,
        "metadata": {"formatVersion": "2.0.0"},
        "cards": [{"id": 1, "name": "Ariel", "fullName": "Ariel - On Human Legs", "type": "Character"}],
    }
    cards = LorcanaIngestor.extract_cards(payload)
    assert len(cards) == 1
    assert cards[0]["setCode"] == "1"


def test_extract_cards_does_not_override_existing_setcode() -> None:
    payload = {
        "code": "9",
        "hasAllCards": True,
        "cards": [
            {
                "id": 2,
                "name": "X",
                "fullName": "X - Y",
                "type": "Character",
                "setCode": "10",
            },
        ],
    }
    cards = LorcanaIngestor.extract_cards(payload)
    assert cards[0]["setCode"] == "10"


def test_normalize_lorcanajson_character() -> None:
    ingestor = LorcanaIngestor(None, None, None)
    raw = {
        "id": 1,
        "fullName": "Ariel - On Human Legs",
        "name": "Ariel",
        "version": "On Human Legs",
        "type": "Character",
        "setCode": "1",
        "number": 1,
        "rarity": "Uncommon",
        "cost": 4,
        "inkwell": True,
        "strength": 3,
        "willpower": 4,
        "lore": 2,
        "color": "Amber",
        "subtypes": ["Storyborn", "Hero"],
        "fullText": "VOICELESS This character can't quest.",
    }
    out = ingestor.normalize_raw_card(raw)
    assert out is not None
    assert out["id"] == "1"
    assert out["name"] == "Ariel - On Human Legs"
    assert out["subtitle"] == "On Human Legs"
    assert out["set_id"] == "1"
    assert out["collector_number"] == 1
    assert out["move_cost"] is None
    assert out["color_aspect"] == ["Amber"]
    assert out["card_type"] == "Character"


def test_normalize_lorcanajson_location_move_cost() -> None:
    ingestor = LorcanaIngestor(None, None, None)
    raw = {
        "id": 500,
        "fullName": "Never Land - Mermaid Lagoon",
        "name": "Never Land",
        "version": "Mermaid Lagoon",
        "type": "Location",
        "setCode": "3",
        "number": 22,
        "cost": 1,
        "moveCost": 2,
        "willpower": 8,
        "lore": 1,
        "color": "Sapphire",
        "fullText": "A location.",
    }
    out = ingestor.normalize_raw_card(raw)
    assert out is not None
    assert out["move_cost"] == 2
    assert out["card_type"] == "Location"


def test_normalize_lorcanajson_action_effects_fallback() -> None:
    ingestor = LorcanaIngestor(None, None, None)
    raw = {
        "id": 99,
        "fullName": "Brawl",
        "name": "Brawl",
        "type": "Action",
        "setCode": "1",
        "number": 200,
        "color": "Ruby",
        "effects": [{"fullText": "Deal 2 damage."}],
    }
    out = ingestor.normalize_raw_card(raw)
    assert out is not None
    assert "Deal 2 damage" in (out["text"] or "")
