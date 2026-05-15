from __future__ import annotations

import argparse
import json

from src.api.routes.ingestion import _build_ingestor
from src.infra.ingestion.hybrid_source import fetch_hybrid_raw_cards, merge_hybrid_cards


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap/re-sync catalog from LorcanaJSON + Lorcast."
    )
    parser.add_argument("--language", default="en")
    parser.add_argument("--lorcanajson-set-codes", default="")
    parser.add_argument("--lorcast-queries", default="set:1")
    parser.add_argument("--include-lorcanajson", action="store_true", default=False)
    parser.add_argument("--include-lorcast", action="store_true", default=False)
    parser.add_argument("--source-precedence", default="lorcast,lorcanajson")
    args = parser.parse_args()

    include_lorcanajson = args.include_lorcanajson or (not args.include_lorcast)
    include_lorcast = args.include_lorcast or (not args.include_lorcanajson)

    fetched = fetch_hybrid_raw_cards(
        language=args.language,
        lorcanajson_set_codes=_parse_csv(args.lorcanajson_set_codes),
        lorcast_queries=_parse_csv(args.lorcast_queries),
        include_lorcanajson=include_lorcanajson,
        include_lorcast=include_lorcast,
    )
    ingestor = _build_ingestor()
    merged, rejected = merge_hybrid_cards(
        ingestor=ingestor,
        raw_cards_by_source=fetched.raw_cards_by_source,
        source_precedence=tuple(_parse_csv(args.source_precedence)),
    )
    summary = ingestor.ingest_from_normalized_cards(
        merged,
        cards_seen=sum(fetched.cards_seen_by_source.values()),
        cards_rejected=rejected,
    )
    print(
        json.dumps(
            {
                "cards_seen_by_source": fetched.cards_seen_by_source,
                "merged_cards_seen": len(merged),
                "summary": {
                    "cards_seen": summary.cards_seen,
                    "cards_loaded_sql": summary.cards_loaded_sql,
                    "cards_loaded_graph": summary.cards_loaded_graph,
                    "cards_loaded_vector": summary.cards_loaded_vector,
                    "cards_rejected": summary.cards_rejected,
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
