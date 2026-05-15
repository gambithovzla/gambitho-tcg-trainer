from dataclasses import dataclass


@dataclass(frozen=True)
class TriggerEvent:
    owner_player_id: int
    trigger_id: str
    description: str


class TheBag:
    """
    Minimal Lorcana The Bag structure for simultaneous trigger handling.
    The active player resolves own triggers first.
    """

    def __init__(self) -> None:
        self._events: list[TriggerEvent] = []

    def clone(self) -> "TheBag":
        copied = TheBag()
        copied.add_many(list(self._events))
        return copied

    def add(self, event: TriggerEvent) -> None:
        self._events.append(event)

    def add_many(self, events: list[TriggerEvent]) -> None:
        self._events.extend(events)

    def has_events(self) -> bool:
        return len(self._events) > 0

    def pop_next_for_player(self, player_id: int) -> TriggerEvent | None:
        for idx, event in enumerate(self._events):
            if event.owner_player_id == player_id:
                return self._events.pop(idx)
        return None

    def pop_any(self) -> TriggerEvent | None:
        if not self._events:
            return None
        return self._events.pop(0)
