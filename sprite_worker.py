"""Keep just the accepted Night Shift jobs awake on a dedicated Sprite."""
import http.client
import logging
import re
import socket

from engine import Engine


class TaskConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect("/.sprite/api.sock")


def hold(method, job):
    if not re.fullmatch("[0-9a-f]{32}", job):
        raise ValueError("Invalid internal job ID")
    conn = TaskConnection("sprite", timeout=2)
    try:
        conn.request(method, "/v1/tasks/night-shift-" + job,
                     b'{"expire":"2m"}' if method == "PUT" else None,
                     {"Content-Type": "application/json"})
        status = conn.getresponse().status
        expected = (200,) if method == "PUT" else (204, 404)
        if status not in expected:
            raise RuntimeError(f"Sprite task {method} returned HTTP {status}")
    except (OSError, http.client.HTTPException) as exc:
        raise RuntimeError("Sprite task socket unavailable") from exc
    finally:
        conn.close()


def release(job):
    try:
        hold("DELETE", job)
    except RuntimeError:
        logging.warning("Sprite task cleanup deferred to its two-minute expiry")


class SpriteEngine(Engine):
    def submit(self, assignment, files):
        # The worker cannot claim a queued row until its admission hold is settled.
        with self.lock:
            job = super().submit(assignment, files)
            try:
                hold("PUT", job)
            except RuntimeError:
                with self.db() as db:
                    self.change(db, job, "FAILED", "Could not acquire the Sprite task hold.")
                release(job)
            return job

    def run(self, row):
        job = row["id"]
        try:
            # Refresh after queue time, including jobs recovered after a cold start.
            hold("PUT", job)
            super().run(row)
        finally:
            release(job)

    def cancel(self, job):
        with self.lock:
            queued = self.get(job)["state"] == "QUEUED"
            super().cancel(job)
            if queued:
                release(job)
