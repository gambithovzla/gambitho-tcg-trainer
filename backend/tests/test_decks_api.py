from fastapi.testclient import TestClient

from src.api.main import app


client = TestClient(app)


def test_validate_deck_returns_issue_codes() -> None:
    payload = {
        "strict_catalog": False,
        "cards": [
            {"card_id": "a", "copies": 4, "colors": ["amethyst"]},
            {"card_id": "b", "copies": 4, "colors": ["ruby"]},
            {"card_id": "c", "copies": 4, "colors": ["sapphire"]},
        ],
    }
    response = client.post("/decks/validate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["is_legal"] is False
    assert any(issue["code"] == "DECK_SIZE_MISMATCH" for issue in body["issues"])
    assert any(issue["code"] == "TOO_MANY_COLORS" for issue in body["issues"])


def test_repair_deck_returns_structured_payload() -> None:
    payload = {
        "strict_catalog": False,
        "cards": [
            {"card_id": "a", "copies": 10, "colors": ["amethyst", "ruby", "sapphire"]},
        ],
    }
    response = client.post("/decks/repair", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert "repaired_cards" in body
    assert "notes" in body
    assert "validation" in body
    assert isinstance(body["validation"]["issues"], list)
