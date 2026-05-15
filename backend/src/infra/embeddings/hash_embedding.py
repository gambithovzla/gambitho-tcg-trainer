import hashlib


def deterministic_embedding(text: str, dim: int = 64) -> list[float]:
    """
    Deterministic pseudo-embedding from text (no external model).
    Values in [-1, 1], stable across runs for the same input string.
    """
    if dim <= 0:
        return []
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    out: list[float] = []
    counter = 0
    while len(out) < dim:
        chunk = hashlib.sha256(digest + counter.to_bytes(4, "big")).digest()
        counter += 1
        for byte in chunk:
            out.append((byte / 127.5) - 1.0)
            if len(out) >= dim:
                break
    return out[:dim]
