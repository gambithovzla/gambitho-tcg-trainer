"""
Build two random 60-card decks from the PostgreSQL catalog and run a real-card match.

Usage (from backend/):
  python scripts/run_real_match_sample.py
  python scripts/run_real_match_sample.py --max-turns 10 --target-lore 6 --seed 42
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _load_env_file() -> None:
    env_path = BACKEND_ROOT / ".env"
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


def _build_random_deck(cards: list, rng: random.Random, size: int = 60) -> list[dict]:
    pool = [card for card in cards if card.card_type in {"Character", "Action", "Song"}]
    if len(pool) < 15:
        raise RuntimeError("Not enough playable cards in catalog for a 60-card deck.")
    rng.shuffle(pool)
    entries: list[dict] = []
    total = 0
    index = 0
    while total < size:
        card = pool[index % len(pool)]
        copies = min(4, size - total)
        entries.append({"card_id": card.id, "copies": copies})
        total += copies
        index += 1
    return entries


def main() -> None:
    _load_env_file()
    parser = argparse.ArgumentParser(description="Run a sample real-card Lorcana match.")
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--target-lore", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    from src.domain.engine.real_deck import DeckEntry
    from src.domain.simulation.real_match import simulate_real_card_match
    from src.infra.db.postgres.card_repository import PostgresCardRepository
    from src.infra.db.postgres.catalog_provider import PostgresCatalogProvider

    repository = PostgresCardRepository()
    cards, total = repository.list_catalog_cards(limit=500, offset=0)
    if total < 60:
        raise RuntimeError(f"Catalog too small ({total} cards). Run hybrid_bootstrap first.")

    rng = random.Random(args.seed)
    p1 = _build_random_deck(cards, rng)
    p2 = _build_random_deck(cards, rng)

    result = simulate_real_card_match(
        catalog=PostgresCatalogProvider(repository),
        player_one_deck=[DeckEntry(card_id=e["card_id"], copies=e["copies"]) for e in p1],
        player_two_deck=[DeckEntry(card_id=e["card_id"], copies=e["copies"]) for e in p2],
        max_turns=args.max_turns,
        target_lore=args.target_lore,
        rng_seed=args.seed,
    )

    print(
        json.dumps(
            {
                "winner_player_id": result.winner_player_id,
                "turns_played": result.turns_played,
                "engine_mode": result.engine_mode,
                "turn_protocol_version": result.turn_protocol_version,
                "cards_referenced": result.cards_referenced[:12],
                "history_tail": result.history[-8:],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
