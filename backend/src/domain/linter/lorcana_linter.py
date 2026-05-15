from dataclasses import dataclass, field


@dataclass
class DeckValidationResult:
    is_legal: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_cards: int = 0
    issues: list["DeckIssue"] = field(default_factory=list)


@dataclass(frozen=True)
class DeckIssue:
    code: str
    message: str
    card_id: str | None = None
    expected: str | None = None
    actual: str | None = None


@dataclass
class DeckRepairResult:
    repaired_deck: list[tuple[str, int, list[str]]]
    notes: list[str] = field(default_factory=list)


class LorcanaDeckLinter:
    """Deterministic baseline linter for Lorcana deck legality."""

    DECK_SIZE = 60
    MAX_COPIES_PER_CARD = 4
    MAX_COLORS = 2

    @staticmethod
    def _add_issue(
        issues: list[DeckIssue],
        *,
        code: str,
        message: str,
        card_id: str | None = None,
        expected: str | None = None,
        actual: str | None = None,
    ) -> None:
        issues.append(
            DeckIssue(
                code=code,
                message=message,
                card_id=card_id,
                expected=expected,
                actual=actual,
            )
        )

    def validate(
        self,
        deck: list[tuple[str, int, list[str]]],
        existing_card_ids: set[str] | None = None,
    ) -> DeckValidationResult:
        issues: list[DeckIssue] = []
        warnings: list[str] = []
        total_cards = sum(copies for _, copies, _ in deck)

        if total_cards != self.DECK_SIZE:
            self._add_issue(
                issues,
                code="DECK_SIZE_MISMATCH",
                message=f"Deck must contain exactly {self.DECK_SIZE} cards. Got {total_cards}.",
                expected=str(self.DECK_SIZE),
                actual=str(total_cards),
            )

        unique_colors: set[str] = set()
        for card_id, copies, colors in deck:
            if copies > self.MAX_COPIES_PER_CARD:
                self._add_issue(
                    issues,
                    code="MAX_COPIES_EXCEEDED",
                    message=f"Card '{card_id}' exceeds max copies ({self.MAX_COPIES_PER_CARD}). Got {copies}.",
                    card_id=card_id,
                    expected=str(self.MAX_COPIES_PER_CARD),
                    actual=str(copies),
                )
            if existing_card_ids is not None and card_id not in existing_card_ids:
                self._add_issue(
                    issues,
                    code="CARD_NOT_IN_CATALOG",
                    message=f"Card '{card_id}' is not present in the ingested catalog.",
                    card_id=card_id,
                )
            unique_colors.update(colors)

        if len(unique_colors) > self.MAX_COLORS:
            self._add_issue(
                issues,
                code="TOO_MANY_COLORS",
                message=f"Deck uses too many colors. Max {self.MAX_COLORS}, got {len(unique_colors)}.",
                expected=str(self.MAX_COLORS),
                actual=str(len(unique_colors)),
            )

        if not deck:
            warnings.append("Deck is empty.")
            self._add_issue(
                issues,
                code="EMPTY_DECK",
                message="Deck is empty.",
            )

        errors = [issue.message for issue in issues]

        return DeckValidationResult(
            is_legal=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            total_cards=total_cards,
            issues=issues,
        )

    def repair(
        self,
        deck: list[tuple[str, int, list[str]]],
        existing_card_ids: set[str] | None = None,
    ) -> DeckRepairResult:
        notes: list[str] = []
        normalized: dict[str, tuple[int, list[str]]] = {}

        for card_id, copies, colors in deck:
            if existing_card_ids is not None and card_id not in existing_card_ids:
                notes.append(f"Removed unknown card '{card_id}' (not in catalog).")
                continue

            capped = min(max(copies, 0), self.MAX_COPIES_PER_CARD)
            if capped != copies:
                notes.append(
                    f"Capped copies for '{card_id}' from {copies} to {self.MAX_COPIES_PER_CARD}."
                )

            dedup_colors = []
            for color in colors:
                if color not in dedup_colors:
                    dedup_colors.append(color)
            if len(dedup_colors) > self.MAX_COLORS:
                notes.append(
                    f"Trimmed colors for '{card_id}' to first {self.MAX_COLORS} entries."
                )
            normalized[card_id] = (capped, dedup_colors[: self.MAX_COLORS])

        repaired = [(card_id, data[0], data[1]) for card_id, data in sorted(normalized.items())]
        total_cards = sum(copies for _, copies, _ in repaired)

        if total_cards > self.DECK_SIZE:
            overflow = total_cards - self.DECK_SIZE
            notes.append(f"Reduced deck size by {overflow} copies to reach {self.DECK_SIZE}.")
            mutable = repaired[:]
            idx = len(mutable) - 1
            while overflow > 0 and idx >= 0:
                card_id, copies, colors = mutable[idx]
                if copies > 0:
                    delta = min(copies, overflow)
                    copies -= delta
                    overflow -= delta
                    mutable[idx] = (card_id, copies, colors)
                idx -= 1
            repaired = [(card_id, copies, colors) for card_id, copies, colors in mutable if copies > 0]

        total_cards = sum(copies for _, copies, _ in repaired)
        if total_cards < self.DECK_SIZE and existing_card_ids:
            missing = self.DECK_SIZE - total_cards
            notes.append(f"Added {missing} filler copies from catalog to reach {self.DECK_SIZE}.")
            mutable = {card_id: [copies, colors] for card_id, copies, colors in repaired}
            for candidate in sorted(existing_card_ids):
                if missing <= 0:
                    break
                current = mutable.get(candidate, [0, []])
                available = self.MAX_COPIES_PER_CARD - current[0]
                if available <= 0:
                    continue
                add = min(available, missing)
                current[0] += add
                mutable[candidate] = current
                missing -= add
            repaired = [(card_id, data[0], data[1]) for card_id, data in sorted(mutable.items()) if data[0] > 0]

        return DeckRepairResult(repaired_deck=repaired, notes=notes)
