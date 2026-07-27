"""OS-agnostic polling loop for continuous fetching.

This is a plain in-process scheduler with no OS-specific dependencies: it works the
same on macOS, Linux, and Windows, and inside a long-lived container — no cron,
launchd, or Task Scheduler required.

It is deliberately designed to be driven by a parent process (for example a frontend
that spawns the CLI as a subprocess):

* **Non-blocking / headless** — the loop performs no interactive I/O of its own, so it
  never waits on a prompt. Callers should pass work (``run_once``) that is likewise
  non-interactive.
* **Clean shutdown** — it installs best-effort ``SIGINT`` / ``SIGTERM`` handlers and
  sleeps on a :class:`threading.Event`, so a parent can stop it promptly with a signal
  (e.g. ``docker stop`` / ``Ctrl-C``) instead of killing it hard.
* **Resilient** — an exception raised by a single cycle is reported via ``emit`` and
  swallowed, so one bad poll (network blip, expired token, daemon asleep) never tears
  down the loop.
"""

from __future__ import annotations

import signal
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional, Tuple


def _default_emit(message: str) -> None:
    print(f"[watch] {message}", file=sys.stderr, flush=True)


def run_watch(
    run_once: Callable[[], None],
    interval: float,
    *,
    max_runs: Optional[int] = None,
    emit: Callable[[str], None] = _default_emit,
    install_signal_handlers: bool = True,
    stop_event: Optional[threading.Event] = None,
) -> int:
    """Invoke ``run_once`` every ``interval`` seconds until stopped.

    Args:
        run_once: Zero-argument callable performing one poll/fetch cycle.
        interval: Seconds to wait between cycles. The wait is interruptible, so a
            stop signal wakes the loop immediately instead of after the full delay.
        max_runs: Optional cap on the number of cycles; ``None`` runs until stopped.
        emit: Sink for human-readable status lines (defaults to flushed stderr).
        install_signal_handlers: Register ``SIGINT`` / ``SIGTERM`` handlers that request
            a graceful stop. Best-effort: silently skipped when unavailable (e.g. not on
            the main thread, or an unsupported platform).
        stop_event: Optional externally-owned event; setting it stops the loop. A fresh
            one is created when omitted.

    Returns:
        The number of cycles that were executed.
    """
    stop = stop_event or threading.Event()
    restore: List[Tuple[int, Any]] = []

    if install_signal_handlers:
        def _request_stop(signum, _frame):  # pragma: no cover - exercised via signals
            emit(f"received signal {signum}; stopping after the current cycle")
            stop.set()

        for name in ("SIGINT", "SIGTERM"):
            sig = getattr(signal, name, None)
            if sig is None:
                continue
            try:
                previous = signal.signal(sig, _request_stop)
                restore.append((sig, previous))
            except (ValueError, OSError, RuntimeError):
                # Not on the main thread, or the signal is unsupported here.
                pass

    runs = 0
    try:
        while not stop.is_set():
            runs += 1
            started = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            emit(f"cycle {runs} started at {started}")
            try:
                run_once()
            except Exception as exc:  # noqa: BLE001 - a bad cycle must not kill the loop
                emit(f"cycle {runs} error: {exc}")
            else:
                emit(f"cycle {runs} finished")

            if max_runs is not None and runs >= max_runs:
                break
            if stop.is_set():
                break
            # Interruptible sleep: returns early as soon as ``stop`` is set.
            stop.wait(interval)
    finally:
        for sig, previous in restore:
            try:
                signal.signal(sig, previous)
            except (ValueError, OSError, RuntimeError):  # pragma: no cover - defensive
                pass

    emit("watch stopped")
    return runs
