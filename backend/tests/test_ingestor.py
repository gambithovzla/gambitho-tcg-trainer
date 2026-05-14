from src.infra.ingestion.lorcana_ingestor import LorcanaIngestor


class FakeCardRepository:
    def __init__(self) -> None:
        self.records = []
        self.schema_initialized = False

    def ensure_schema(self) -> None:
        self.schema_initialized = True

    def upsert_cards(self, cards):
        self.records.extend(cards)
        return len(cards)


class FakeGraphLoader:
    def load(self, cards):
        return len(cards)


class FakeEmbedIndexer:
    def index(self, cards):
        return len(cards)


def test_ingestor_loads_valid_cards_and_rejects_invalid() -> None:
    ingestor = LorcanaIngestor(
        card_repository=FakeCardRepository(),
        graph_loader=FakeGraphLoader(),
        embed_indexer=FakeEmbedIndexer(),
    )

    payload = [
        {"id": "A1", "name": "Card A", "cost": 2, "colors": ["amethyst"]},
        {"id": "B2", "name": "Card B", "cost": "3", "color": "ruby"},
        {"id": "", "name": "Invalid"},
    ]

    result = ingestor.ingest_from_payload(payload)

    assert result.cards_seen == 3
    assert result.cards_loaded_sql == 2
    assert result.cards_loaded_graph == 2
    assert result.cards_loaded_vector == 2
    assert result.cards_rejected == 1
