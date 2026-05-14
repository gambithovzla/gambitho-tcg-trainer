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


class PostgresCardRepository:
    def __init__(self, dsn: str | None = None, schema_path: Path | None = None) -> None:
        self._dsn = dsn or os.getenv("POSTGRES_DSN", "postgresql://tcg:tcg@localhost:5432/tcg")
        self._schema_path = schema_path or Path(__file__).with_name("schema.sql")

    def ensure_schema(self) -> None:
        schema_sql = self._schema_path.read_text(encoding="utf-8")
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
            conn.commit()

    def upsert_cards(self, cards: list[CardRecord]) -> int:
        if not cards:
            return 0

        with psycopg.connect(self._dsn) as conn:
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
