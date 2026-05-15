"""HTTP client for Lorcast public API (https://lorcast.com/docs/api/cards)."""

from typing import Any

import httpx

LORCAST_SEARCH_URL = "https://api.lorcast.com/v0/cards/search"


def fetch_card_search(*, query: str, unique: str = "prints", timeout: float = 60.0) -> dict[str, Any]:
    params = {"q": query, "unique": unique}
    headers = {"User-Agent": "gambitho-tcg-trainer/0.1"}
    with httpx.Client(timeout=timeout) as client:
        response = client.get(LORCAST_SEARCH_URL, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
