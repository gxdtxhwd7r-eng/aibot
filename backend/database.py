"""Small SQLite repository; deliberately isolated for future auth scoping."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
 id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT NOT NULL UNIQUE,
 cm_url TEXT, source_url TEXT, source TEXT, brand TEXT, model TEXT, generation TEXT,
 year TEXT, mileage TEXT, price TEXT, condition TEXT, pts TEXT, owners TEXT,
 seller_type TEXT, seller_name TEXT, city TEXT, description TEXT, published_at TEXT,
 photos TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 analysis_status TEXT NOT NULL DEFAULT 'new' CHECK(analysis_status IN ('new','processing','ready','do_not_contact','error')),
 car TEXT, hook TEXT, message TEXT, reason TEXT,
 manager_status TEXT NOT NULL DEFAULT 'new' CHECK(manager_status IN ('new','contacted','skipped'))
);
CREATE INDEX IF NOT EXISTS ix_leads_created_at ON leads(created_at DESC);
"""

FIELDS = ("external_id", "cm_url", "source_url", "source", "brand", "model", "generation", "year", "mileage", "price", "condition", "pts", "owners", "seller_type", "seller_name", "city", "description", "published_at", "photos")


class LeadRepository:
    def __init__(self, path: str) -> None:
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        return db

    def create(self, row: dict[str, Any]) -> int | None:
        now = datetime.now(timezone.utc).isoformat()
        columns = ",".join(FIELDS) + ",created_at,updated_at"
        placeholders = ",".join("?" for _ in range(len(FIELDS) + 2))
        try:
            with self.connect() as db:
                cursor = db.execute(f"INSERT INTO leads ({columns}) VALUES ({placeholders})", [row.get(k) for k in FIELDS] + [now, now])
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError:
            return None

    def update_analysis(self, lead_id: int, status: str, **values: Any) -> None:
        allowed = {"car", "hook", "message", "reason"}
        values = {key: value for key, value in values.items() if key in allowed}
        values.update(analysis_status=status, updated_at=datetime.now(timezone.utc).isoformat())
        with self.connect() as db:
            db.execute(f"UPDATE leads SET {','.join(f'{key}=?' for key in values)} WHERE id=?", [*values.values(), lead_id])

    def get(self, lead_id: int) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        return dict(row) if row else None

    def list(self, limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM leads ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [dict(row) for row in rows]

    def manager_status(self, lead_id: int, status: str) -> bool:
        with self.connect() as db:
            cursor = db.execute("UPDATE leads SET manager_status=?, updated_at=? WHERE id=?", (status, datetime.now(timezone.utc).isoformat(), lead_id))
            return cursor.rowcount > 0

    def counts(self) -> dict[str, int]:
        with self.connect() as db:
            rows = db.execute("SELECT analysis_status, count(*) count FROM leads GROUP BY analysis_status").fetchall()
        result = {key: 0 for key in ("new", "processing", "ready", "do_not_contact", "error")}
        result.update({row["analysis_status"]: row["count"] for row in rows})
        return result
