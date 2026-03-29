"""Load and validate source registry from YAML."""

from pathlib import Path
import yaml


def load_sources(registry_path: Path | None = None) -> list[dict]:
    """Load all sources from sources.yaml."""
    if registry_path is None:
        registry_path = Path(__file__).parent / "registry" / "sources.yaml"

    with open(registry_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data.get("sources", [])


def get_active_sources(registry_path: Path | None = None) -> list[dict]:
    """Return only enabled sources."""
    return [s for s in load_sources(registry_path) if s.get("enabled", True)]


def get_sources_by_tier(tier: int, registry_path: Path | None = None) -> list[dict]:
    """Return sources matching the given tier."""
    return [s for s in get_active_sources(registry_path) if s.get("tier") == tier]
