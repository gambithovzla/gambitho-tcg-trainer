import os
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.infra.embeddings.hash_embedding import deterministic_embedding


class QdrantEmbedIndexer:
    """
    Indexes card text with deterministic vectors when QDRANT_URL is set.
    Without QDRANT_URL, returns len(cards) (stub parity with previous behavior).
    """

    VECTOR_DIM = 64

    def __init__(self) -> None:
        self._url = os.getenv("QDRANT_URL", "").strip()
        self._collection = os.getenv("QDRANT_COLLECTION", "lorcana_cards").strip()

    def index(self, cards: list[dict[str, Any]]) -> int:
        if not cards:
            return 0
        if not self._url:
            return len(cards)

        try:
            client = QdrantClient(url=self._url)
        except Exception:
            return 0

        try:
            names = [c.name for c in client.get_collections().collections]
            if self._collection not in names:
                client.create_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(
                        size=self.VECTOR_DIM,
                        distance=Distance.COSINE,
                    ),
                )

            points: list[PointStruct] = []
            for card in cards:
                cid = card["id"]
                text = str(card.get("text") or "")
                name = str(card.get("name") or "")
                payload_text = f"{name}\n{text}".strip()
                vector = deterministic_embedding(payload_text, dim=self.VECTOR_DIM)
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, cid))
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "card_id": cid,
                            "name": name,
                            "card_type": card.get("card_type"),
                            "text": text[:2000],
                        },
                    )
                )

            client.upsert(collection_name=self._collection, points=points)
            return len(points)
        except Exception:
            return 0
