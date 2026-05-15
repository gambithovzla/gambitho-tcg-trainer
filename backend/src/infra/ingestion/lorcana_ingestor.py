from dataclasses import dataclass

from src.infra.db.postgres.card_repository import CardRecord


@dataclass
class IngestionSummary:
    cards_seen: int
    cards_loaded_sql: int
    cards_loaded_graph: int
    cards_loaded_vector: int
    cards_rejected: int


class LorcanaIngestor:
    def __init__(self, card_repository, graph_loader, embed_indexer) -> None:
        self._card_repository = card_repository
        self._graph_loader = graph_loader
        self._embed_indexer = embed_indexer

    @staticmethod
    def _to_int(value) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_bool(value) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.lower().strip()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return None

    @staticmethod
    def _to_list(value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        return [str(value)]

    @staticmethod
    def extract_cards(payload: dict | list) -> list[dict]:
        """
        Normalizes common provider response shapes to a plain list of card dicts.
        Accepted shapes:
        - list[dict]
        - {"cards": list[dict]}
        - {"data": list[dict]}
        """
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("cards", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    def ingest_from_payload(self, payload: list[dict]) -> IngestionSummary:
        normalized_cards: list[dict] = []
        sql_records: list[CardRecord] = []
        rejected = 0

        for raw in payload:
            card_uuid = str(raw.get("id") or raw.get("uuid") or "").strip()
            card_name = str(raw.get("name") or "").strip()
            if not card_uuid or not card_name:
                rejected += 1
                continue

            colors = self._to_list(raw.get("colors") or raw.get("color") or raw.get("aspects"))
            subtypes = self._to_list(raw.get("subtypes"))

            normalized = {
                "id": card_uuid,
                "name": card_name,
                "subtitle": raw.get("subtitle"),
                "set_id": raw.get("set_id") or raw.get("setCode"),
                "collector_number": raw.get("collector_number") or raw.get("number"),
                "rarity": raw.get("rarity"),
                "cost": self._to_int(raw.get("cost")),
                "inkwell_inkable": self._to_bool(raw.get("inkwell_inkable") or raw.get("inkwell")),
                "strength": self._to_int(raw.get("strength")),
                "willpower": self._to_int(raw.get("willpower")),
                "lore": self._to_int(raw.get("lore")),
                "move_cost": self._to_int(raw.get("move_cost")),
                "color_aspect": colors,
                "card_type": raw.get("card_type") or raw.get("type"),
                "subtypes": subtypes,
                "text": raw.get("text") or raw.get("abilities") or "",
            }
            normalized_cards.append(normalized)

            sql_records.append(
                CardRecord(
                    uuid=normalized["id"],
                    name=normalized["name"],
                    subtitle=normalized["subtitle"],
                    set_id=normalized["set_id"],
                    collector_number=normalized["collector_number"],
                    rarity=normalized["rarity"],
                    cost=normalized["cost"],
                    inkwell_inkable=normalized["inkwell_inkable"],
                    strength=normalized["strength"],
                    willpower=normalized["willpower"],
                    lore=normalized["lore"],
                    move_cost=normalized["move_cost"],
                    color_aspect=normalized["color_aspect"],
                    card_type=normalized["card_type"],
                    subtypes=normalized["subtypes"],
                )
            )

        self._card_repository.ensure_schema()
        sql_loaded = self._card_repository.upsert_cards(sql_records)
        graph_loaded = self._graph_loader.load(normalized_cards)
        vector_loaded = self._embed_indexer.index(normalized_cards)

        return IngestionSummary(
            cards_seen=len(payload),
            cards_loaded_sql=sql_loaded,
            cards_loaded_graph=graph_loaded,
            cards_loaded_vector=vector_loaded,
            cards_rejected=rejected,
        )
