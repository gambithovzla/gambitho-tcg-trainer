from fastapi.testclient import TestClient

from src.api.main import app


client = TestClient(app)


def test_decision_endpoint_returns_structured_report() -> None:
    payload = {
        "target_lore": 8,
        "active_player_id": 1,
        "player_one_lore": 2,
        "player_two_lore": 3,
        "ismcts_iterations": 24,
        "observed_opponent_profile": "aggro",
        "observed_avg_cost": 2.1,
        "observed_turns": 3,
    }
    response = client.post("/simulate/decision", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["chosen_action_type"] in {"gain_lore", "end_turn"}
    assert body["chosen_player_id"] == 1
    assert body["total_iterations"] == 24
    assert isinstance(body["options"], list)
    assert len(body["options"]) >= 1
