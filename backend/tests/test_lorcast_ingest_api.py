from fastapi.testclient import TestClient

from src.api.main import app


client = TestClient(app)


def test_lorcast_ingest_uses_fetch_and_ingests(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_fetch(*, query: str, unique: str, timeout: float = 60.0) -> dict:
        captured["query"] = query
        captured["unique"] = unique
        return {
            "results": [
                {
                    "id": "crd_abc",
                    "name": "Test Card",
                    "version": "v1",
                    "cost": 1,
                    "inkwell": True,
                    "ink": "Ruby",
                    "type": ["Character"],
                    "classifications": ["Hero"],
                    "text": "Do something",
                    "strength": 1,
                    "willpower": 2,
                    "lore": 1,
                    "rarity": "Common",
                    "collector_number": "1",
                    "set": {"code": "9", "id": "set_9", "name": "Test"},
                }
            ]
        }

    monkeypatch.setattr("src.api.routes.ingestion.fetch_card_search", fake_fetch)

    from src.infra.ingestion.lorcana_ingestor import LorcanaIngestor

    class FakeCardRepository:
        def ensure_schema(self) -> None:
            return None

        def upsert_cards(self, cards):
            return len(cards)

    class FakeGraphLoader:
        def load(self, cards):
            return len(cards)

    class FakeEmbedIndexer:
        def index(self, cards):
            return len(cards)

    def fake_build_ingestor() -> LorcanaIngestor:
        return LorcanaIngestor(
            card_repository=FakeCardRepository(),
            graph_loader=FakeGraphLoader(),
            embed_indexer=FakeEmbedIndexer(),
        )

    monkeypatch.setattr("src.api.routes.ingestion._build_ingestor", fake_build_ingestor)

    response = client.post("/ingest/lorcana/lorcast", json={"q": "set:9", "unique": "prints"})

    assert response.status_code == 200
    body = response.json()
    assert body["cards_seen"] == 1
    assert body["cards_rejected"] == 0
    assert captured["query"] == "set:9"
    assert captured["unique"] == "prints"
