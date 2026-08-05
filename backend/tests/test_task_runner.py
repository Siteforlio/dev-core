import pytest
import asyncio

@pytest.mark.asyncio
async def test_task_runner_runs_task():
    from app.core.task_runner import TaskRunner
    runner = TaskRunner()
    results = []
    async def my_task():
        results.append("ran")
    runner.submit(my_task())
    await asyncio.sleep(0.05)
    assert results == ["ran"]
    await runner.shutdown()

@pytest.mark.asyncio
async def test_task_runner_periodic():
    from app.core.task_runner import TaskRunner
    runner = TaskRunner()
    counter = {"n": 0}
    async def tick():
        counter["n"] += 1
    runner.schedule_periodic(tick, interval_seconds=0.05)
    await asyncio.sleep(0.18)
    await runner.shutdown()
    assert counter["n"] >= 2
