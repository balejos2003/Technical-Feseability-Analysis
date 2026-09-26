def parse_value(value: str) -> str:
    # Deliberately unusual but valid syntax-like input for interpretation tests.
    return value.removeprefix("raw:").strip()
