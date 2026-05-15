from src.domain.engine.actions import (
    ChallengeAction,
    DevelopInkAction,
    EndTurnAction,
    PlayCharacterAction,
    QuestAction,
)
from src.domain.engine.fsm import CharacterInPlay, GameEngineFSM


def _setup_p1_with_ready_character(engine: GameEngineFSM) -> None:
    engine.apply_action(DevelopInkAction(player_id=1))
    engine.apply_action(EndTurnAction(player_id=1))
    engine.apply_action(DevelopInkAction(player_id=2))
    engine.apply_action(EndTurnAction(player_id=2))
    engine.apply_action(DevelopInkAction(player_id=1))
    play = next(action for action in engine.get_legal_actions() if action.action_type == "play_character")
    engine.apply_action(play)
    engine.apply_action(EndTurnAction(player_id=1))
    engine.apply_action(EndTurnAction(player_id=2))


def test_quest_updates_state_and_resolves_bag() -> None:
    engine = GameEngineFSM(target_lore=2)
    _setup_p1_with_ready_character(engine)
    engine.apply_action(QuestAction(player_id=1, amount=1))

    assert engine.state.players[1].lore == 1
    assert any("Resolve trigger" in log for log in engine.state.action_log)


def test_end_turn_switches_active_player() -> None:
    engine = GameEngineFSM()

    engine.apply_action(EndTurnAction(player_id=1))

    assert engine.state.active_player_id == 2
    assert engine.state.players[2].hand_size == 8
    assert engine.state.players[2].deck_size == 52


def test_hidden_combo_potential_can_grant_bonus_lore() -> None:
    engine = GameEngineFSM()
    engine.state.players[1].hidden_combo_potential = 0.9
    _setup_p1_with_ready_character(engine)
    engine.apply_action(QuestAction(player_id=1, amount=1))

    assert engine.state.players[1].lore == 2


def test_end_turn_refreshes_next_player_ink_and_turn_flags() -> None:
    engine = GameEngineFSM()

    engine.apply_action(EndTurnAction(player_id=1))
    engine.apply_action(DevelopInkAction(player_id=2))
    engine.apply_action(EndTurnAction(player_id=2))

    p1 = engine.state.players[1]
    assert engine.state.active_player_id == 1
    assert p1.ink_played_this_turn is False
    assert p1.ink_available == p1.ink_total


def test_first_player_skips_first_draw_step() -> None:
    engine = GameEngineFSM()
    p1 = engine.state.players[1]
    assert p1.hand_size == 7
    assert p1.deck_size == 53
    assert any("skips draw" in line for line in engine.state.action_log)


def test_quest_requires_ready_character_and_removes_quest_action_after_use() -> None:
    engine = GameEngineFSM(target_lore=10)
    p1 = engine.state.players[1]

    engine.apply_action(DevelopInkAction(player_id=1))
    assert p1.ink_total == 1
    assert p1.ink_available == 1

    legal_action_types = {action.action_type for action in engine.get_legal_actions()}
    assert "quest" not in legal_action_types

    engine.apply_action(EndTurnAction(player_id=1))
    engine.apply_action(DevelopInkAction(player_id=2))
    engine.apply_action(EndTurnAction(player_id=2))
    engine.apply_action(DevelopInkAction(player_id=1))
    play = next(action for action in engine.get_legal_actions() if action.action_type == "play_character")
    engine.apply_action(play)
    engine.apply_action(EndTurnAction(player_id=1))
    engine.apply_action(EndTurnAction(player_id=2))
    engine.apply_action(QuestAction(player_id=1, amount=1))
    assert p1.lore == 1

    legal_action_types = {action.action_type for action in engine.get_legal_actions()}
    assert "quest" not in legal_action_types
    assert "end_turn" in legal_action_types


