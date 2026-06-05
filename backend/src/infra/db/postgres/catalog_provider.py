from src.domain.engine.card_model import CatalogProvider
from src.infra.db.postgres.card_repository import CatalogCard, PostgresCardRepository


class PostgresCatalogProvider(CatalogProvider):
    def __init__(self, repository: PostgresCardRepository | None = None) -> None:
        self._repository = repository or PostgresCardRepository()

    def get_cards(self, card_ids: list[str]) -> dict[str, CatalogCard]:
        return self._repository.get_catalog_cards(card_ids)
