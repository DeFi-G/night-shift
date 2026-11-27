
import http.client
import json
import logging
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit
from datetime import datetime, timezone

CREDENTIAL = Path("/home/sprite/night-shift-private/discord-webhook")

MESSAGES = {
    "CLOCKED_IN": (
        "SHIFT STARTED",
        "Night Shift has clocked in. Your assignment is being processed.",
        10181046
    ),
    "COMPLETED": (
        "SHIFT COMPLETE",
        "Your verified report is ready for review.",
        5763719
    ),
    "FAILED": (
        "SHIFT FAILED",
        "Return to Night Shift to review the assignment status.",
        15548997
    ),
    "INTERRUPTED": (
        "SHIFT INTERRUPTED",
        "The worker was interrupted. Review the assignment status.",
        16753920
    )
}


def now():
    return datetime.now(timezone.utc).isoformat()


def payload(job, state, mode):
    if not re.fullmatch(r"[0-9a-f]{32}", job):
        raise ValueError("Invalid job identifier")

    if state not in MESSAGES or mode not in ("mock", "ollama"):
        raise ValueError("Invalid notification metadata")

    title, description, color = MESSAGES[state]

    return {
        "username": "Night Shift",
        "allowed_mentions": {"parse": []},
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "fields": [
                {"name": "Job", "value": job[:12], "inline": True},
                {"name": "Mode", "value": mode, "inline": True}
            ],
            "footer": {"text": "Night Shift | DeFi Network"},
            "timestamp": now()
        }]
    }


def deliver(message):
    url = CREDENTIAL.read_text(encoding="ascii").strip()

    if not re.fullmatch(
        r"https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+",
        url
    ):
        raise ValueError("Invalid webhook configuration")

    path = urlsplit(url).path
    body = json.dumps(message).encode("utf-8")

    conn = http.client.HTTPSConnection("discord.com", timeout=3)

    try:
        conn.request(
            "POST",
            path + "?wait=true",
            body,
            {"Content-Type": "application/json",
             "User-Agent": "NightShift/1"}
        )

        response = conn.getresponse()
        return response.status
    finally:
        conn.close()


class Notifier:
    def __init__(self, root, sender=deliver):
        self.path = Path(root) / "notifications.sqlite3"
        self.sender = sender

        with sqlite3.connect(self.path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS notifications(
                    job TEXT NOT NULL,
                    state TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created TEXT NOT NULL,
                    finished TEXT,
                    http_status INTEGER,
                    PRIMARY KEY(job, state)
                )
            """)

    def notify(self, job, state, mode):
        try:
            return self._notify(job, state, mode)
        except Exception:
            logging.warning("Night Shift notification unavailable")
            return "UNAVAILABLE"

    def _notify(self, job, state, mode):
        message = payload(job, state, mode)

        with sqlite3.connect(self.path) as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO notifications "
                "(job,state,status,created) VALUES(?,?,?,?)",
                (job, state, "ATTEMPTING", now())
            )

            if cursor.rowcount != 1:
                return "DUPLICATE_SKIPPED"

        http_status = None

        try:
            http_status = self.sender(message)
            status = (
                "DELIVERED"
                if http_status in (200, 204)
                else "REJECTED"
            )
        except Exception:
            status = "DELIVERY_UNKNOWN"

        with sqlite3.connect(self.path) as db:
            db.execute(
                "UPDATE notifications "
                "SET status=?,finished=?,http_status=? "
                "WHERE job=? AND state=?",
                (status, now(), http_status, job, state)
            )

        return status
