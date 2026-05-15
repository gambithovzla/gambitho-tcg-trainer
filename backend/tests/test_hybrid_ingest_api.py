from fastapi.testclient import TestClient

from src.api.main import app
from src.infra.ingestion.lorcana_ingestor import LorcanaIngestor


client = TestClient(app)


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


def test_hybrid_ingest_merges_sources_with_precedence(monkeypatch) -> None:
    def fake_fetch_hybrid_raw_cards(**kwargs):
        return type(
            "HybridFetchResult",
            (),
            {
                "raw_cards_by_source": {
                    "lorcanajson": [
                        {"id": 1, "fullName": "Ariel - On Human Legs", "type": "Character", "setCode": "1", "number": 1}
                    ],
                    "lorcast": [
                        {
                            "id": "crd_override",
                            "name": "Ariel - On Human Legs",
                            "type": ["Character"],
                            "set": {"code": "1"},
                            "collector_number": "1",
                            "strength": 3,
                        }
                    ],
                },
                "cards_seen_by_source": {"lorcanajson": 1, "lorcast": 1},
            },
        )()

    monkeypatch.setattr("src.api.routes.ingestion.fetch_hybrid_raw_cards", fake_fetch_hybrid_raw_cards)

    def fake_build_ingestor() -> LorcanaIngestor:
        return LorcanaIngestor(
            card_repository=FakeCardRepository(),
            graph_loader=FakeGraphLoader(),
            embed_indexer=FakeEmbedIndexer(),
        )

    monkeypatch.setattr("src.api.routes.ingestion._build_ingestor", fake_build_ingestor)

    response = client.post(
        "/ingest/lorcana/hybrid",
        json={
            "include_lorcanajson": True,
            "include_lorcast": True,
            "source_precedence": ["lorcast", "lorcanajson"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["cards_seen"] == 2
    assert body["cards_seen_by_source"] == {"lorcanajson": 1, "lorcast": 1}
    assert body["merged_cards_seen"] == 1
    assert body["cards_rejected"] == 0
