"""Process-local resource declarations and deadlock-resistant async locks."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from .permission import normalize_capabilities


class ResourceAccess(StrEnum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class ResourceLockTimeout(TimeoutError):
    """Raised when a resource lock cannot be acquired before its deadline."""


def normalize_resources(resources: Mapping[str, ResourceAccess | str] | None) -> Mapping[str, ResourceAccess]:
    """Validate resource IDs and return a deterministic immutable mapping."""

    if resources is None:
        return MappingProxyType({})
    if not isinstance(resources, Mapping):
        raise TypeError("resources must be a mapping of resource IDs to access modes")
    normalized: dict[str, ResourceAccess] = {}
    for resource, access in resources.items():
        if not isinstance(resource, str):
            raise TypeError("resource IDs must be strings")
        resource_id = resource.strip()
        if not resource_id:
            raise ValueError("resource IDs must be non-empty")
        try:
            mode = access if isinstance(access, ResourceAccess) else ResourceAccess(str(access).strip().lower())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"unsupported resource access mode: {access!r}") from exc
        normalized[resource_id] = mode
    return MappingProxyType(dict(sorted(normalized.items())))


def validate_resource_capabilities(
    resources: Mapping[str, ResourceAccess], capabilities: Any
) -> None:
    """Ensure every declared resource mode is covered by Tool capabilities."""

    labels = normalize_capabilities(capabilities)
    for resource, mode in resources.items():
        required = {"read"} if mode is ResourceAccess.READ else {"write"}
        if mode is ResourceAccess.DESTRUCTIVE:
            required.add("destructive")
        missing = required - labels
        if missing:
            raise ValueError(
                f"resource {resource!r} requires capabilities: {sorted(missing)}"
            )


@dataclass
class _ResourceState:
    readers: int = 0
    writer: bool = False
    waiting_writers: int = 0


class ResourceLockManager:
    """Write-priority process-local read/write lock manager.

    A request acquires all resources in sorted order. The public context
    manager releases every acquired lock even when the body raises or the
    task is cancelled.
    """

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._states: dict[str, _ResourceState] = {}

    @asynccontextmanager
    async def hold(
        self,
        resources: Mapping[str, ResourceAccess | str] | None,
        *,
        timeout: float | None = None,
    ) -> AsyncIterator[None]:
        normalized = normalize_resources(resources)
        if timeout is not None and timeout < 0:
            raise ValueError("lock timeout cannot be negative")
        acquired: list[tuple[str, ResourceAccess]] = []
        deadline = None if timeout is None else time.monotonic() + timeout
        try:
            for resource, mode in normalized.items():
                await self._acquire_one(resource, mode, deadline)
                acquired.append((resource, mode))
            yield
        finally:
            for resource, mode in reversed(acquired):
                await self._release_one(resource, mode)

    async def _acquire_one(
        self,
        resource: str,
        mode: ResourceAccess,
        deadline: float | None,
    ) -> None:
        async with self._condition:
            state = self._states.setdefault(resource, _ResourceState())
            is_writer = mode in (ResourceAccess.WRITE, ResourceAccess.DESTRUCTIVE)
            if is_writer:
                state.waiting_writers += 1
            try:
                while (
                    state.writer
                    or (is_writer and state.readers > 0)
                    or (not is_writer and state.waiting_writers > 0)
                ):
                    remaining = None if deadline is None else deadline - time.monotonic()
                    if remaining is not None and remaining <= 0:
                        raise ResourceLockTimeout(
                            f"timed out waiting for resource lock: {resource}"
                        )
                    try:
                        if remaining is None:
                            await self._condition.wait()
                        else:
                            await asyncio.wait_for(self._condition.wait(), remaining)
                    except asyncio.TimeoutError as exc:
                        raise ResourceLockTimeout(
                            f"timed out waiting for resource lock: {resource}"
                        ) from exc
                if is_writer:
                    state.writer = True
                else:
                    state.readers += 1
            finally:
                if is_writer:
                    state.waiting_writers -= 1

    async def _release_one(self, resource: str, mode: ResourceAccess) -> None:
        async with self._condition:
            state = self._states.get(resource)
            if state is None:
                return
            if mode in (ResourceAccess.WRITE, ResourceAccess.DESTRUCTIVE):
                state.writer = False
            else:
                state.readers -= 1
            if state.readers == 0 and not state.writer and state.waiting_writers == 0:
                self._states.pop(resource, None)
            self._condition.notify_all()
