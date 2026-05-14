from dataclasses import dataclass, field


@dataclass
class DeckValidationResult:
    is_legal: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_cards: int = 0


class LorcanaDeckLinter:
    """Deterministic baseline linter for Lorcana deck legality."""

    DECK_SIZE = 60
    MAX_COPIES_PER_CARD = 4
    MAX_COLORS = 2

    def validate(self, deck: list[tuple[str, int, list[str]]]) -> DeckValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        total_cards = sum(copies for _, copies, _ in deck)

        if total_cards != self.DECK_SIZE:
            errors.append(f"Deck must contain exactly {self.DECK_SIZE} cards. Got {total_cards}.")

        unique_colors: set[str] = set()
        for card_id, copies, colors in deck:
            if copies > self.MAX_COPIES_PER_CARD:
                errors.append(
                    f"Card '{card_id}' exceeds max copies ({self.MAX_COPIES_PER_CARD}). Got {copies}."
                )
            unique_colors.update(colors)

        if len(unique_colors) > self.MAX_COLORS:
            errors.append(
                f"Deck uses too many colors. Max {self.MAX_COLORS}, got {len(unique_colors)}."
            )

        if not deck:
            warnings.append("Deck is empty.")

        return DeckValidationResult(
            is_legal=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            total_cards=total_cards,
        )
