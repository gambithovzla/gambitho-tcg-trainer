from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any

import psycopg


@dataclass(frozen=True)
class CatalogCard:
    id: str
    name: str
    subtitle: str | None
    set_id: str | None
    collector_number: str | None
    rarity: str | None
    card_type: str | None
    cost: int | None
    strength: int | None
    willpower: int | None
    lore: int | None
    move_cost: int | None
    inkwell_inkable: bool | None
    color_aspect: list[str]
    subtypes: list[str]
    rules_text: str
    image_url: str | None
    image_thumbnail_url: str | None


@dataclass(frozen=True)
class CardRecord:
    uuid: str
    name: str
    subtitle: str | None
    set_id: str | None
    collector_number: str | None
    rarity: str | None
    cost: int | None
    inkwell_inkable: bool | None
    strength: int | None
    willpower: int | None
    lore: int | None
    move_cost: int | None
    color_aspect: list[str]
    card_type: str | None
    subtypes: list[str]
    rules_text: str
    source_provider: str
    image_url: str | None = None
    image_thumbnail_url: str | None = None


@dataclass(frozen=True)
class CardIntentProfile:
    card_id: str
    cost: int | None
    strength: int | None
    willpower: int | None
    lore: int | None
    card_type: str | None
    subtypes: list[str]


