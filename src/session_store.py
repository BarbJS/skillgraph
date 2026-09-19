"""Local persistence for Streamlit conversations, isolated by simulated role."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SessionStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    dify_conversation_id TEXT NOT NULL DEFAULT '',
                    backend TEXT NOT NULL DEFAULT 'dify',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'desenvolvedor'
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    route TEXT NOT NULL DEFAULT '',
                    request_id TEXT NOT NULL DEFAULT '',
                    sources_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
                """
            )
            columns = {row[1] for row in db.execute("PRAGMA table_info(conversations)").fetchall()}
            if "role" not in columns:
                db.execute("ALTER TABLE conversations ADD COLUMN role TEXT NOT NULL DEFAULT 'desenvolvedor'")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_conversation(self, title: str = "Nova conversa", backend: str = "dify", role: str = "desenvolvedor") -> str:
        conversation_id, now = str(uuid.uuid4()), self._now()
        with self._connect() as db:
            db.execute("INSERT INTO conversations (id,title,dify_conversation_id,backend,created_at,updated_at,role) VALUES (?, ?, '', ?, ?, ?, ?)", (conversation_id, title[:80], backend, now, now, role))
        return conversation_id

    def list_conversations(self, role: str | None = None) -> list[dict[str, Any]]:
        where, params = ("WHERE role = ?", (role,)) if role else ("", ())
        with self._connect() as db:
            rows = db.execute(f"SELECT id,title,dify_conversation_id,backend,created_at,updated_at,role FROM conversations {where} ORDER BY datetime(updated_at) DESC, datetime(created_at) DESC, id DESC", params).fetchall()
        return [dict(row) for row in rows]

    def get_conversation(self, conversation_id: str, role: str | None = None) -> dict[str, Any] | None:
        query, params = "SELECT * FROM conversations WHERE id = ?", [conversation_id]
        if role:
            query += " AND role = ?"; params.append(role)
        with self._connect() as db:
            row = db.execute(query, params).fetchone()
        return dict(row) if row else None

    def set_title(self, conversation_id: str, title: str, role: str | None = None) -> None:
        query, params = "UPDATE conversations SET title=?,updated_at=? WHERE id=?", [title[:80], self._now(), conversation_id]
        if role: query += " AND role=?"; params.append(role)
        with self._connect() as db: db.execute(query, params)

    rename_conversation = set_title

    def set_dify_conversation(self, conversation_id: str, dify_id: str, role: str | None = None) -> None:
        query, params = "UPDATE conversations SET dify_conversation_id=?,updated_at=? WHERE id=?", [dify_id, self._now(), conversation_id]
        if role: query += " AND role=?"; params.append(role)
        with self._connect() as db: db.execute(query, params)

    def search_conversations(self, text: str, role: str | None = None) -> list[dict[str, Any]]:
        query = f"%{text.strip()}%"
        clauses = ["(c.title LIKE ? OR m.content LIKE ?)"]
        params: list[Any] = [query, query]
        if role:
            clauses.append("c.role = ?")
            params.append(role)
        with self._connect() as db:
            rows = db.execute(
                "SELECT DISTINCT c.* FROM conversations c LEFT JOIN messages m ON m.conversation_id = c.id WHERE "
                + " AND ".join(clauses)
                + " ORDER BY datetime(c.updated_at) DESC, datetime(c.created_at) DESC, c.id DESC",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def add_message(self, conversation_id: str, role: str, content: str, *, route: str = "", request_id: str = "", sources: list[dict[str, str]] | None = None, conversation_role: str | None = None) -> str:
        if not self.get_conversation(conversation_id, conversation_role):
            raise ValueError("Conversa não encontrada para este perfil.")
        message_id, now = str(uuid.uuid4()), self._now()
        with self._connect() as db:
            db.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (message_id, conversation_id, role, content, route, request_id, json.dumps(sources or [], ensure_ascii=False), now))
            db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id))
        return message_id

    def messages(self, conversation_id: str, role: str | None = None) -> list[dict[str, Any]]:
        if not self.get_conversation(conversation_id, role): return []
        with self._connect() as db:
            rows = db.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at", (conversation_id,)).fetchall()
        result = []
        for row in rows:
            item = dict(row); item["sources"] = json.loads(item.pop("sources_json") or "[]"); result.append(item)
        return result

    def delete_conversation(self, conversation_id: str, role: str | None = None) -> None:
        if not self.get_conversation(conversation_id, role): return
        with self._connect() as db:
            db.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,)); db.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
