import asyncio

import pytest

from agentguard import ResourceAccess, ResourceLockManager, ResourceLockTimeout
from agentguard.runtime.tool import Tool, ToolRegistry


def noop() -> None:
    return None


def test_tool_resource_declarations_are_immutable_and_capability_consistent() -> None:
    tool = Tool(
        "write",
        noop,
        capabilities={"write"},
        resources={" config.json ": "write"},
    )
    assert dict(tool.resources) == {"config.json": ResourceAccess.WRITE}
    with pytest.raises(TypeError):
        tool.resources["other.json"] = ResourceAccess.WRITE

    with pytest.raises(ValueError):
        Tool("bad", noop, capabilities={"read"}, resources={"config.json": "write"})
    with pytest.raises(ValueError):
        Tool("bad", noop, capabilities={"write", "destructive"}, resources={" ": "write"})


def test_registry_preserves_tools_without_resource_declarations() -> None:
    registry = ToolRegistry()
    registry.register("noop", noop)
    assert registry.get("noop").resources == {}


@pytest.mark.asyncio
async def test_reads_can_overlap_but_writes_are_exclusive() -> None:
    manager = ResourceLockManager()
    entered: list[str] = []
    release = asyncio.Event()

    async def reader(name: str) -> None:
        async with manager.hold({"file": "read"}):
            entered.append(name)
            await release.wait()

    first = asyncio.create_task(reader("a"))
    second = asyncio.create_task(reader("b"))
    await asyncio.sleep(0)
    assert entered == ["a", "b"]
    release.set()
    await asyncio.gather(first, second)


@pytest.mark.asyncio
async def test_writer_priority_blocks_later_reader() -> None:
    manager = ResourceLockManager()
    release = asyncio.Event()
    order: list[str] = []

    async def first_reader() -> None:
        async with manager.hold({"file": "read"}):
            order.append("reader-1")
            await release.wait()

    async def writer() -> None:
        async with manager.hold({"file": "write"}):
            order.append("writer")

    async def second_reader() -> None:
        async with manager.hold({"file": "read"}):
            order.append("reader-2")

    first = asyncio.create_task(first_reader())
    await asyncio.sleep(0)
    write_task = asyncio.create_task(writer())
    await asyncio.sleep(0)
    read_task = asyncio.create_task(second_reader())
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(first, write_task, read_task)
    assert order == ["reader-1", "writer", "reader-2"]


@pytest.mark.asyncio
async def test_multi_resource_timeout_releases_partial_acquisition() -> None:
    manager = ResourceLockManager()
    blocker = asyncio.Event()

    async def hold_b() -> None:
        async with manager.hold({"b": "write"}):
            await blocker.wait()

    task = asyncio.create_task(hold_b())
    await asyncio.sleep(0)
    with pytest.raises(ResourceLockTimeout):
        async with manager.hold({"a": "write", "b": "write"}, timeout=0.01):
            pass
    blocker.set()
    await task
    async with manager.hold({"a": "write", "b": "write"}, timeout=0.01):
        pass


@pytest.mark.asyncio
async def test_lock_releases_after_body_exception_and_cancellation() -> None:
    manager = ResourceLockManager()
    with pytest.raises(RuntimeError):
        async with manager.hold({"file": "write"}):
            raise RuntimeError("boom")
    async with manager.hold({"file": "write"}, timeout=0.01):
        pass

    entered = asyncio.Event()

    async def cancellable() -> None:
        async with manager.hold({"file": "write"}):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(cancellable())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with manager.hold({"file": "write"}, timeout=0.01):
        pass