def test_challenge_banishes_opponent_exerted_character() -> None:
    engine = GameEngineFSM(target_lore=10)
    _setup_p1_with_ready_character(engine)
    engine.state.players[2].battlefield.append(
        CharacterInPlay(strength=2, willpower=2, exerted=True, summoning_sick=False)
    )
    GameEngineFSM._sync_board_counts(engine.state.players[2])

    legal_action_types = {action.action_type for action in engine.get_legal_actions()}
    assert "challenge" in legal_action_types

    engine.apply_action(ChallengeAction(player_id=1))

    p1 = engine.state.players[1]
    p2 = engine.state.players[2]
    assert p1.board_ready_characters == 0
    assert p1.board_exerted_characters in {0, 1}
    assert p2.board_exerted_characters == 0


def test_challenge_resolves_damage_exchange_and_can_banish_both() -> None:
    engine = GameEngineFSM(target_lore=10)
    _setup_p1_with_ready_character(engine)

    p1 = engine.state.players[1]
    p2 = engine.state.players[2]
    p1.battlefield = [CharacterInPlay(strength=3, willpower=2, exerted=False, summoning_sick=False)]
    p2.battlefield = [CharacterInPlay(strength=2, willpower=2, exerted=True, summoning_sick=False)]
    GameEngineFSM._sync_board_counts(p1)
    GameEngineFSM._sync_board_counts(p2)

    engine.apply_action(ChallengeAction(player_id=1))

    assert len(p1.battlefield) == 0
    assert len(p2.battlefield) == 0


def test_legal_actions_include_multiple_play_templates_with_enough_ink() -> None:
    engine = GameEngineFSM(target_lore=10)
    p1 = engine.state.players[1]
    p1.ink_available = 4
    p1.ink_total = 4
    p1.hand_size = 5

    play_actions = [action for action in engine.get_legal_actions() if action.action_type == "play_character"]
    archetypes = {getattr(action, "archetype", None) for action in play_actions}

    assert len(play_actions) >= 3
    assert {"tempo", "aggressive", "quester"}.issubset(archetypes)


def test_play_character_consumes_matching_hand_intent() -> None:
    engine = GameEngineFSM(target_lore=10)
    p1 = engine.state.players[1]
    p1.hand_intents = ["quester", "song"]
    p1.ink_total = 3
    p1.ink_available = 3
    engine._sync_hand_size(p1)

    legal = engine.get_legal_actions()
    play = next(action for action in legal if action.action_type == "play_character" and action.archetype == "quester")
    engine.apply_action(play)

    assert p1.hand_intents == ["song"]
    assert p1.board_fresh_characters == 1


def test_illegal_play_character_does_not_spend_ink_or_change_state() -> None:
    engine = GameEngineFSM(target_lore=10)
    p1 = engine.state.players[1]
    p1.hand_intents = ["tempo"]
    p1.ink_total = 3
    p1.ink_available = 3
    engine._sync_hand_size(p1)

    illegal = PlayCharacterAction(
        player_id=1,
        cost=1,
        strength=9,
        willpower=9,
        lore_value=9,
        archetype="tempo",
    )
    engine.apply_action(illegal)

    assert p1.ink_available == 3
    assert p1.hand_intents == ["tempo"]
    assert len(p1.battlefield) == 0
    assert any("illegal action" in line for line in engine.state.action_log)


def test_illegal_quest_amount_is_rejected() -> None:
    engine = GameEngineFSM(target_lore=10)
    _setup_p1_with_ready_character(engine)
    p1 = engine.state.players[1]

    engine.apply_action(QuestAction(player_id=1, amount=5))

    assert p1.lore == 0
    assert p1.board_ready_characters == 1
    assert any("illegal action" in line for line in engine.state.action_log)


