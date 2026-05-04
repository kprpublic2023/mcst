"""SQLite 기반 스냅샷 저장소.

스키마:
  snapshots(org_id, category, platform, handle, captured_at, followers,
            posts_total, posts_30d, posts_90d, last_post_at, avg_views,
            avg_likes, avg_comments, engagement_rate, source, raw_json)
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id          TEXT NOT NULL,
    category        TEXT NOT NULL,
    platform        TEXT NOT NULL,
    handle          TEXT,
    captured_at     TEXT NOT NULL,
    followers       INTEGER,
    posts_total     INTEGER,
    posts_30d       INTEGER,
    posts_90d       INTEGER,
    last_post_at    TEXT,
    avg_views       REAL,
    avg_likes       REAL,
    avg_comments    REAL,
    engagement_rate REAL,
    source          TEXT,
    raw_json        TEXT
);
CREATE INDEX IF NOT EXISTS idx_snapshots_org_platform_time
    ON snapshots(org_id, platform, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_captured_at
    ON snapshots(captured_at DESC);
"""


@dataclass
class Snapshot:
    org_id: str
    category: str
    platform: str
    handle: str = ""
    captured_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    followers: int | None = None
    posts_total: int | None = None
    posts_30d: int | None = None
    posts_90d: int | None = None
    last_post_at: str | None = None
    avg_views: float | None = None
    avg_likes: float | None = None
    avg_comments: float | None = None
    engagement_rate: float | None = None
    source: str = "unknown"  # "api" | "scrape" | "demo"
    raw: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> tuple:
        return (
            self.org_id,
            self.category,
            self.platform,
            self.handle,
            self.captured_at,
            self.followers,
            self.posts_total,
            self.posts_30d,
            self.posts_90d,
            self.last_post_at,
            self.avg_views,
            self.avg_likes,
            self.avg_comments,
            self.engagement_rate,
            self.source,
            json.dumps(self.raw, ensure_ascii=False),
        )


class SnapshotStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def insert_many(self, snapshots: Iterable[Snapshot]) -> int:
        rows = [s.to_row() for s in snapshots]
        if not rows:
            return 0
        with self._conn() as c:
            c.executemany(
                """INSERT INTO snapshots
                   (org_id, category, platform, handle, captured_at, followers,
                    posts_total, posts_30d, posts_90d, last_post_at, avg_views,
                    avg_likes, avg_comments, engagement_rate, source, raw_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
        return len(rows)

    def latest(self) -> list[dict[str, Any]]:
        """기관×플랫폼별 최신 스냅샷."""
        with self._conn() as c:
            cur = c.execute(
                """
                SELECT s.* FROM snapshots s
                JOIN (
                    SELECT org_id, platform, MAX(captured_at) AS max_ts
                    FROM snapshots GROUP BY org_id, platform
                ) m
                ON s.org_id = m.org_id
                   AND s.platform = m.platform
                   AND s.captured_at = m.max_ts
                """
            )
            return [dict(r) for r in cur.fetchall()]

    def history(self, org_id: str | None = None, platform: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM snapshots WHERE 1=1"
        args: list[Any] = []
        if org_id:
            q += " AND org_id = ?"
            args.append(org_id)
        if platform:
            q += " AND platform = ?"
            args.append(platform)
        q += " ORDER BY captured_at ASC"
        with self._conn() as c:
            cur = c.execute(q, args)
            return [dict(r) for r in cur.fetchall()]

    def all(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            cur = c.execute("SELECT * FROM snapshots ORDER BY captured_at ASC")
            return [dict(r) for r in cur.fetchall()]
