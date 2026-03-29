"""Global fetcher class registry — avoids circular imports between runner and fetchers."""

FETCHER_CLASSES: dict[str, type] = {}


def register_fetcher(fetcher_type: str):
    """Decorator to register a fetcher class by type name."""
    def wrapper(cls):
        FETCHER_CLASSES[fetcher_type] = cls
        return cls
    return wrapper
