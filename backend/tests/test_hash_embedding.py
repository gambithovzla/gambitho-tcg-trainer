from src.infra.embeddings.hash_embedding import deterministic_embedding


def test_deterministic_embedding_length_and_stability() -> None:
    a = deterministic_embedding("hello", dim=64)
    b = deterministic_embedding("hello", dim=64)
    c = deterministic_embedding("world", dim=64)

    assert len(a) == 64
    assert a == b
    assert a != c
