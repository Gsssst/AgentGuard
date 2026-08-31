"""Storage boundaries for structured Runtime events."""

import json
from pathlib import Path
from typing import Protocol

from .model import RuntimeEvent


class EventSink(Protocol):
    """Destination for Runtime events."""

    def emit(self, event: RuntimeEvent) -> None:
        """Persist or retain one event."""


class InMemoryEventSink:
    """Retain events in order for tests and local inspection."""

    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    def emit(self, event: RuntimeEvent) -> None:
        self.events.append(event)


class JsonlEventSink:
    """Append each Runtime event as one JSON object per line."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: RuntimeEvent) -> None:
        line = json.dumps(event.to_dict(), ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(line)
            file.write("\n")
