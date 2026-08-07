"""Server-owned, replayable analysis runs.

An analysis worker consumes the model stream independently of any browser connection.
Subscribers receive a numbered replay of buffered SSE events, so disconnecting a tab
only detaches the view; it does not close the model process.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import Condition, Event, Lock, Thread
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from fit2json.chats import INTERRUPTED_ANALYSIS_MESSAGE, ChatStore
from fit2json.web.sse import SSE_HEARTBEAT_SECONDS, sse

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = ("completed", "failed", "cancelled")
_MAX_RETAINED_RUNS = 200
FinishCallback = Callable[[str, str, Optional[str], str, str], None]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_frame(frame: str) -> Tuple[str, Dict[str, Any]]:
    event = "message"
    data_lines: List[str] = []
    for line in frame.splitlines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if not data_lines:
        return event, {}
    try:
        data = json.loads("\n".join(data_lines))
    except json.JSONDecodeError:
        data = {}
    return event, data if isinstance(data, dict) else {}


def _numbered(frame: str, event_id: int) -> str:
    return f"id: {event_id}\n{frame}"


class AnalysisRun:
    """One background worker plus its replay buffer and terminal state."""

    def __init__(
        self,
        run_id: str,
        source: Iterator[str],
        owner: Tuple[Optional[str], Optional[str]],
        on_finish: Optional[FinishCallback] = None,
        on_terminal: Optional[Callable[["AnalysisRun"], None]] = None,
    ):
        self.id = run_id
        self.owner = owner
        self._source = source
        self._on_finish = on_finish
        self._on_terminal = on_terminal
        self._condition = Condition()
        self._cancel_requested = Event()
        self._events: List[Tuple[int, str]] = []
        self._content = ""
        self._backend = ""
        self._replace_seen = False
        self._thinking_summary = ""
        self._thinking = ""
        self._thread: Optional[Thread] = None
        self.status = "running"
        self.error: Optional[str] = None
        self.created_at = _now()
        self.finished_at: Optional[str] = None

    def start(self) -> None:
        thread = Thread(target=self._work, name=f"fitsift-analysis-{self.id[:24]}", daemon=True)
        self._thread = thread
        thread.start()

    def join(self, timeout: Optional[float] = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def matches_owner(self, owner: Tuple[Optional[str], Optional[str]]) -> bool:
        with self._condition:
            return self.owner == owner

    def claim_cancelled(
        self,
        owner: Tuple[Optional[str], Optional[str]],
        on_finish: Optional[FinishCallback],
        persist: Callable[[], None],
    ) -> bool:
        """Bind an unclaimed Stop-before-start tombstone to its late chat request."""
        with self._condition:
            if self.status != "cancelled" or self.owner != (None, None):
                return False
            persist()
            self.owner = owner
            self._on_finish = on_finish
            if self._on_terminal is not None:
                self._on_terminal(self)
            return True

    def info(self) -> Dict[str, Any]:
        with self._condition:
            return {
                "id": self.id,
                "status": self.status,
                "error": self.error,
                "last_event_id": len(self._events),
                "created_at": self.created_at,
                "finished_at": self.finished_at,
            }

    def cancel(self) -> None:
        with self._condition:
            if self.status in TERMINAL_STATUSES:
                return
            self.status = "cancelling"
            self._cancel_requested.set()
            self._condition.notify_all()

    def cancel_before_start(self) -> None:
        self._cancel_requested.set()
        self._finish("cancelled", sse("cancelled", {}))

    def events(self, after: int = 0) -> Iterator[str]:
        """Replay events after ``after`` and then wait for new ones until terminal."""
        cursor = max(0, after)
        while True:
            heartbeat = False
            with self._condition:
                pending = self._events[cursor:]
                terminal = self.status in TERMINAL_STATUSES
                if not pending and not terminal:
                    notified = self._condition.wait(timeout=SSE_HEARTBEAT_SECONDS)
                    if not notified:
                        heartbeat = True

            if heartbeat:
                yield sse("ping", {})
                continue
            if not pending and not terminal:
                continue

            for event_id, frame in pending:
                cursor = event_id
                yield _numbered(frame, event_id)
            if terminal and cursor >= len(self._events):
                return

    def _append(self, frame: str, event: str, data: Dict[str, Any]) -> None:
        with self._condition:
            if event == "start":
                self._backend = str(data.get("backend") or "")
            elif event == "reduce":
                self._content = ""
                self._replace_seen = False
                self._thinking_summary = ""
                self._thinking = ""
            elif event == "thinking":
                self._thinking_summary = str(data.get("summary") or "")
                self._thinking = str(data.get("text") or "")
            elif event == "delta":
                self._content += str(data.get("text") or "")
            elif event == "replace":
                self._content = str(data.get("text") or "")
                self._replace_seen = True
            event_id = len(self._events) + 1
            self._events.append((event_id, frame))
            self._condition.notify_all()

    def _finish(
        self,
        status: str,
        terminal_frame: str,
        error: Optional[str] = None,
    ) -> None:
        content = self._content
        if status in ("failed", "cancelled") and self._backend == "copilot" and not self._replace_seen:
            content = ""
        if self._on_finish is not None:
            try:
                self._on_finish(
                    status,
                    content,
                    error,
                    self._thinking_summary,
                    self._thinking,
                )
            except Exception as exc:
                logger.exception("Failed to persist analysis run %s", self.id)
                status = "failed"
                error = f"Analysis finished, but its response could not be saved: {exc}"
                terminal_frame = sse("error", {"message": error})

        event, data = _parse_frame(terminal_frame)
        with self._condition:
            self.status = status
            self.error = error
            self.finished_at = _now()
            event_id = len(self._events) + 1
            self._events.append((event_id, terminal_frame))
            if self._on_terminal is not None:
                try:
                    self._on_terminal(self)
                except Exception:
                    logger.exception("Failed to persist terminal analysis run %s", self.id)
            self._condition.notify_all()

    def _work(self) -> None:
        terminal = False
        try:
            if self._cancel_requested.is_set():
                self._finish("cancelled", sse("cancelled", {}))
                return
            for frame in self._source:
                if self._cancel_requested.is_set():
                    self._finish("cancelled", sse("cancelled", {}))
                    terminal = True
                    break

                event, data = _parse_frame(frame)
                if event == "ping":
                    continue
                if event == "done":
                    content = self._content
                    chars = data.get("chars")
                    if not content.strip() or (isinstance(chars, int) and chars <= 0):
                        message = "The model returned no response. Please try again."
                        self._finish("failed", sse("error", {"message": message}), message)
                    else:
                        self._finish("completed", frame)
                    terminal = True
                    break
                if event == "error":
                    message = str(data.get("message") or "Analysis failed")
                    self._finish("failed", frame, message)
                    terminal = True
                    break
                self._append(frame, event, data)

            if not terminal:
                if self._cancel_requested.is_set():
                    self._finish("cancelled", sse("cancelled", {}))
                else:
                    message = "The analysis ended before the model returned a complete response."
                    self._finish("failed", sse("error", {"message": message}), message)
        except Exception as exc:
            message = getattr(exc, "message", None) or str(exc) or "Analysis failed"
            self._finish("failed", sse("error", {"message": message}), message)
        finally:
            close = getattr(self._source, "close", None)
            if close is not None:
                try:
                    close()
                except Exception:
                    logger.exception("Failed to close analysis source %s", self.id)


class AnalysisRunRegistry:
    """Process-local registry for the web server's active and recently finished runs."""

    def __init__(self, chats_dir: Path):
        self._lock = Lock()
        self._runs: Dict[str, AnalysisRun] = {}
        self._records_dir = chats_dir / ".analysis-runs"
        ChatStore(chats_dir).recover_interrupted_analyses()
        self._recover_records()

    def get(self, run_id: str) -> Optional[AnalysisRun]:
        with self._lock:
            return self._runs.get(run_id)

    def create(
        self,
        run_id: str,
        source: Iterator[str],
        owner: Tuple[Optional[str], Optional[str]],
        on_finish: Optional[FinishCallback],
    ) -> Tuple[AnalysisRun, bool]:
        with self._lock:
            existing = self._runs.get(run_id)
            if existing is not None:
                return existing, False
            self._trim_locked()
            run = AnalysisRun(run_id, source, owner, on_finish, self._persist_run)
            self._persist_run(run)
            self._runs[run_id] = run
            return run, True

    def discard(self, run_id: str) -> None:
        with self._lock:
            self._runs.pop(run_id, None)
            path = self._record_path(run_id)
            if path.exists():
                path.unlink()

    def cancel(
        self,
        run_id: str,
    ) -> Tuple[Optional[AnalysisRun], Optional[Dict[str, Any]]]:
        """Atomically cancel a run, return durable terminal state, or create a tombstone."""
        created = False
        persisted = None
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                record = self._read_record(run_id)
                if record is not None:
                    persisted = self._record_info(record, run_id)
                else:
                    self._trim_locked()
                    run = AnalysisRun(
                        run_id,
                        iter(()),
                        (None, None),
                        on_terminal=self._persist_run,
                    )
                    run.cancel_before_start()
                    self._runs[run_id] = run
                    created = True
        if persisted is not None:
            return None, persisted
        assert run is not None
        if not created:
            run.cancel()
        return run, None

    def shutdown(self) -> None:
        """Stop every worker before the web process exits."""
        with self._lock:
            runs = list(self._runs.values())
        for run in runs:
            run.cancel()
        for run in runs:
            run.join()

    def persisted(
        self,
        run_id: str,
    ) -> Optional[Tuple[Dict[str, Any], Tuple[Optional[str], Optional[str]]]]:
        with self._lock:
            record = self._read_record(run_id)
            if record is None:
                return None
            owner_data = record.get("owner") or [None, None]
            owner = (
                owner_data[0] if len(owner_data) > 0 else None,
                owner_data[1] if len(owner_data) > 1 else None,
            )
            info = self._record_info(record, run_id)
            return info, owner

    def claim_persisted_cancelled(
        self,
        run_id: str,
        owner: Tuple[Optional[str], Optional[str]],
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._read_record(run_id)
            if record is None:
                return None
            owner_data = record.get("owner") or [None, None]
            if record.get("status") != "cancelled" or owner_data != [None, None]:
                return None
            record["owner"] = list(owner)
            self._write_record(record)
            return {
                "id": str(record.get("id") or run_id),
                "status": "cancelled",
                "error": None,
                "last_event_id": int(record.get("last_event_id") or 1),
                "created_at": str(record.get("created_at") or _now()),
                "finished_at": record.get("finished_at"),
            }

    @staticmethod
    def _record_info(record: Dict[str, Any], run_id: str) -> Dict[str, Any]:
        return {
            "id": str(record.get("id") or run_id),
            "status": str(record.get("status") or "failed"),
            "error": record.get("error"),
            "last_event_id": int(record.get("last_event_id") or 0),
            "created_at": str(record.get("created_at") or _now()),
            "finished_at": record.get("finished_at"),
        }

    def _record_path(self, run_id: str) -> Path:
        digest = sha256(run_id.encode("utf-8")).hexdigest()
        return self._records_dir / f"{digest}.json"

    def _read_record(self, run_id: str) -> Optional[Dict[str, Any]]:
        path = self._record_path(run_id)
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(record, dict) or record.get("id") != run_id:
            return None
        return record

    def _write_record(self, record: Dict[str, Any]) -> None:
        self._records_dir.mkdir(parents=True, exist_ok=True)
        path = self._record_path(str(record["id"]))
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _persist_run(self, run: AnalysisRun) -> None:
        info = run.info()
        record = {
            **info,
            "owner": list(run.owner),
        }
        self._write_record(record)

    def _recover_records(self) -> None:
        if not self._records_dir.exists():
            return
        for path in self._records_dir.glob("*.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(record, dict) or not record.get("id"):
                continue
            if record.get("status") in ("running", "cancelling"):
                record["status"] = "failed"
                record["error"] = INTERRUPTED_ANALYSIS_MESSAGE
                record["finished_at"] = _now()
                record["last_event_id"] = max(1, int(record.get("last_event_id") or 0))
                try:
                    self._write_record(record)
                except OSError:
                    logger.exception("Failed to recover interrupted analysis run %s", record["id"])

    def _trim_locked(self) -> None:
        if len(self._runs) < _MAX_RETAINED_RUNS:
            return
        for run_id, run in list(self._runs.items()):
            if run.info()["status"] in TERMINAL_STATUSES:
                del self._runs[run_id]
                if len(self._runs) < _MAX_RETAINED_RUNS:
                    break


_registries: Dict[str, AnalysisRunRegistry] = {}
_registries_lock = Lock()


def get_analysis_run_registry(chats_dir: Path) -> AnalysisRunRegistry:
    key = str(chats_dir.expanduser().resolve())
    with _registries_lock:
        registry = _registries.get(key)
        if registry is None:
            registry = AnalysisRunRegistry(chats_dir)
            _registries[key] = registry
        return registry
