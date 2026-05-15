from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from src.infra.db.postgres.card_repository import PostgresCardRepository
from src.infra.ingestion.hybrid_source import fetch_lorcanajson_cards
from src.infra.ingestion.lorcana_ingestor import LorcanaIngestor


def _load_env_file() -> None:
    env_path = Path.cwd() / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    _load_env_file()
    parser = argparse.ArgumentParser(description="Backfill official card image URLs from LorcanaJSON.")
    parser.add_argument("--language", default="en")
    args = parser.parse_args()

    ingestor = LorcanaIngestor(None, None, None)
    raw_cards = fetch_lorcanajson_cards(language=args.language, set_codes=None)
    updates: list[tuple[str, str | None, str | None]] = []
    for raw in raw_cards:
        normalized = ingestor.normalize_raw_card(raw)
        if not normalized:
            continue
        image_url = normalized.get("image_url")
        if not image_url:
            continue
        updates.append(
            (
                normalized["id"],
                image_url,
                normalized.get("image_thumbnail_url"),
            )
        )

    print(f"Preparadas {len(updates)} URLs de imagen...", flush=True)
    repository = PostgresCardRepository()
    repository.ensure_schema()

    chunk_size = 250
    updated = 0
    for start in range(0, len(updates), chunk_size):
        chunk = updates[start : start + chunk_size]
        updated += repository.update_card_images(chunk)
        print(f"  {min(start + chunk_size, len(updates))}/{len(updates)}", flush=True)

    print(json.dumps({"cards_seen": len(raw_cards), "images_updated": updated}, indent=2))


if __name__ == "__main__":
    main()
