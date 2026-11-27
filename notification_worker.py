
import json
import logging
import subprocess
import sys
from pathlib import Path

from engine import ACTIVE, Stopped
from sprite_worker import SpriteEngine, hold, release
from discord_notify import Notifier

HERE = Path(__file__).resolve().parent


def bounded_delivery(message):
    child = (
        "import sys,json;"
        "from discord_notify import deliver;"
        "print(deliver(json.load(sys.stdin)))"
    )

    result = subprocess.run(
        [sys.executable, "-B", "-c", child],
        input=json.dumps(message),
        capture_output=True,
        text=True,
        cwd=HERE,
        timeout=8
    )

    if result.returncode != 0:
        raise RuntimeError("Discord delivery unavailable")

    return int(result.stdout.strip())


class NotificationEngine(SpriteEngine):

    def notify_state(self, job, state, mode):
        try:
            notifier = Notifier(
                self.root,
                sender=bounded_delivery
            )
            return notifier.notify(job, state, mode)
        except Exception:
            logging.warning("Notification unavailable")

    def run(self, row):
        job = row["id"]
        mode = row["mode"]

        try:
            hold("PUT", job)

            self.notify_state(job, "CLOCKED_IN", mode)

            # Refresh the hold after notification delivery.
            hold("PUT", job)

            try:
                super(SpriteEngine, self).run(row)

            except Stopped:
                pass

            except Exception as exc:
                with self.db() as db:
                    state = db.execute(
                        "SELECT state FROM jobs WHERE id=?",
                        (job,)
                    ).fetchone()[0]

                    if state in ACTIVE:
                        message = (
                            str(exc)
                            if isinstance(exc, (TimeoutError, RuntimeError))
                            else type(exc).__name__
                        )
                        self.change(db, job, "FAILED", message[:240])

        except Exception as exc:
            with self.db() as db:
                state = db.execute(
                    "SELECT state FROM jobs WHERE id=?",
                    (job,)
                ).fetchone()[0]

                if state in ACTIVE:
                    self.change(
                        db, job, "FAILED",
                        "Worker execution or task hold failed."
                    )

        finally:
            try:
                state = self.get(job)["state"]

                if state in ("COMPLETED", "FAILED", "INTERRUPTED"):
                    self.notify_state(job, state, mode)

            finally:
                release(job)


    def submit(self, assignment, files):
        job = super().submit(assignment, files)
        record = self.get(job)

        if record["state"] == "FAILED":
            self.notify_state(job, "FAILED", record["mode"])

        return job

    def start(self):
        super().start()

        with self.db() as db:
            interrupted = db.execute(
                "SELECT id,mode FROM jobs WHERE state=?",
                ("INTERRUPTED",)
            ).fetchall()

        for row in interrupted:
            self.notify_state(
                row["id"], "INTERRUPTED", row["mode"]
            )
