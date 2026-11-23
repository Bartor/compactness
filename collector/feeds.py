from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

DEFAULT_FEEDS_FILE = Path(__file__).with_name("feeds.yaml")


@dataclass
class Feed:
    id: str
    city: str
    url: str | None = None
    format: str = "gtfs-rt"           # gtfs-rt | gdansk-json
    interval: float = 30.0            # seconds between polls
    enabled: bool = False
    trip_updates_url: str | None = None
    entity: str = "vehicles"          # "trip_updates" = feed offers only TripUpdates at `url`
    opts: dict = field(default_factory=dict)
    note: str = ""


def load_feeds(path: Path | None = None) -> list[Feed]:
    data = yaml.safe_load(Path(path or DEFAULT_FEEDS_FILE).read_text(encoding="utf-8"))
    names = {f.name for f in fields(Feed)}
    return [Feed(**{k: v for k, v in d.items() if k in names}) for d in data["feeds"]]
