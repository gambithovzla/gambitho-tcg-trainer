from fastapi.testclient import TestClient

from src.api.main import app
from src.infra.db.postgres.card_repository import CatalogCard

client = TestClient(app)


def test_list_catalog_cards(monkeypatch) -> None:
    sample = CatalogCard(
        id="1",
        name="Ariel - On Human Legs",
        subtitle="On Human Legs",
        set_id="1",
        collector_number="1",
        rarity="Uncommon",
        card_type="Character",
        cost=4,
        strength=3,
        willpower=4,
        lore=2,
        move_cost=None,
        inkwell_inkable=True,
        color_aspect=["Amber"],
        subtypes=["Storyborn"],
        rules_text="VOICELESS",
        image_url="https://api.lorcana.ravensburger.com/images/en/set1/1_full.jpg",
        image_thumbnail_url="https://api.lorcana.ravensburger.com/images/en/set1/1_thumb.jpg",
    )

    class FakeRepository:
        def list_catalog_cards(self, *, search: str | None = None, limit: int = 48, offset: int = 0):
            return [sample], 1

    monkeypatch.setattr("src.api.routes.catalog.PostgresCardRepository", FakeRepository)

    response = client.get("/catalog/cards?search=ariel")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["cards"][0]["image_url"].endswith("1_full.jpg")
    assert body["cards"][0]["name"] == "Ariel - On Human Legs"
