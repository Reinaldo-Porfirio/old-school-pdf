from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from docforge.application.job_service import JobRegistry
from docforge.domain.errors import InvalidTransitionError
from docforge.domain.tasks import TaskSpec, TaskState


@pytest.fixture
def registry():
    return JobRegistry()


def submit(registry):
    return registry.submit(TaskSpec("internal-test", "Teste interno, sem operação PDF"))


def test_task_lifecycle_and_immutable_status(registry):
    task = submit(registry)
    snapshot = registry.status(task)
    assert snapshot.state == TaskState.PENDING
    with pytest.raises(FrozenInstanceError):
        snapshot.progress = 60
    registry.start(task)
    registry.update_progress(task, 75)
    registry.finish(task, result=Path("validated-by-future-worker.pdf"))
    record = registry.status(task)
    assert record.state == TaskState.SUCCEEDED
    assert record.progress == 100
    assert record.created_at <= record.started_at <= record.finished_at
    assert record.created_at.tzinfo is not None
    assert snapshot.state == TaskState.PENDING


def test_cancel_queued_task_never_starts(registry):
    task = submit(registry)
    registry.cancel(task)
    assert registry.status(task).state == TaskState.CANCELLED
    assert registry.token(task).requested
    with pytest.raises(InvalidTransitionError):
        registry.start(task)


def test_running_cancel_requires_worker_ack_and_drops_partial_output(registry):
    task = submit(registry)
    registry.start(task)
    registry.update_progress(task, 50)
    registry.cancel(task)
    assert registry.status(task).state == TaskState.CANCELLING
    assert registry.status(task).finished_at is None
    registry.finish(task, result=Path("partial-must-not-be-published.pdf"))
    record = registry.status(task)
    assert record.state == TaskState.CANCELLED
    assert record.result is None
    assert record.progress == 50


def test_failure_does_not_publish_output_and_terminal_cancel_is_idempotent(registry):
    task = submit(registry)
    registry.start(task)
    registry.finish(task, result=Path("bad-output.pdf"), error="Erro de teste sanitizado")
    snapshot = registry.status(task)
    registry.cancel(task)
    assert registry.status(task) == snapshot
    assert snapshot.state == TaskState.FAILED
    assert snapshot.result is None
    assert snapshot.error == "Erro de teste sanitizado"


@pytest.mark.parametrize("value", [-1, 100, 101])
def test_progress_reserves_completion_for_validated_finish(registry, value):
    task = submit(registry)
    registry.start(task)
    with pytest.raises(InvalidTransitionError):
        registry.update_progress(task, value)


def test_illegal_transitions_and_backwards_progress_are_rejected(registry):
    task = submit(registry)
    with pytest.raises(InvalidTransitionError):
        registry.finish(task)
    registry.start(task)
    with pytest.raises(InvalidTransitionError):
        registry.start(task)
    registry.update_progress(task, 40)
    with pytest.raises(InvalidTransitionError):
        registry.update_progress(task, 20)
    registry.finish(task)
    with pytest.raises(InvalidTransitionError):
        registry.finish(task)


def test_registry_accepts_concurrent_submissions_without_losing_records(registry):
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: submit(registry), range(24)))
    assert len(set(ids)) == len(registry.list_tasks()) == 24


def test_empty_task_description_is_invalid():
    with pytest.raises(ValueError):
        TaskSpec("ocr", " ")
