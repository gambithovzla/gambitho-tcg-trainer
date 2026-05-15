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
    def _is_lorcast_shape(raw: dict) -> bool:
        cid = str(raw.get("id") or "")
        if cid.startswith("crd_"):
            return True
        return "ink" in raw and isinstance(raw.get("type"), list)

    def normalize_raw_card(self, raw: dict) -> dict | None:
        """Maps provider-specific JSON to the internal normalized card dict."""
        if self._is_lorcast_shape(raw):
            return self._normalize_lorcast_card(raw)
        return self._normalize_generic_card(raw)

    def _normalize_lorcast_card(self, raw: dict) -> dict | None:
        card_uuid = str(raw.get("id") or "").strip()
        card_name = str(raw.get("name") or "").strip()
        if not card_uuid or not card_name:
            return None

        ink = raw.get("ink")
        colors = [str(ink)] if ink else []

        types = raw.get("type") or []
        card_type = str(types[0]) if types else None

        set_obj = raw.get("set") if isinstance(raw.get("set"), dict) else {}
        set_id = set_obj.get("code") or set_obj.get("id")

        subtypes = self._to_list(raw.get("classifications"))

        return {
            "id": card_uuid,
            "name": card_name,
            "subtitle": raw.get("version"),
            "set_id": set_id,
            "collector_number": raw.get("collector_number"),
            "rarity": raw.get("rarity"),
            "cost": self._to_int(raw.get("cost")),
            "inkwell_inkable": self._to_bool(raw.get("inkwell")),
            "strength": self._to_int(raw.get("strength")),
            "willpower": self._to_int(raw.get("willpower")),
            "lore": self._to_int(raw.get("lore")),
            "move_cost": self._to_int(raw.get("move_cost")),
            "color_aspect": colors,
            "card_type": card_type,
            "subtypes": subtypes,
            "text": raw.get("text") or raw.get("abilities") or "",
        }

    def _normalize_generic_card(self, raw: dict) -> dict | None:
        card_uuid = str(raw.get("id") or raw.get("uuid") or "").strip()
        card_name = str(raw.get("name") or "").strip()
        if not card_uuid or not card_name:
            return None

        colors = self._to_list(raw.get("colors") or raw.get("color") or raw.get("aspects"))
        subtypes = self._to_list(raw.get("subtypes"))

        card_type = raw.get("card_type") or raw.get("type")
        if isinstance(card_type, list) and card_type:
            card_type = str(card_type[0])
        elif card_type is not None:
            card_type = str(card_type)

        return {
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
            "card_type": card_type,
            "subtypes": subtypes,
            "text": raw.get("text") or raw.get("abilities") or "",
        }

    @staticmethod
    def extract_cards(payload: dict | list) -> list[dict]:
        """
        Normalizes common provider response shapes to a plain list of card dicts.
        Accepted shapes:
        - list[dict]
        - {"cards": list[dict]}
        - {"data": list[dict]}
        - {"results": list[dict]}  (Lorcast search)
        - single card dict (id + name)
        """
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            if "results" in payload and isinstance(payload["results"], list):
                return [item for item in payload["results"] if isinstance(item, dict)]
            for key in ("cards", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            if payload.get("id") and payload.get("name"):
                return [payload]
        return []

    def ingest_from_payload(self, payload: list[dict]) -> IngestionSummary:
        normalized_cards: list[dict] = []
        sql_records: list[CardRecord] = []
        rejected = 0

        for raw in payload:
            normalized = self.normalize_raw_card(raw)
            if not normalized:
                rejected += 1
                continue

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
