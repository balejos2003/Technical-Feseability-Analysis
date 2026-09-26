class Cache:
    def __init__(self) -> None:
        self._values: dict[str, dict[str, object]] = {}

    def get(self, key: str) -> dict[str, object] | None:
        return self._values.get(key)

    def put(self, key: str, value: dict[str, object]) -> None:
        self._values[key] = value
