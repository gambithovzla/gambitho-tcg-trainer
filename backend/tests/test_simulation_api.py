from fastapi.testclient import TestClient

from src.api.main import app


client = TestClient(app)


def test_decision_endpoint_golden_contract_snapshot() -> None:
    payload = {
        "target_lore": 8,
        "active_player_id": 1,
        "player_one_lore": 2,
        "player_two_lore": 3,
        "ismcts_iterations": 24,
        "active_player_intent_weights": {
            "tempo": 0.5,
            "aggressive": 0.2,
            "quester": 0.15,
            "defender": 0.1,
            "song": 0.05,
        },
        "opponent_intent_weights": {
            "tempo": 0.1,
            "aggressive": 0.1,
            "quester": 0.1,
            "defender": 0.5,
            "song": 0.2,
        },
    }
    response = client.post("/simulate/decision", json=payload)

    assert response.status_code == 200
    body = response.json()
    expected_keys = {
        "chosen_action_type",
        "chosen_player_id",
        "chosen_amount",
        "chosen_cost",
        "chosen_archetype",
        "total_iterations",
        "options",
        "resolved_active_player_intent_weights",
        "resolved_opponent_intent_weights",
        "resolved_weights_source",
        "strict_validation",
    }
    assert expected_keys.issubset(body.keys())
    assert body["chosen_action_type"] in {
        "challenge",
        "develop_ink",
        "play_character",
        "quest",
        "sing_song",
        "end_turn",
    }
    assert body["chosen_player_id"] == 1
    assert body["total_iterations"] == 24
    assert body["resolved_weights_source"] == "active:manual;opponent:manual"
    assert body["strict_validation"] == []

    for key in ("resolved_active_player_intent_weights", "resolved_opponent_intent_weights"):
        weights = body[key]
        assert set(weights.keys()) == {"tempo", "aggressive", "quester", "defender", "song"}
        assert abs(sum(weights.values()) - 1.0) < 1e-6

    assert isinstance(body["options"], list)
    assert len(body["options"]) >= 1
    option_keys = {"action_type", "player_id", "amount", "cost", "archetype", "visits", "reward_sum", "mean_value"}
    sum_visits = 0
    for opt in body["options"]:
        assert option_keys.issubset(opt.keys())
        assert isinstance(opt["visits"], int)
        assert opt["visits"] >= 0
        sum_visits += opt["visits"]
        if opt["visits"] > 0:
            assert abs(opt["mean_value"] - opt["reward_sum"] / opt["visits"]) < 1e-6
        else:
            assert opt["mean_value"] == 0.0
    if body["total_iterations"] > 0:
        assert sum_visits == body["total_iterations"]
    else:
        assert sum_visits == 0


