"""Local response feedback storage for the SkillGraph MVP."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class FeedbackStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    message_id TEXT PRIMARY KEY,
                    rating INTEGER NOT NULL CHECK (rating IN (-1, 1)),
                    comment TEXT NOT NULL DEFAULT '',
                    route TEXT NOT NULL DEFAULT '',
                    trace_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            columns = {
                row[1] for row in db.execute("PRAGMA table_info(feedback)").fetchall()
            }
            if "trace_id" not in columns:
                db.execute(
                    "ALTER TABLE feedback ADD COLUMN trace_id TEXT NOT NULL DEFAULT ''"
                )

    def get(self, message_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                """
                SELECT message_id, rating, comment, route, trace_id, created_at
                FROM feedback
                WHERE message_id = ?
                """,
                (message_id,),
            ).fetchone()
        if not row:
            return None
        columns = ("message_id", "rating", "comment", "route", "trace_id", "created_at")
        return dict(zip(columns, row, strict=True))

    def save(
        self,
        message_id: str,
        rating: int,
        *,
        route: str = "",
        comment: str = "",
        trace_id: str = "",
    ) -> None:
        if rating not in (-1, 1):
            raise ValueError("rating must be -1 or 1")
        with sqlite3.connect(self.path) as db:
            db.execute(
                """
                INSERT OR REPLACE INTO feedback
                    (message_id, rating, comment, route, trace_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    rating,
                    comment[:500],
                    route,
                    trace_id,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def summary(self) -> dict[str, int | float]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute(
                "SELECT rating, COUNT(*) FROM feedback GROUP BY rating"
            ).fetchall()
        positive = next((count for rating, count in rows if rating == 1), 0)
        negative = next((count for rating, count in rows if rating == -1), 0)
        total = positive + negative
        return {
            "positive": positive,
            "negative": negative,
            "total": total,
            "positive_rate": round(positive / total, 4) if total else 0.0,
        }

    def summary_legacy(self) -> dict[str, int]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute(
                "SELECT rating, COUNT(*) FROM feedback GROUP BY rating"
            ).fetchall()
        positive = next((count for rating, count in rows if rating == 1), 0)
        negative = next((count for rating, count in rows if rating == -1), 0)
        total = positive + negative
        return {
            "positive": positive,
            "negative": negative,
            "total": total,
            "positive_rate": round(positive / total, 4) if total else 0.0,
        }
