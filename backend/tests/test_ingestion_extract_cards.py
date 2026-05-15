from src.infra.ingestion.lorcana_ingestor import LorcanaIngestor


def test_extract_cards_from_list_payload() -> None:
    payload = [{"id": "a"}, {"id": "b"}]
    cards = LorcanaIngestor.extract_cards(payload)
    assert len(cards) == 2


def test_extract_cards_from_cards_key() -> None:
    payload = {"cards": [{"id": "a"}, {"id": "b"}]}
    cards = LorcanaIngestor.extract_cards(payload)
    assert len(cards) == 2


def test_extract_cards_from_data_key() -> None:
    payload = {"data": [{"id": "a"}]}
    cards = LorcanaIngestor.extract_cards(payload)
    assert len(cards) == 1


def test_extract_cards_from_lorcast_results() -> None:
    payload = {"results": [{"id": "crd_1", "name": "X"}, {"id": "crd_2", "name": "Y"}]}
    cards = LorcanaIngestor.extract_cards(payload)
    assert len(cards) == 2


def test_extract_cards_single_card_object() -> None:
    payload = {"id": "crd_1", "name": "Solo", "ink": "Ruby", "type": ["Item"]}
    cards = LorcanaIngestor.extract_cards(payload)
    assert len(cards) == 1


def test_extract_cards_returns_empty_on_unknown_shape() -> None:
    payload = {"unexpected": {"id": "x"}}
    cards = LorcanaIngestor.extract_cards(payload)
    assert cards == []
