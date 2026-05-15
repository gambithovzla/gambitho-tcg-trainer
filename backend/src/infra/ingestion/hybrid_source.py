from dataclasses import dataclass
from typing import Any

import httpx

from src.infra.ingestion.lorcana_ingestor import LorcanaIngestor
from src.infra.ingestion.lorcast_client import fetch_card_search

LORCANAJSON_FILES_BASE = "https://lorcanajson.org/files/current"


@dataclass(frozen=True)
class HybridFetchResult:
    raw_cards_by_source: dict[str, list[dict[str, Any]]]
    cards_seen_by_source: dict[str, int]


def _lorcanajson_all_cards_url(language: str) -> str:
    return f"{LORCANAJSON_FILES_BASE}/{language}/allCards.json"


def _lorcanajson_setdata_url(language: str, set_code: str) -> str:
    return f"{LORCANAJSON_FILES_BASE}/{language}/sets/setdata.{set_code}.json"


def fetch_lorcanajson_cards(
    *,
    language: str,
    set_codes: list[str] | None = None,
    timeout_seconds: float = 300.0,
) -> list[dict[str, Any]]:
    headers = {"User-Agent": "gambitho-tcg-trainer/0.1"}
    timeout = httpx.Timeout(timeout_seconds, connect=30.0)
    cards: list[dict[str, Any]] = []
    urls: list[str] = []
    if set_codes:
        urls = [_lorcanajson_setdata_url(language, code.strip()) for code in set_codes if code.strip()]
    if not urls:
        urls = [_lorcanajson_all_cards_url(language)]

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for url in urls:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
            cards.extend(LorcanaIngestor.extract_cards(payload))
    return cards


def fetch_lorcast_cards(
    *,
    queries: list[str],
    unique: str = "prints",
    timeout_seconds: float = 60.0,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for query in queries:
        if not query.strip():
            continue
        payload = fetch_card_search(query=query.strip(), unique=unique, timeout=timeout_seconds)
        cards.extend(LorcanaIngestor.extract_cards(payload))
    return cards


def fetch_hybrid_raw_cards(
    *,
    language: str,
    lorcanajson_set_codes: list[str] | None,
    lorcast_queries: list[str],
    include_lorcanajson: bool = True,
    include_lorcast: bool = True,
) -> HybridFetchResult:
    raw_cards_by_source: dict[str, list[dict[str, Any]]] = {"lorcanajson": [], "lorcast": []}
    if include_lorcanajson:
        raw_cards_by_source["lorcanajson"] = fetch_lorcanajson_cards(
            language=language,
            set_codes=lorcanajson_set_codes,
        )
    if include_lorcast:
        raw_cards_by_source["lorcast"] = fetch_lorcast_cards(queries=lorcast_queries)
    return HybridFetchResult(
        raw_cards_by_source=raw_cards_by_source,
        cards_seen_by_source={source: len(cards) for source, cards in raw_cards_by_source.items()},
    )


def merge_hybrid_cards(
    *,
    ingestor: LorcanaIngestor,
    raw_cards_by_source: dict[str, list[dict[str, Any]]],
    source_precedence: tuple[str, ...] = ("lorcast", "lorcanajson"),
) -> tuple[list[dict[str, Any]], int]:
    merged_by_key: dict[str, dict[str, Any]] = {}
    source_rank = {source: rank for rank, source in enumerate(source_precedence)}
    rejected = 0

    for source, cards in raw_cards_by_source.items():
        for raw in cards:
            normalized = ingestor.normalize_raw_card(raw)
            if not normalized:
                rejected += 1
                continue
            normalized["source_provider"] = source
            set_id = str(normalized.get("set_id") or "").strip().lower()
            collector = str(normalized.get("collector_number") or "").strip().lower()
            name = str(normalized.get("name") or "").strip().lower()
            if set_id and collector and name:
                key = f"{set_id}::{collector}::{name}"
            else:
                key = str(normalized.get("id") or "").strip().lower()
            if not key:
                rejected += 1
                continue
            current = merged_by_key.get(key)
            if current is None:
                merged_by_key[key] = normalized
                continue
            current_rank = source_rank.get(str(current.get("source_provider")), 999)
            candidate_rank = source_rank.get(source, 999)
            if candidate_rank < current_rank:
                merged_by_key[key] = normalized

    return list(merged_by_key.values()), rejected