def test_sing_song_requires_song_intent_and_consumes_it() -> None:
    engine = GameEngineFSM(target_lore=10)
    p1 = engine.state.players[1]
    p1.battlefield = [CharacterInPlay(strength=2, willpower=2, exerted=False, summoning_sick=False)]
    p1.ink_total = 2
    p1.ink_available = 2
    p1.hand_intents = ["song"]
    engine._sync_hand_size(p1)
    GameEngineFSM._sync_board_counts(p1)

    legal_types = {action.action_type for action in engine.get_legal_actions()}
    assert "sing_song" in legal_types

    sing = next(action for action in engine.get_legal_actions() if action.action_type == "sing_song")
    engine.apply_action(sing)

    assert p1.hand_intents == []
    assert p1.lore == 1


def test_intent_profile_biases_initial_hand_generation() -> None:
    engine = GameEngineFSM(
        target_lore=10,
        intent_weights_by_player={
            1: {"tempo": 0.0, "aggressive": 0.0, "quester": 0.0, "defender": 0.0, "song": 1.0},
            2: {"tempo": 1.0, "aggressive": 0.0, "quester": 0.0, "defender": 0.0, "song": 0.0},
        },
    )

    assert set(engine.state.players[1].hand_intents) == {"song"}
    assert set(engine.state.players[2].hand_intents) == {"tempo"}


def test_golden_opening_flow_develop_play_quest() -> None:
    engine = GameEngineFSM(target_lore=10)
    p1 = engine.state.players[1]
    p2 = engine.state.players[2]

    engine.apply_action(DevelopInkAction(player_id=1))
    engine.apply_action(EndTurnAction(player_id=1))
    engine.apply_action(DevelopInkAction(player_id=2))
    engine.apply_action(EndTurnAction(player_id=2))

    p1.hand_intents = ["defender", "tempo"]
    engine._sync_hand_size(p1)
    engine.apply_action(DevelopInkAction(player_id=1))
    play = next(
        action
        for action in engine.get_legal_actions()
        if action.action_type == "play_character" and action.archetype == "tempo"
    )
    engine.apply_action(play)
    engine.apply_action(EndTurnAction(player_id=1))
    engine.apply_action(EndTurnAction(player_id=2))

    quest = next(action for action in engine.get_legal_actions() if action.action_type == "quest")
    engine.apply_action(quest)

    assert engine.state.active_player_id == 1
    assert engine.state.turn_number == 5
    assert engine.state.total_turns_taken == 4
    assert p1.lore == 1
    assert p1.ink_total == 2
    assert p1.ink_available == 2
    assert p1.hand_size == 1
    assert p1.deck_size == 51
    assert p1.board_ready_characters == 0
    assert p1.board_exerted_characters == 1
    assert p1.board_fresh_characters == 0
    assert p2.hand_size == 8
    assert p2.deck_size == 51


def test_golden_challenge_flow_damage_persists_across_turns() -> None:
    engine = GameEngineFSM(target_lore=10)
    _setup_p1_with_ready_character(engine)
    p1 = engine.state.players[1]
    p2 = engine.state.players[2]

    p1.battlefield = [CharacterInPlay(strength=3, willpower=3, damage=0, exerted=False, summoning_sick=False)]
    p2.battlefield = [CharacterInPlay(strength=1, willpower=2, damage=0, exerted=True, summoning_sick=False)]
    GameEngineFSM._sync_board_counts(p1)
    GameEngineFSM._sync_board_counts(p2)

    engine.apply_action(ChallengeAction(player_id=1))

    assert len(p1.battlefield) == 1
    assert p1.battlefield[0].damage == 1
    assert p1.board_ready_characters == 0
    assert p1.board_exerted_characters == 1
    assert len(p2.battlefield) == 0
    assert p2.board_exerted_characters == 0

    engine.apply_action(EndTurnAction(player_id=1))
    engine.apply_action(EndTurnAction(player_id=2))

    assert engine.state.active_player_id == 1
    assert p1.battlefield[0].damage == 1
    assert p1.battlefield[0].exerted is False
    assert p1.battlefield[0].summoning_sick is False
    assert p1.board_ready_characters == 1