class PostgresCardRepository:
    def __init__(
        self,
        dsn: str | None = None,
        schema_path: Path | None = None,
        connect_timeout: int | None = None,
    ) -> None:
        self._dsn = dsn or os.getenv("POSTGRES_DSN", "postgresql://tcg:tcg@localhost:5432/tcg")
        self._schema_path = schema_path or Path(__file__).with_name("schema.sql")
        self._connect_timeout = connect_timeout or int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "2"))

    def ensure_schema(self) -> None:
        schema_sql = self._schema_path.read_text(encoding="utf-8")
        with psycopg.connect(self._dsn, connect_timeout=self._connect_timeout) as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
            conn.commit()

    def upsert_cards(self, cards: list[CardRecord]) -> int:
        if not cards:
            return 0

        with psycopg.connect(self._dsn, connect_timeout=self._connect_timeout) as conn:
            with conn.cursor() as cur:
                for card in cards:
                    cur.execute(
                        """
                        INSERT INTO dim_card_core (
                          uuid, name, subtitle, set_id, collector_number, rarity,
                          image_url, image_thumbnail_url
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (uuid) DO UPDATE SET
                          name = EXCLUDED.name,
                          subtitle = EXCLUDED.subtitle,
                          set_id = EXCLUDED.set_id,
                          collector_number = EXCLUDED.collector_number,
                          rarity = EXCLUDED.rarity,
                          image_url = COALESCE(EXCLUDED.image_url, dim_card_core.image_url),
                          image_thumbnail_url = COALESCE(
                            EXCLUDED.image_thumbnail_url, dim_card_core.image_thumbnail_url
                          )
                        """,
                        (
                            card.uuid,
                            card.name,
                            card.subtitle,
                            card.set_id,
                            card.collector_number,
                            card.rarity,
                            card.image_url,
                            card.image_thumbnail_url,
                        ),
                    )

                    cur.execute(
                        """
                        INSERT INTO fact_card_stats (
                          card_uuid, cost, inkwell_inkable, strength, willpower, lore, move_cost
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (card_uuid) DO UPDATE SET
                          cost = EXCLUDED.cost,
                          inkwell_inkable = EXCLUDED.inkwell_inkable,
                          strength = EXCLUDED.strength,
                          willpower = EXCLUDED.willpower,
                          lore = EXCLUDED.lore,
                          move_cost = EXCLUDED.move_cost
                        """,
                        (
                            card.uuid,
                            card.cost,
                            card.inkwell_inkable,
                            card.strength,
                            card.willpower,
                            card.lore,
                            card.move_cost,
                        ),
                    )

                    cur.execute(
                        """
                        INSERT INTO fact_card_rules (card_uuid, rules_text, source_provider)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (card_uuid) DO UPDATE SET
                          rules_text = EXCLUDED.rules_text,
                          source_provider = EXCLUDED.source_provider,
                          updated_at = NOW()
                        """,
                        (
                            card.uuid,
                            card.rules_text,
                            card.source_provider,
                        ),
                    )

                    cur.execute(
                        """
                        INSERT INTO dim_card_tags (card_uuid, color_aspect, card_type, subtypes)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (card_uuid) DO UPDATE SET
                          color_aspect = EXCLUDED.color_aspect,
                          card_type = EXCLUDED.card_type,
                          subtypes = EXCLUDED.subtypes
                        """,
                        (
                            card.uuid,
                            card.color_aspect,
                            card.card_type,
                            card.subtypes,
                        ),
                    )
            conn.commit()

        return len(cards)

    def update_card_images(self, updates: list[tuple[str, str | None, str | None]]) -> int:
        if not updates:
            return 0

        with psycopg.connect(self._dsn, connect_timeout=self._connect_timeout) as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    UPDATE dim_card_core
                    SET image_url = %s, image_thumbnail_url = %s
                    WHERE uuid = %s
                    """,
                    [(url, thumb, card_id) for card_id, url, thumb in updates],
                )
            conn.commit()
        return len(updates)

    def _catalog_select_sql(self) -> str:
        return """
            SELECT
              core.uuid,
              core.name,
              core.subtitle,
              core.set_id,
              core.collector_number,
              core.rarity,
              core.image_url,
              core.image_thumbnail_url,
              stats.cost,
              stats.strength,
              stats.willpower,
              stats.lore,
              tags.color_aspect,
              tags.subtypes,
              rules.rules_text,
              stats.move_cost,
              stats.inkwell_inkable,
              tags.card_type
            FROM dim_card_core AS core
            LEFT JOIN fact_card_stats AS stats ON stats.card_uuid = core.uuid
            LEFT JOIN dim_card_tags AS tags ON tags.card_uuid = core.uuid
            LEFT JOIN fact_card_rules AS rules ON rules.card_uuid = core.uuid
        """

    @staticmethod
    def _catalog_row_to_card(row: tuple[Any, ...]) -> CatalogCard:
        subtypes = list(row[13]) if row[13] else []
        colors = list(row[12]) if row[12] else []
        return CatalogCard(
            id=row[0],
            name=row[1],
            subtitle=row[2],
            set_id=row[3],
            collector_number=str(row[4]) if row[4] is not None else None,
            rarity=row[5],
            image_url=row[6],
            image_thumbnail_url=row[7],
            cost=row[8],
            strength=row[9],
            willpower=row[10],
            lore=row[11],
            move_cost=row[15],
            inkwell_inkable=row[16],
            color_aspect=colors,
            subtypes=subtypes,
            rules_text=row[14] or "",
            card_type=row[17],
        )

    def list_catalog_cards(
        self,
        *,
        search: str | None = None,
        limit: int = 48,
        offset: int = 0,
    ) -> tuple[list[CatalogCard], int]:
        safe_limit = max(1, min(limit, 200))
        safe_offset = max(0, offset)
        term = (search or "").strip()

        where_clause = ""
        params: list[Any] = []
        if term:
            where_clause = """
                WHERE core.name ILIKE %s
                   OR core.uuid = %s
                   OR core.subtitle ILIKE %s
            """
            like = f"%{term}%"
            params.extend([like, term, like])

        with psycopg.connect(self._dsn, connect_timeout=self._connect_timeout) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) FROM dim_card_core AS core {where_clause}",
                    params,
                )
                total = int(cur.fetchone()[0])

                cur.execute(
                    f"""
                    {self._catalog_select_sql()}
                    {where_clause}
                    ORDER BY core.name ASC
                    LIMIT %s OFFSET %s
                    """,
                    [*params, safe_limit, safe_offset],
                )
                rows = cur.fetchall()

        return [self._catalog_row_to_card(row) for row in rows], total

    def get_catalog_card(self, card_id: str) -> CatalogCard | None:
        with psycopg.connect(self._dsn, connect_timeout=self._connect_timeout) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"{self._catalog_select_sql()} WHERE core.uuid = %s",
                    (card_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return self._catalog_row_to_card(row)

    def get_existing_card_ids(self, card_ids: list[str]) -> set[str]:
        if not card_ids:
            return set()

        with psycopg.connect(self._dsn, connect_timeout=self._connect_timeout) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT uuid FROM dim_card_core WHERE uuid = ANY(%s)",
                    (card_ids,),
                )
                rows = cur.fetchall()
        return {row[0] for row in rows}

    def get_intent_profiles(self, card_ids: list[str]) -> dict[str, CardIntentProfile]:
        if not card_ids:
            return {}

        with psycopg.connect(self._dsn, connect_timeout=self._connect_timeout) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      core.uuid,
                      stats.cost,
                      stats.strength,
                      stats.willpower,
                      stats.lore,
                      tags.card_type,
                      tags.subtypes
                    FROM dim_card_core AS core
                    LEFT JOIN fact_card_stats AS stats ON stats.card_uuid = core.uuid
                    LEFT JOIN dim_card_tags AS tags ON tags.card_uuid = core.uuid
                    WHERE core.uuid = ANY(%s)
                    """,
                    (card_ids,),
                )
                rows = cur.fetchall()

        out: dict[str, CardIntentProfile] = {}
        for row in rows:
            subtypes = list(row[6]) if row[6] else []
            out[row[0]] = CardIntentProfile(
                card_id=row[0],
                cost=row[1],
                strength=row[2],
                willpower=row[3],
                lore=row[4],
                card_type=row[5],
                subtypes=subtypes,
            )
        return out
