from dataclasses import dataclass
from pathlib import Path
import os

import psycopg


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
                        INSERT INTO dim_card_core (uuid, name, subtitle, set_id, collector_number, rarity)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (uuid) DO UPDATE SET
                          name = EXCLUDED.name,
                          subtitle = EXCLUDED.subtitle,
                          set_id = EXCLUDED.set_id,
                          collector_number = EXCLUDED.collector_number,
                          rarity = EXCLUDED.rarity
                        """,
                        (
                            card.uuid,
                            card.name,
                            card.subtitle,
                            card.set_id,
                            card.collector_number,
                            card.rarity,
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
