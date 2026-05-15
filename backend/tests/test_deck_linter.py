from src.domain.linter.lorcana_linter import LorcanaDeckLinter


def test_linter_accepts_valid_60_card_two_color_deck() -> None:
    linter = LorcanaDeckLinter()
    deck = []
    for idx in range(15):
        deck.append((f"card_{idx}_a", 2, ["amethyst"]))
        deck.append((f"card_{idx}_b", 2, ["ruby"]))

    result = linter.validate(deck)
    assert result.is_legal is True
    assert result.total_cards == 60
    assert result.errors == []


def test_linter_rejects_wrong_size_and_too_many_colors() -> None:
    linter = LorcanaDeckLinter()
    deck = [
        ("a", 4, ["amethyst"]),
        ("b", 4, ["ruby"]),
        ("c", 4, ["sapphire"]),
    ]
    result = linter.validate(deck)

    assert result.is_legal is False
    assert any("exactly 60 cards" in err for err in result.errors)
    assert any("too many colors" in err for err in result.errors)


def test_linter_rejects_cards_missing_from_catalog() -> None:
    linter = LorcanaDeckLinter()
    deck = []
    for idx in range(15):
        deck.append((f"card_{idx}_a", 2, ["amethyst"]))
        deck.append((f"card_{idx}_b", 2, ["ruby"]))

    catalog = {f"card_{idx}_a" for idx in range(15)}
    catalog.update({f"card_{idx}_b" for idx in range(14)})
    result = linter.validate(deck, existing_card_ids=catalog)

    assert result.is_legal is False
    assert any("is not present in the ingested catalog" in err for err in result.errors)
    assert any(issue.code == "CARD_NOT_IN_CATALOG" for issue in result.issues)


def test_repair_caps_overcopies_and_fixes_size() -> None:
    linter = LorcanaDeckLinter()
    deck = [("card_a", 10, ["amethyst"]), ("card_b", 10, ["ruby"])]

    repaired = linter.repair(deck)
    total = sum(copies for _, copies, _ in repaired.repaired_deck)

    assert total == 8
    assert any("Capped copies" in note for note in repaired.notes)
