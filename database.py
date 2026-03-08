import sqlite3
from contextlib import contextmanager
from config import DB_PATH


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db():
    with conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS tracks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                url        TEXT NOT NULL,
                added_by   INTEGER NOT NULL,
                added_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS listens (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id    INTEGER NOT NULL REFERENCES tracks(id),
                user_id     INTEGER NOT NULL,
                reaction    TEXT,
                review      TEXT,
                listened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(track_id, user_id)
            );
        """)


# ── Tracks ───────────────────────────────────────────────────

def add_track(url: str, added_by: int) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO tracks (url, added_by) VALUES (?, ?)", (url, added_by)
        )
        return cur.lastrowid


def get_track_by_id(track_id: int):
    with conn() as c:
        return c.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()


def get_next_unlistened(user_id: int):
    """Oldest track added by someone else that user hasn't listened yet."""
    with conn() as c:
        return c.execute("""
            SELECT t.id, t.url, t.added_by FROM tracks t
            WHERE t.added_by != ?
              AND t.id NOT IN (SELECT track_id FROM listens WHERE user_id = ?)
            ORDER BY t.added_at ASC
            LIMIT 1
        """, (user_id, user_id)).fetchone()


def get_unlistened_count(user_id: int) -> int:
    with conn() as c:
        row = c.execute("""
            SELECT COUNT(*) AS cnt FROM tracks
            WHERE added_by != ?
              AND id NOT IN (SELECT track_id FROM listens WHERE user_id = ?)
        """, (user_id, user_id)).fetchone()
        return row["cnt"]


def get_all_users_except(user_id: int) -> list:
    with conn() as c:
        rows = c.execute(
            "SELECT DISTINCT added_by FROM tracks WHERE added_by != ?", (user_id,)
        ).fetchall()
        return [r["added_by"] for r in rows]


# ── Listens ──────────────────────────────────────────────────

def set_reaction(track_id: int, user_id: int, reaction: str):
    with conn() as c:
        c.execute("""
            INSERT INTO listens (track_id, user_id, reaction) VALUES (?, ?, ?)
            ON CONFLICT(track_id, user_id) DO UPDATE SET reaction = excluded.reaction
        """, (track_id, user_id, reaction))


def save_review(track_id: int, user_id: int, review: str):
    with conn() as c:
        c.execute("""
            INSERT INTO listens (track_id, user_id, review) VALUES (?, ?, ?)
            ON CONFLICT(track_id, user_id) DO UPDATE SET review = excluded.review
        """, (track_id, user_id, review))


def mark_listened(track_id: int, user_id: int):
    with conn() as c:
        c.execute("""
            INSERT OR IGNORE INTO listens (track_id, user_id) VALUES (?, ?)
        """, (track_id, user_id))


# ── Stats ────────────────────────────────────────────────────

def get_user_stats(user_id: int) -> dict:
    with conn() as c:
        total = c.execute(
            "SELECT COUNT(*) FROM tracks WHERE added_by = ?", (user_id,)
        ).fetchone()[0]
        listened = c.execute("""
            SELECT COUNT(*) FROM listens l
            JOIN tracks t ON t.id = l.track_id
            WHERE t.added_by = ? AND l.user_id != ?
        """, (user_id, user_id)).fetchone()[0]
        likes = c.execute("""
            SELECT COUNT(*) FROM listens l
            JOIN tracks t ON t.id = l.track_id
            WHERE t.added_by = ? AND l.reaction = 'like'
        """, (user_id,)).fetchone()[0]
        dislikes = c.execute("""
            SELECT COUNT(*) FROM listens l
            JOIN tracks t ON t.id = l.track_id
            WHERE t.added_by = ? AND l.reaction = 'dislike'
        """, (user_id,)).fetchone()[0]
        return {"total": total, "listened": listened, "likes": likes, "dislikes": dislikes}
