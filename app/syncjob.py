"""
Running the Discogs sync in the background. A sync can take longer than the
web server's timeout, so the Sync button starts it in a thread and returns at
once, and the page then polls for the sync's log until it's done.

A job's state and log are kept in files in the sync folder (app/sync.py's
`lock_folder`), not in memory: under gunicorn the request that polls a job may
reach a different worker process from the one running it.
"""

import datetime
import json
import logging
import os
import re
import threading
import time
import uuid

from app import sync

logger = logging.getLogger("vc.sync")

# Job files older than this are deleted when the next job starts.
KEEP_SECONDS = 24 * 60 * 60

_JOB_ID = re.compile(r"[0-9a-f]{32}")


def _state_path(folder, job_id):
    return os.path.join(folder, job_id + ".json")


def _log_path(folder, job_id):
    return os.path.join(folder, job_id + ".log")


def _read_state(folder, job_id):
    try:
        with open(_state_path(folder, job_id), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_state(folder, state):
    # Write a new file and move it into place, so a poll never reads half of it.
    path = _state_path(folder, state["id"])
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(path + ".tmp", path)


def _append_log(folder, job_id, line):
    with open(_log_path(folder, job_id), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _process_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _check_alive(folder, state):
    """
    Mark a running job failed if the process running it has gone (the server
    restarted, or gunicorn replaced the worker), since it will never finish.
    """
    if state["status"] == "running" and not _process_alive(state["pid"]):
        _append_log(
            folder,
            state["id"],
            "The server stopped before the sync finished. Run it again.",
        )
        state = dict(state, status="failed", finished=_now())
        _write_state(folder, state)
    return state


def _running_job(folder):
    """
    The id of the running job, if there is one. Also deletes the files of
    jobs that finished more than KEEP_SECONDS ago.
    """
    found = None
    cutoff = time.time() - KEEP_SECONDS
    for name in os.listdir(folder):
        job_id, ext = os.path.splitext(name)
        if ext != ".json" or not _JOB_ID.fullmatch(job_id):
            continue
        state = _read_state(folder, job_id)
        if state is None:
            continue
        state = _check_alive(folder, state)
        if state["status"] == "running":
            found = job_id
        elif os.path.getmtime(_state_path(folder, job_id)) < cutoff:
            for path in (_state_path(folder, job_id), _log_path(folder, job_id)):
                try:
                    os.remove(path)
                except OSError:
                    pass
    return found


class _JobLogHandler(logging.Handler):
    """Copies the log records of one thread to a job's log file."""

    def __init__(self, folder, job_id, thread_id):
        super().__init__(logging.INFO)
        self.folder = folder
        self.job_id = job_id
        self.thread_id = thread_id
        self.errors = 0
        self.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
        )

    def emit(self, record):
        if record.thread != self.thread_id:
            return
        if record.levelno >= logging.ERROR:
            self.errors += 1
        try:
            _append_log(self.folder, self.job_id, self.format(record))
        except Exception:
            self.handleError(record)


def _spawn(target):
    threading.Thread(target=target, name="vc-sync", daemon=True).start()


def start(app, dry_run=False):
    """
    Run the sync in the background and return the job's id. If a sync job is
    still running, return that one's id instead of starting another.
    """
    folder = sync.lock_folder(app)
    running = _running_job(folder)
    if running:
        return running

    job_id = uuid.uuid4().hex
    title = "Discogs sync (dry run)" if dry_run else "Discogs sync"
    state = {
        "id": job_id,
        "title": title,
        "pid": os.getpid(),
        "status": "running",
        "started": _now(),
        "finished": None,
        "errors": 0,
    }
    open(_log_path(folder, job_id), "w").close()
    _write_state(folder, state)

    def run():
        root = logging.getLogger()
        handler = _JobLogHandler(folder, job_id, threading.get_ident())
        root.addHandler(handler)
        status = "failed"
        try:
            with app.app_context():
                sync.run(app, dry_run=dry_run)
            status = "done"
        except sync.SyncAlreadyRunning:
            # The command is running one. Say so in the log and finish.
            logger.error("A sync is already running (from the command line).")
        except Exception:
            logger.exception(title + " failed")
        finally:
            root.removeHandler(handler)
            _write_state(
                folder,
                dict(state, status=status, finished=_now(), errors=handler.errors),
            )

    _spawn(run)
    return job_id


def read(app, job_id, offset=0):
    """
    A job's state, with the part of its log from byte offset on and the offset
    to ask for next, or None if there's no such job.
    """
    if not _JOB_ID.fullmatch(job_id or ""):
        return None
    folder = sync.lock_folder(app)
    state = _read_state(folder, job_id)
    if state is None:
        return None
    # Read the state before the log: once a job's state says it's finished,
    # everything it logged is already in the file.
    state = _check_alive(folder, state)
    try:
        with open(_log_path(folder, job_id), "rb") as f:
            f.seek(max(offset, 0))
            data = f.read()
    except OSError:
        data = b""
    if state["status"] == "running":
        # Leave a line that's still being written for the next poll.
        data = data[: data.rfind(b"\n") + 1]
    return {
        "id": job_id,
        "title": state["title"],
        "status": state["status"],
        "errors": state.get("errors", 0),
        "log": data.decode("utf-8", "replace"),
        "offset": max(offset, 0) + len(data),
    }
