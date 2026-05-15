from src.infra.ingestion.lorcana_ingestor import LorcanaIngestor


def test_normalize_lorcast_card_maps_fields() -> None:
    ingestor = LorcanaIngestor(
        card_repository=object(),
        graph_loader=object(),
        embed_indexer=object(),
    )
    raw = {
        "id": "crd_test",
        "name": "Elsa",
        "version": "Spirit of Winter",
        "cost": 8,
        "inkwell": False,
        "ink": "Amethyst",
        "type": ["Character"],
        "classifications": ["Floodborn", "Hero"],
        "text": "Shift 6",
        "strength": 4,
        "willpower": 6,
        "lore": 3,
        "move_cost": None,
        "rarity": "Enchanted",
        "collector_number": "207",
        "set": {"id": "set_x", "code": "1", "name": "The First Chapter"},
    }

    normalized = ingestor.normalize_raw_card(raw)

    assert normalized is not None
    assert normalized["id"] == "crd_test"
    assert normalized["name"] == "Elsa"
    assert normalized["subtitle"] == "Spirit of Winter"
    assert normalized["set_id"] == "1"
    assert normalized["collector_number"] == "207"
    assert normalized["color_aspect"] == ["Amethyst"]
    assert normalized["card_type"] == "Character"
    assert normalized["subtypes"] == ["Floodborn", "Hero"]
    assert normalized["inkwell_inkable"] is False
