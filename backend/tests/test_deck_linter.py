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
