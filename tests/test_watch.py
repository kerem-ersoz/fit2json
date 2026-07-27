"""Tests for the OS-agnostic polling loop (``fit2json.watch.run_watch``).

The loop is exercised without any real sleeping by using ``interval=0`` (the
interruptible wait returns immediately) and bounding iterations with ``max_runs``
or an injected stop event.
"""

import threading

from fit2json.watch import run_watch


def _collector():
    msgs = []
    return msgs, msgs.append


class TestRunWatch:
    def test_runs_exactly_max_runs_times(self):
        calls = []
        _, emit = _collector()

        runs = run_watch(
            lambda: calls.append(1),
            interval=0,
            max_runs=3,
            emit=emit,
            install_signal_handlers=False,
        )

        assert runs == 3
        assert len(calls) == 3

    def test_errors_do_not_break_the_loop(self):
        calls = []
        msgs, emit = _collector()

        def boom():
            calls.append(1)
            raise RuntimeError("transient failure")

        runs = run_watch(boom, interval=0, max_runs=3, emit=emit,
                         install_signal_handlers=False)

        # Every cycle ran despite raising, and nothing propagated.
        assert runs == 3
        assert len(calls) == 3
        assert sum("error: transient failure" in m for m in msgs) == 3

    def test_stop_event_halts_before_max_runs(self):
        stop = threading.Event()
        calls = []

        def run_once():
            calls.append(1)
            stop.set()  # request shutdown after the first cycle

        _, emit = _collector()
        runs = run_watch(
            run_once,
            interval=0,
            max_runs=None,  # unbounded — only the stop event ends it
            emit=emit,
            install_signal_handlers=False,
            stop_event=stop,
        )

        assert runs == 1
        assert len(calls) == 1

    def test_signal_handler_registration_off_main_thread_is_safe(self):
        # signal.signal() raises off the main thread; the loop must swallow that and
        # still run so it works when a parent spawns it in a worker thread.
        result = {}

        def target():
            result["runs"] = run_watch(
                lambda: None,
                interval=0,
                max_runs=1,
                emit=lambda m: None,
                install_signal_handlers=True,
            )

        t = threading.Thread(target=target)
        t.start()
        t.join(timeout=5)

        assert not t.is_alive()
        assert result["runs"] == 1

    def test_emits_lifecycle_messages(self):
        msgs, emit = _collector()
        run_watch(lambda: None, interval=0, max_runs=1, emit=emit,
                 install_signal_handlers=False)

        joined = "\n".join(msgs)
        assert "cycle 1 started" in joined
        assert "cycle 1 finished" in joined
        assert "watch stopped" in joined
