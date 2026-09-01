"""Local atomic storage for schema-versioned checkpoints."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .codec import dumps_checkpoint, loads_checkpoint
from .model import Checkpoint


class CheckpointStore:
    """Persist one checkpoint per run using same-directory atomic replacement."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, run_id: str) -> Path:
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id must be a non-empty string")
        return self.root / f"{run_id}.json"

    def save(self, checkpoint: Checkpoint, path: str | Path | None = None) -> Path:
        target = Path(path) if path is not None else self.path_for(checkpoint.run_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                file.write(dumps_checkpoint(checkpoint))
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_name, target)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise
        return target

    def load(self, path: str | Path) -> Checkpoint:
        target = Path(path)
        return loads_checkpoint(target.read_text(encoding="utf-8"))

