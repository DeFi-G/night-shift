
"""Persistent conservative inference accounting."""
import sqlite3
import time
import json
from pathlib import Path
from contextlib import contextmanager, closing

MODEL = "gpt-oss:20b"

MAX_INPUT = 8192
MAX_OUTPUT = 512
MAX_MESSAGE_BYTES = 8192

# Provisional rates expressed in billionths of a dollar.
INPUT_RATE = 150
OUTPUT_RATE = 600

BUDGET = 7_680_000

RESERVATION = (
    MAX_INPUT * INPUT_RATE
    + MAX_OUTPUT * OUTPUT_RATE
)

class Ledger:
    def __init__(self, root):
        self.root = Path(root).resolve()

        if not self.root.is_dir():
            raise RuntimeError("Ledger directory unavailable")

        self.path = self.root / "inference.sqlite3"

        if not self.path.is_file():
            raise RuntimeError("Ledger not initialized")

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=5)

        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @classmethod
    def initialize(cls, root):
        root = Path(root)
        root.mkdir(mode=0o700, parents=False, exist_ok=False)

        path = root / "inference.sqlite3"

        with closing(sqlite3.connect(path)) as db, db:
            db.execute("PRAGMA synchronous=FULL")

            db.execute("""
                CREATE TABLE requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reserved INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    created REAL NOT NULL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    actual INTEGER,
                    completed REAL
                )
            """)

            db.execute("""
                CREATE TABLE controls (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    disabled INTEGER NOT NULL
                )
            """)

            db.execute("INSERT INTO controls VALUES(1,0)")

        path.chmod(0o600)
        return cls(root)

    def reserve(self, messages, model):
        if model != MODEL:
            raise RuntimeError("Unapproved model")

        if len(json.dumps(
            messages, ensure_ascii=True
        ).encode()) > MAX_MESSAGE_BYTES:
            raise RuntimeError("Inference context exceeds limit")

        with self.db() as db:
            if (self.root / "disabled").exists():
                raise RuntimeError("Live inference disabled")

            control = db.execute(
                "SELECT disabled FROM controls WHERE id=1"
            ).fetchone()

            if control != (0,):
                raise RuntimeError("Live inference disabled")

            pending = db.execute(
                "SELECT count(*) FROM requests "
                "WHERE state='RESERVED'"
            ).fetchone()[0]

            if pending:
                raise RuntimeError("Unresolved inference reservation")

            committed = db.execute(
                "SELECT coalesce(sum(reserved),0) FROM requests"
            ).fetchone()[0]

            if committed + RESERVATION > BUDGET:
                raise RuntimeError("Persistent inference budget exhausted")

            cursor = db.execute(
                "INSERT INTO requests(reserved,state,created) "
                "VALUES(?,?,?)",
                (RESERVATION, "RESERVED", time.time())
            )

            return cursor.lastrowid

    def receipt(self, ticket, result):
        incoming = result.get("prompt_eval_count")
        outgoing = result.get("eval_count")

        if (
            result.get("model") != MODEL
            or result.get("done") is not True
            or any(
                type(n) is not int or n < 0
                for n in (incoming, outgoing)
            )
        ):
            raise RuntimeError("Invalid inference receipt")

        actual = (
            incoming * INPUT_RATE
            + outgoing * OUTPUT_RATE
        )

        exceeded = (
            incoming > MAX_INPUT
            or outgoing > MAX_OUTPUT
        )

        with self.db() as db:
            cursor = db.execute(
                "UPDATE requests SET state=?,input_tokens=?,"
                "output_tokens=?,actual=?,completed=? "
                "WHERE id=? AND state='RESERVED'",
                (
                    "EXCEEDED" if exceeded else "SETTLED",
                    incoming, outgoing, actual,
                    time.time(), ticket
                )
            )

            if cursor.rowcount != 1:
                raise RuntimeError("Invalid reservation settlement")

            if exceeded:
                db.execute(
                    "UPDATE controls SET disabled=1 WHERE id=1"
                )

        if exceeded:
            raise RuntimeError("Provider exceeded token limits")

    def status(self):
        with self.db() as db:
            row = db.execute("""
                SELECT count(*),
                    coalesce(sum(reserved),0),
                    coalesce(sum(actual),0),
                    coalesce(sum(input_tokens),0),
                    coalesce(sum(output_tokens),0),
                    coalesce(sum(state='RESERVED'),0)
                FROM requests
            """).fetchone()

            disabled = db.execute(
                "SELECT disabled FROM controls WHERE id=1"
            ).fetchone()[0]

        return {
            "requests": row[0],
            "reserved_usd": row[1] / 1_000_000_000,
            "estimated_actual_usd": row[2] / 1_000_000_000,
            "input_tokens": row[3],
            "output_tokens": row[4],
            "unresolved": row[5],
            "disabled": bool(disabled)
                or (self.root / "disabled").exists(),
            "budget_usd": BUDGET / 1_000_000_000
        }
