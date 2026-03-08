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
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY,
                name       TEXT
            );
            CREATE TABLE IF NOT EXISTS pairs (
                user_a     INTEGER NOT NULL,
                user_b     INTEGER NOT NULL,
                PRIMARY KEY (user_a, user_b)
            );
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


# ── Users ────────────────────────────────────────────────────

def add_user(user_id: int, name: str):
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO users (id, name) VALUES (?, ?)",
            (user_id, name)
        )


def remove_user(user_id: int):
    with conn() as c:
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        c.execute("DELETE FROM pairs WHERE user_a = ? OR user_b = ?", (user_id, user_id))


def is_allowed(user_id: int) -> bool:
    with conn() as c:
        row = c.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        return row is not None


def get_all_users() -> list:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM users").fetchall()]


# ── Pairs ────────────────────────────────────────────────────

def add_pair(user_a: int, user_b: int):
    """A бачить треки B і навпаки."""
    with conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO pairs (user_a, user_b) VALUES (?, ?)", (user_a, user_b)
        )
        c.execute(
            "INSERT OR IGNORE INTO pairs (user_a, user_b) VALUES (?, ?)", (user_b, user_a)
        )


def remove_pair(user_a: int, user_b: int):
    with conn() as c:
        c.execute(
            "DELETE FROM pairs WHERE (user_a=? AND user_b=?) OR (user_a=? AND user_b=?)",
            (user_a, user_b, user_b, user_a)
        )


def get_visible_users(user_id: int) -> list:
    """Список ID юзерів чиї треки може бачити user_id."""
    with conn() as c:
        rows = c.execute(
            "SELECT user_b FROM pairs WHERE user_a = ?", (user_id,)
        ).fetchall()
        return [r["user_b"] for r in rows]


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
    visible = get_visible_users(user_id)
    if not visible:
        return None
    placeholders = ",".join("?" * len(visible))
    with conn() as c:
        return c.execute(f"""
            SELECT t.id, t.url, t.added_by FROM tracks t
            WHERE t.added_by IN ({placeholders})
              AND t.id NOT IN (SELECT track_id FROM listens WHERE user_id = ?)
            ORDER BY t.added_at ASC
            LIMIT 1
        """, (*visible, user_id)).fetchone()


def get_unlistened_count(user_id: int) -> int:
    visible = get_visible_users(user_id)
    if not visible:
        return 0
    placeholders = ",".join("?" * len(visible))
    with conn() as c:
        row = c.execute(f"""
            SELECT COUNT(*) AS cnt FROM tracks
            WHERE added_by IN ({placeholders})
              AND id NOT IN (SELECT track_id FROM listens WHERE user_id = ?)
        """, (*visible, user_id)).fetchone()
        return row["cnt"]


def get_all_users_except(user_id: int) -> list:
    visible = get_visible_users(user_id)
    return visible


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
        c.execute(
            "INSERT OR IGNORE INTO listens (track_id, user_id) VALUES (?, ?)",
            (track_id, user_id)
        )


# ── Reviews ──────────────────────────────────────────────────

def get_reviews_for_my_tracks(user_id: int) -> list:
    with conn() as c:
        rows = c.execute("""
            SELECT t.url, t.id as track_id,
                   l.reaction, l.review, l.user_id as listener_id, l.listened_at
            FROM listens l
            JOIN tracks t ON t.id = l.track_id
            WHERE t.added_by = ? AND l.user_id != ?
            ORDER BY l.listened_at DESC
        """, (user_id, user_id)).fetchall()
        return [dict(r) for r in rows]


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
        my_listened = c.execute(
            "SELECT COUNT(*) FROM listens WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        return {
            "total": total,
            "listened": listened,
            "likes": likes,
            "dislikes": dislikes,
            "my_listened": my_listened,
        }
