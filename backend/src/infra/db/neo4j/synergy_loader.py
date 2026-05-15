import os
from typing import Any

from neo4j import GraphDatabase


class Neo4jSynergyLoader:
    """
    Upserts LorcanaCard nodes and HAS_SUBTYPE / INK edges when NEO4J_URI is set.
    If Neo4j is not configured, returns len(cards) (same as stub) so counts stay consistent.
    """

    def __init__(self) -> None:
        self._uri = os.getenv("NEO4J_URI", "").strip()
        self._user = os.getenv("NEO4J_USER", "neo4j").strip()
        self._password = os.getenv("NEO4J_PASSWORD", "").strip()
        self._database = os.getenv("NEO4J_DATABASE", "neo4j").strip()

    def load(self, cards: list[dict[str, Any]]) -> int:
        if not cards:
            return 0
        if not self._uri or not self._password:
            return len(cards)

        written = 0
        try:
            driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))
        except Exception:
            return 0

        try:
            with driver.session(database=self._database) as session:
                for card in cards:
                    session.execute_write(self._merge_card, card)
                    written += 1
        except Exception:
            written = 0
        finally:
            driver.close()

        return written if written > 0 else 0

    @staticmethod
    def _merge_card(tx, card: dict[str, Any]) -> None:
        cid = card["id"]
        name = card.get("name") or ""
        card_type = card.get("card_type") or ""
        text = card.get("text") or ""
        subtypes = list(card.get("subtypes") or [])
        inks = list(card.get("color_aspect") or [])

        tx.run(
            """
            MERGE (c:LorcanaCard {id: $id})
            SET c.name = $name,
                c.card_type = $card_type,
                c.text = $text
            """,
            id=cid,
            name=name,
            card_type=card_type,
            text=text,
        )

        for st in subtypes:
            tx.run(
                """
                MERGE (c:LorcanaCard {id: $id})
                MERGE (s:Subtype {name: $st})
                MERGE (c)-[:HAS_SUBTYPE]->(s)
                """,
                id=cid,
                st=st,
            )

        for ink in inks:
            tx.run(
                """
                MERGE (c:LorcanaCard {id: $id})
                MERGE (i:Ink {name: $ink})
                MERGE (c)-[:INK]->(i)
                """,
                id=cid,
                ink=ink,
            )
