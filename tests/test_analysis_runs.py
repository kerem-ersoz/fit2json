"""Concurrency tests for server-owned analysis runs."""

import threading

from fit2json.web.analysis_runs import AnalysisRunRegistry


def test_cancel_serializes_with_run_creation(tmp_path):
    registry = AnalysisRunRegistry(tmp_path / "chats")
    persist_started = threading.Event()
    release_persist = threading.Event()
    original_persist = registry._persist_run

    def blocked_persist(run):
        persist_started.set()
        assert release_persist.wait(timeout=2)
        original_persist(run)

    registry._persist_run = blocked_persist
    created = {}
    cancelled = {}

    def create():
        created["run"], _ = registry.create(
            "run-race",
            iter(()),
            (None, None),
            None,
        )

    def cancel():
        cancelled["run"], cancelled["persisted"] = registry.cancel("run-race")

    create_thread = threading.Thread(target=create)
    create_thread.start()
    assert persist_started.wait(timeout=1)

    cancel_thread = threading.Thread(target=cancel)
    cancel_thread.start()
    release_persist.set()
    create_thread.join(timeout=2)
    cancel_thread.join(timeout=2)

    assert cancelled["persisted"] is None
    assert cancelled["run"] is created["run"]
    assert created["run"].info()["status"] == "cancelling"