def test_decision_endpoint_golden_contract_snapshot_strict_resolution() -> None:
    payload = {
        "target_lore": 8,
        "active_player_id": 1,
        "player_one_lore": 2,
        "player_two_lore": 3,
        "ismcts_iterations": 12,
        "strict_intent_resolution": True,
        "active_player_intent_weights": {
            "tempo": 0.2,
            "aggressive": 0.2,
            "quester": 0.2,
            "defender": 0.2,
            "song": 0.2,
        },
        "opponent_intent_weights": {
            "tempo": 0.2,
            "aggressive": 0.2,
            "quester": 0.2,
            "defender": 0.2,
            "song": 0.2,
        },
    }
    response = client.post("/simulate/decision", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["total_iterations"] == 12
    assert body["resolved_weights_source"] == "active:manual;opponent:manual"
    assert body["strict_validation"] == []


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
    assert body["chosen_action_type"] in {
        "challenge",
        "develop_ink",
        "play_character",
        "quest",
        "sing_song",
        "end_turn",
    }
    assert body["chosen_player_id"] == 1
    assert body["total_iterations"] == 24
    assert isinstance(body["options"], list)
    assert len(body["options"]) >= 1
    assert "chosen_cost" in body
    assert "chosen_archetype" in body
    assert "resolved_active_player_intent_weights" in body
    assert "resolved_opponent_intent_weights" in body
    assert "resolved_weights_source" in body
    assert body["strict_validation"] == []


def test_decision_endpoint_accepts_hidden_information_constraints() -> None:
    payload = {
        "target_lore": 8,
        "active_player_id": 1,
        "player_one_lore": 2,
        "player_two_lore": 3,
        "ismcts_iterations": 16,
        "observed_opponent_profile": "control",
        "observed_avg_cost": 4.6,
        "observed_turns": 6,
        "min_opponent_hand_size": 5,
        "max_opponent_hand_size": 6,
        "min_opponent_combo_potential": 0.2,
        "max_opponent_combo_potential": 0.4,
    }
    response = client.post("/simulate/decision", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["total_iterations"] == 16
    assert len(body["options"]) >= 1
    assert isinstance(body["resolved_active_player_intent_weights"], dict)
    assert isinstance(body["resolved_opponent_intent_weights"], dict)


def test_decision_endpoint_accepts_intent_weight_profiles() -> None:
    payload = {
        "target_lore": 8,
        "active_player_id": 1,
        "player_one_lore": 1,
        "player_two_lore": 2,
        "ismcts_iterations": 12,
        "active_player_intent_weights": {
            "tempo": 0.6,
            "aggressive": 0.2,
            "quester": 0.1,
            "defender": 0.1,
            "song": 0.0,
        },
        "opponent_intent_weights": {
            "tempo": 0.0,
            "aggressive": 0.0,
            "quester": 0.0,
            "defender": 0.0,
            "song": 1.0,
        },
    }
    response = client.post("/simulate/decision", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["total_iterations"] == 12
    assert body["resolved_weights_source"].startswith("active:")


def test_match_endpoint_accepts_deck_for_intent_inference() -> None:
    payload = {
        "max_turns": 6,
        "target_lore": 6,
        "strategy": "heuristic",
        "player_one_deck": [
            {"card_id": "song_1", "copies": 4, "card_type": "Song", "subtypes": ["Song"]},
            {"card_id": "song_2", "copies": 4, "card_type": "Song", "subtypes": ["Song"]},
            {"card_id": "char_1", "copies": 4, "card_type": "Character", "cost": 2, "strength": 2, "willpower": 2, "lore": 1},
        ],
        "player_two_deck": [
            {"card_id": "char_a", "copies": 4, "card_type": "Character", "cost": 4, "strength": 2, "willpower": 4, "lore": 1},
            {"card_id": "char_b", "copies": 4, "card_type": "Character", "cost": 3, "strength": 3, "willpower": 2, "lore": 1},
        ],
    }
    response = client.post("/simulate/match", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert "turns_played" in body
    assert isinstance(body["history"], list)
    assert "resolved_player_one_intent_weights" in body
    assert "resolved_player_two_intent_weights" in body
    assert body["resolved_weights_source"].startswith("p1:")


def test_match_endpoint_golden_contract_snapshot() -> None:
    payload = {
        "max_turns": 6,
        "target_lore": 6,
        "strategy": "heuristic",
        "player_one_intent_weights": {
            "tempo": 0.0,
            "aggressive": 0.0,
            "quester": 1.0,
            "defender": 0.0,
            "song": 0.0,
        },
        "player_two_intent_weights": {
            "tempo": 0.0,
            "aggressive": 0.0,
            "quester": 0.0,
            "defender": 1.0,
            "song": 0.0,
        },
        "opponent_intent_weights": {
            "tempo": 0.0,
            "aggressive": 0.0,
            "quester": 0.0,
            "defender": 1.0,
            "song": 0.0,
        },
    }
    response = client.post("/simulate/match", json=payload)

    assert response.status_code == 200
    body = response.json()
    expected_keys = {
        "winner_player_id",
        "turns_played",
        "history",
        "resolved_player_one_intent_weights",
        "resolved_player_two_intent_weights",
        "resolved_weights_source",
        "strict_validation",
    }
    assert expected_keys.issubset(body.keys())
    assert body["winner_player_id"] in {None, 1, 2}
    assert isinstance(body["turns_played"], int)
    assert 1 <= body["turns_played"] <= payload["max_turns"] + 1
    assert isinstance(body["history"], list)
    assert len(body["history"]) > 0
    assert any("wins by lore" in line for line in body["history"]) or body["turns_played"] == payload["max_turns"] + 1
    assert body["resolved_weights_source"] == "p1:manual;p2:manual;opp:manual"
    assert body["strict_validation"] == []

    for key in ("resolved_player_one_intent_weights", "resolved_player_two_intent_weights"):
        weights = body[key]
        assert set(weights.keys()) == {"tempo", "aggressive", "quester", "defender", "song"}
        assert abs(sum(weights.values()) - 1.0) < 1e-6

    # Golden expectations for this deterministic profile matchup.
    assert body["resolved_player_one_intent_weights"]["quester"] == 1.0
    assert body["resolved_player_two_intent_weights"]["defender"] == 1.0


def test_match_endpoint_turns_played_when_budget_exhausted_without_winner() -> None:
    """Contract: turns_played == max_turns + 1 when lore target is not reached before the loop stops."""
    payload = {
        "max_turns": 3,
        "target_lore": 40,
        "strategy": "heuristic",
    }
    response = client.post("/simulate/match", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["winner_player_id"] is None
    assert body["turns_played"] == payload["max_turns"] + 1


def test_intent_profile_endpoint_returns_weights_and_metadata() -> None:
    payload = {
        "deck": [
            {"card_id": "song_1", "copies": 4, "card_type": "Song", "subtypes": ["Song"]},
            {"card_id": "char_1", "copies": 4, "card_type": "Character", "cost": 3, "strength": 3, "willpower": 2, "lore": 1},
        ]
    }
    response = client.post("/simulate/intent-profile", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["cards_seen"] == 2
    assert "weights" in body
    assert "song" in body["weights"]
    assert body["source"] in {"input_only", "catalog+input", "none"}
    assert body["strict_validation"] == []


def test_intent_profile_endpoint_strict_golden_contract_snapshot() -> None:
    payload = {
        "strict": True,
        "deck": [
            {"card_id": "song_hint", "copies": 4, "card_type": "Song", "subtypes": ["Song"]},
            {
                "card_id": "char_hint",
                "copies": 4,
                "card_type": "Character",
                "cost": 3,
                "strength": 2,
                "willpower": 3,
                "lore": 1,
            },
        ],
    }
    response = client.post("/simulate/intent-profile", json=payload)

    assert response.status_code == 200
    body = response.json()
    expected_keys = {
        "weights",
        "cards_seen",
        "cards_matched_catalog",
        "source",
        "strict_validation",
    }
    assert expected_keys.issubset(body.keys())
    assert body["cards_seen"] == 2
    assert body["cards_matched_catalog"] >= 0
    assert body["source"] in {"input_only", "catalog+input", "none"}

    weights = body["weights"]
    assert set(weights.keys()) == {"tempo", "aggressive", "quester", "defender", "song"}
    assert abs(sum(weights.values()) - 1.0) < 1e-6
    assert all(value >= 0.0 for value in weights.values())

    assert isinstance(body["strict_validation"], list)
    assert len(body["strict_validation"]) == 1
    entry = body["strict_validation"][0]
    assert set(entry.keys()) == {
        "actor",
        "hinted_cards",
        "matched_catalog_cards",
        "total_cards",
        "source",
    }
    assert entry["actor"] == "intent_profile"
    assert entry["hinted_cards"] == 2
    assert entry["total_cards"] == 2
    assert entry["matched_catalog_cards"] >= 0
    assert entry["source"] in {"input_only", "catalog+input", "none"}


def test_intent_profile_endpoint_strict_rejects_weak_hints() -> None:
    payload = {
        "strict": True,
        "deck": [
            {"card_id": "no_hint_a", "copies": 4},
            {"card_id": "no_hint_b", "copies": 4},
        ],
    }
    response = client.post("/simulate/intent-profile", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["contract_version"] == "1"
    assert detail["error_code"] == "STRICT_INTENT_HINTS_INSUFFICIENT"
    assert "usable hints" in detail["message"]
    assert detail["context"]["actor"] == "intent_profile"


def test_intent_profile_endpoint_strict_accepts_structural_hints() -> None:
    payload = {
        "strict": True,
        "deck": [
            {"card_id": "song_hint", "copies": 4, "card_type": "Song", "subtypes": ["Song"]},
            {
                "card_id": "char_hint",
                "copies": 4,
                "card_type": "Character",
                "cost": 3,
                "strength": 2,
                "willpower": 3,
                "lore": 1,
            },
        ],
    }
    response = client.post("/simulate/intent-profile", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["cards_seen"] == 2
    assert len(body["strict_validation"]) == 1
    entry = body["strict_validation"][0]
    assert entry["actor"] == "intent_profile"
    assert entry["hinted_cards"] == 2
    assert entry["total_cards"] == 2
    assert entry["matched_catalog_cards"] >= 0
    assert entry["source"] in {"input_only", "catalog+input", "none"}


def test_intent_preset_endpoints_roundtrip(tmp_path, monkeypatch) -> None:
    presets_path = tmp_path / "intent-presets.json"
    monkeypatch.setenv("INTENT_PRESETS_PATH", str(presets_path))

    upsert_payload = {
        "name": "aggro_song",
        "weights": {
            "tempo": 0.1,
            "aggressive": 0.5,
            "quester": 0.1,
            "defender": 0.1,
            "song": 0.2,
        },
        "tags": ["ladder", "aggro"],
    }
    put_response = client.post("/simulate/intent-presets", json=upsert_payload)
    assert put_response.status_code == 200
    put_body = put_response.json()
    assert put_body["name"] == "aggro_song"
    assert abs(sum(put_body["weights"].values()) - 1.0) < 1e-6
    assert put_body["updated_at"] is not None
    assert put_body["created_at"] is not None
    assert put_body["version"] == 1
    assert put_body["history_length"] == 1
    assert set(put_body["tags"]) == {"ladder", "aggro"}

    get_response = client.get("/simulate/intent-presets/aggro_song")
    assert get_response.status_code == 200
    get_body = get_response.json()
    assert get_body["name"] == "aggro_song"
    assert get_body["weights"]["aggressive"] > get_body["weights"]["tempo"]
    assert get_body["updated_at"] is not None
    assert get_body["created_at"] is not None
    assert get_body["version"] == 1
    assert get_body["history_length"] == 1
    assert set(get_body["tags"]) == {"ladder", "aggro"}

    second_upsert = client.post("/simulate/intent-presets", json=upsert_payload)
    assert second_upsert.status_code == 200
    second_body = second_upsert.json()
    assert second_body["version"] == 2
    assert second_body["created_at"] == put_body["created_at"]
    assert second_body["history_length"] == 2

    patch_response = client.patch(
        "/simulate/intent-presets/aggro_song",
        json={"weights": {"song": 0.5, "aggressive": 0.3}, "tags": ["ladder", "bo1"]},
    )
    assert patch_response.status_code == 200
    patch_body = patch_response.json()
    assert patch_body["version"] == 3
    assert patch_body["history_length"] == 3
    assert patch_body["weights"]["song"] > patch_body["weights"]["tempo"]
    assert set(patch_body["tags"]) == {"ladder", "bo1"}

    history_response = client.get("/simulate/intent-presets/aggro_song/history")
    assert history_response.status_code == 200
    history_body = history_response.json()
    assert history_body["name"] == "aggro_song"
    assert len(history_body["history"]) == 3
    assert history_body["history"][-1]["version"] == 3

    list_response = client.get("/simulate/intent-presets")
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["total"] >= 1
    assert list_body["returned"] >= 1
    assert "next_offset" in list_body
    assert "prev_offset" in list_body
    assert "has_more" in list_body
    assert list_body["prev_offset"] is None
    assert any(preset["name"] == "aggro_song" for preset in list_body["presets"])
    listed = next(preset for preset in list_body["presets"] if preset["name"] == "aggro_song")
    assert listed["history_preview"] == []

    list_with_history = client.get("/simulate/intent-presets?include_history=true&history_limit=2")
    assert list_with_history.status_code == 200
    with_history_body = list_with_history.json()
    listed_with_history = next(
        preset for preset in with_history_body["presets"] if preset["name"] == "aggro_song"
    )
    assert len(listed_with_history["history_preview"]) == 2
    assert listed_with_history["history_preview"][-1]["version"] == 3

    list_filtered = client.get("/simulate/intent-presets?q=bo1")
    assert list_filtered.status_code == 200
    filtered_body = list_filtered.json()
    assert len(filtered_body["presets"]) == 1
    assert filtered_body["presets"][0]["name"] == "aggro_song"

    delete_response = client.delete("/simulate/intent-presets/aggro_song")
    assert delete_response.status_code == 200
    delete_body = delete_response.json()
    assert delete_body["name"] == "aggro_song"
    assert delete_body["deleted"] is True

    missing_delete = client.delete("/simulate/intent-presets/aggro_song")
    assert missing_delete.status_code == 200
    assert missing_delete.json()["deleted"] is False

    missing_patch = client.patch("/simulate/intent-presets/does_not_exist", json={"weights": {"song": 1.0}})
    assert missing_patch.status_code == 200
    assert missing_patch.json()["weights"] == {}


def test_decision_endpoint_resolves_weights_from_preset(tmp_path, monkeypatch) -> None:
    presets_path = tmp_path / "intent-presets.json"
    monkeypatch.setenv("INTENT_PRESETS_PATH", str(presets_path))
    preset_payload = {
        "name": "control_wall",
        "weights": {
            "tempo": 0.1,
            "aggressive": 0.05,
            "quester": 0.15,
            "defender": 0.65,
            "song": 0.05,
        },
    }
    upsert = client.post("/simulate/intent-presets", json=preset_payload)
    assert upsert.status_code == 200

    payload = {
        "target_lore": 8,
        "active_player_id": 1,
        "player_one_lore": 2,
        "player_two_lore": 3,
        "ismcts_iterations": 10,
        "opponent_intent_preset": "control_wall",
    }
    response = client.post("/simulate/decision", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "opponent:preset:control_wall" in body["resolved_weights_source"]
    assert body["resolved_opponent_intent_weights"]["defender"] > 0.5


def test_intent_preset_list_supports_sort_and_pagination(tmp_path, monkeypatch) -> None:
    presets_path = tmp_path / "intent-presets.json"
    monkeypatch.setenv("INTENT_PRESETS_PATH", str(presets_path))

    presets = [
        ("preset_a", {"tempo": 0.8, "aggressive": 0.1, "quester": 0.05, "defender": 0.05, "song": 0.0}),
        ("preset_b", {"tempo": 0.1, "aggressive": 0.8, "quester": 0.05, "defender": 0.05, "song": 0.0}),
        ("preset_c", {"tempo": 0.1, "aggressive": 0.1, "quester": 0.1, "defender": 0.1, "song": 0.6}),
    ]
    for name, weights in presets:
        response = client.post("/simulate/intent-presets", json={"name": name, "weights": weights})
        assert response.status_code == 200

    by_name_desc = client.get("/simulate/intent-presets?sort_by=name&order=desc&limit=2")
    assert by_name_desc.status_code == 200
    body = by_name_desc.json()
    assert body["total"] == 3
    assert body["returned"] == 2
    assert body["has_more"] is True
    assert body["next_offset"] == 2
    assert body["prev_offset"] is None
    assert [preset["name"] for preset in body["presets"]] == ["preset_c", "preset_b"]

    by_name_offset = client.get("/simulate/intent-presets?sort_by=name&order=asc&offset=1&limit=2")
    assert by_name_offset.status_code == 200
    body_offset = by_name_offset.json()
    assert body_offset["total"] == 3
    assert body_offset["returned"] == 2
    assert body_offset["has_more"] is False
    assert body_offset["next_offset"] is None
    assert body_offset["prev_offset"] == 0
    assert [preset["name"] for preset in body_offset["presets"]] == ["preset_b", "preset_c"]


def test_decision_endpoint_strict_intent_resolution_rejects_missing_preset() -> None:
    payload = {
        "target_lore": 8,
        "active_player_id": 1,
        "player_one_lore": 2,
        "player_two_lore": 3,
        "ismcts_iterations": 10,
        "opponent_intent_preset": "missing_preset",
        "strict_intent_resolution": True,
    }
    response = client.post("/simulate/decision", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["contract_version"] == "1"
    assert detail["error_code"] == "STRICT_INTENT_PRESET_MISSING"
    assert "missing_preset" in detail["message"]
    assert "missing_preset" in detail["context"]["missing_presets"]


def test_match_endpoint_strict_intent_resolution_rejects_implicit_defaults() -> None:
    payload = {
        "max_turns": 4,
        "target_lore": 6,
        "strategy": "heuristic",
        "strict_intent_resolution": True,
    }
    response = client.post("/simulate/match", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["contract_version"] == "1"
    assert detail["error_code"] == "STRICT_INTENT_INPUT_REQUIRED"
    assert detail["context"]["actor"] == "p1"


def test_decision_endpoint_strict_intent_resolution_rejects_implicit_defaults() -> None:
    payload = {
        "target_lore": 8,
        "active_player_id": 1,
        "player_one_lore": 2,
        "player_two_lore": 3,
        "ismcts_iterations": 8,
        "strict_intent_resolution": True,
    }
    response = client.post("/simulate/decision", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["contract_version"] == "1"
    assert detail["error_code"] == "STRICT_INTENT_INPUT_REQUIRED"
    assert detail["context"]["actor"] == "active_player"


def test_match_endpoint_strict_intent_resolution_rejects_missing_preset() -> None:
    payload = {
        "max_turns": 6,
        "target_lore": 6,
        "strategy": "heuristic",
        "player_one_intent_preset": "missing_1",
        "strict_intent_resolution": True,
    }
    response = client.post("/simulate/match", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["contract_version"] == "1"
    assert detail["error_code"] == "STRICT_INTENT_PRESET_MISSING"
    assert "missing_1" in detail["message"]
    assert "missing_1" in detail["context"]["missing_presets"]


def test_decision_endpoint_strict_intent_resolution_rejects_weak_deck_hints() -> None:
    payload = {
        "target_lore": 8,
        "active_player_id": 1,
        "player_one_lore": 2,
        "player_two_lore": 3,
        "ismcts_iterations": 10,
        "strict_intent_resolution": True,
        "opponent_intent_weights": {
            "tempo": 0.2,
            "aggressive": 0.2,
            "quester": 0.2,
            "defender": 0.2,
            "song": 0.2,
        },
        "active_player_deck": [
            {"card_id": "non_catalog_a", "copies": 4},
            {"card_id": "non_catalog_b", "copies": 4},
        ],
    }
    response = client.post("/simulate/decision", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["contract_version"] == "1"
    assert detail["error_code"] == "STRICT_INTENT_HINTS_INSUFFICIENT"
    assert "usable hints" in detail["message"]
    assert detail["context"]["actor"] == "active_player"


def test_intent_profile_endpoint_strict_rejects_missing_input() -> None:
    payload = {"strict": True, "deck": []}
    response = client.post("/simulate/intent-profile", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["contract_version"] == "1"
    assert detail["error_code"] == "STRICT_INTENT_INPUT_REQUIRED"
    assert detail["context"]["actor"] == "intent_profile"


def test_match_endpoint_strict_intent_resolution_accepts_deck_hints() -> None:
    payload = {
        "max_turns": 4,
        "target_lore": 6,
        "strategy": "heuristic",
        "strict_intent_resolution": True,
        "player_one_deck": [
            {
                "card_id": "non_catalog_song",
                "copies": 4,
                "card_type": "Song",
                "subtypes": ["Song"],
            },
            {
                "card_id": "non_catalog_char",
                "copies": 4,
                "card_type": "Character",
                "cost": 3,
                "strength": 2,
                "willpower": 3,
                "lore": 1,
            },
        ],
        "player_two_intent_weights": {
            "tempo": 0.2,
            "aggressive": 0.2,
            "quester": 0.2,
            "defender": 0.2,
            "song": 0.2,
        },
    }
    response = client.post("/simulate/match", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["strict_validation"], list)
    assert len(body["strict_validation"]) >= 1
    first = body["strict_validation"][0]
    assert first["hinted_cards"] >= 1
    assert first["total_cards"] >= 1
    assert first["matched_catalog_cards"] >= 0
    assert first["source"] in {"input_only", "catalog+input", "none"}


def test_decision_endpoint_strict_intent_resolution_accepts_deck_hints() -> None:
    payload = {
        "target_lore": 8,
        "active_player_id": 1,
        "player_one_lore": 2,
        "player_two_lore": 3,
        "ismcts_iterations": 10,
        "strict_intent_resolution": True,
        "active_player_deck": [
            {"card_id": "active_song", "copies": 4, "card_type": "Song", "subtypes": ["Song"]},
            {
                "card_id": "active_char",
                "copies": 4,
                "card_type": "Character",
                "cost": 2,
                "strength": 2,
                "willpower": 2,
                "lore": 1,
            },
        ],
        "opponent_intent_weights": {
            "tempo": 0.2,
            "aggressive": 0.2,
            "quester": 0.2,
            "defender": 0.2,
            "song": 0.2,
        },
    }
    response = client.post("/simulate/decision", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert len(body["strict_validation"]) == 1
    entry = body["strict_validation"][0]
    assert entry["actor"] == "active_player"
    assert entry["hinted_cards"] == 2
    assert entry["total_cards"] == 2
    assert entry["matched_catalog_cards"] >= 0
