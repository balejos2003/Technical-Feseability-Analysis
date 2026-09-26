"""Small service entry point used by discovery and analysis scenarios."""

from .cache import Cache


def load_record(record_id: str, cache: Cache) -> dict[str, object]:
    cached = cache.get(record_id)
    if cached is not None:
        return cached
    record = {"id": record_id, "status": "loaded"}
    cache.put(record_id, record)
    return record
