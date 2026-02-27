"""
database.py — all schema creation and data access for the PKM app.

Every function follows the same pattern:
  - accepts an open sqlite3.Connection as its first argument
  - does NOT call conn.close() itself — the caller owns the connection lifecycle
  - does call conn.commit() after writes

The one exception is init_db(), which opens and closes its own connection
because it is called once at app startup before any UI is rendered.
"""

import os
import sqlite3

# ─── Connection ───────────────────────────────────────────────────────────────

# Store the database next to this file so it stays inside the project folder.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pkm.db")

# Content types that get seeded into a fresh database.
# Users can add more from the Capture page.
DEFAULT_CONTENT_TYPES = [
    "Article",
    "Book",
    "Fleeting Note",
    "Note / Thought",
    "Podcast",
    "Video",
]


def get_conn() -> sqlite3.Connection:
    """Return a new SQLite connection with row dict access enabled."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ─── Schema ───────────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Create all tables if they don't exist, then seed default content types.
    Safe to call on every app start — uses IF NOT EXISTS everywhere.
    """
    conn = get_conn()

    conn.executescript("""
        -- User-defined content types (Article, Book, Podcast, etc.)
        CREATE TABLE IF NOT EXISTS content_types (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL UNIQUE,
            created_at TEXT    DEFAULT (datetime('now'))
        );

        -- The main library: anything you've read, watched, listened to, or written.
        -- AI fields (ai_summary, ai_insight) are NULL until Phase 2 processing runs.
        -- impact_rating and synthesis_note are filled in by the user in Phase 2.
        CREATE TABLE IF NOT EXISTS items (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            title            TEXT    NOT NULL,
            content_type_id  INTEGER REFERENCES content_types(id),
            url              TEXT,
            body             TEXT,
            impact_rating    INTEGER,           -- 1-5, user-assigned in Phase 2
            synthesis_note   TEXT,             -- user's own synthesis, Phase 2
            ai_summary       TEXT,             -- AI-generated 1-2 sentence summary
            ai_insight       TEXT,             -- AI-extracted actionable insight
            created_at       TEXT    DEFAULT (datetime('now')),
            updated_at       TEXT    DEFAULT (datetime('now'))
        );

        -- Quotes, passages, highlights clipped from items (or standalone).
        -- parent_item_id is nullable: a highlight can float freely or be anchored
        -- to an item. If the parent item is deleted, the highlight survives (SET NULL).
        CREATE TABLE IF NOT EXISTS highlights (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            text            TEXT    NOT NULL,
            source_info     TEXT,             -- e.g. "Atomic Habits, p. 47"
            parent_item_id  INTEGER REFERENCES items(id) ON DELETE SET NULL,
            impact_rating   INTEGER,
            synthesis_note  TEXT,
            ai_summary      TEXT,
            ai_insight      TEXT,
            created_at      TEXT    DEFAULT (datetime('now')),
            updated_at      TEXT    DEFAULT (datetime('now'))
        );

        -- Flat tag vocabulary, shared by both items and highlights.
        CREATE TABLE IF NOT EXISTS tags (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT    NOT NULL UNIQUE   -- always stored lowercase
        );

        -- Many-to-many: items ↔ tags
        CREATE TABLE IF NOT EXISTS item_tags (
            item_id  INTEGER REFERENCES items(id) ON DELETE CASCADE,
            tag_id   INTEGER REFERENCES tags(id)  ON DELETE CASCADE,
            PRIMARY KEY (item_id, tag_id)
        );

        -- Many-to-many: highlights ↔ tags
        CREATE TABLE IF NOT EXISTS highlight_tags (
            highlight_id INTEGER REFERENCES highlights(id) ON DELETE CASCADE,
            tag_id       INTEGER REFERENCES tags(id)       ON DELETE CASCADE,
            PRIMARY KEY (highlight_id, tag_id)
        );

        -- Explicit directional links between items, with a relationship label.
        -- Phase 3 will add UI for creating and browsing these.
        -- e.g. source "contradicts" target, or source "is an example of" target.
        CREATE TABLE IF NOT EXISTS item_links (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id          INTEGER REFERENCES items(id) ON DELETE CASCADE,
            target_id          INTEGER REFERENCES items(id) ON DELETE CASCADE,
            relationship_label TEXT,
            created_at         TEXT DEFAULT (datetime('now'))
        );
    """)

    for name in DEFAULT_CONTENT_TYPES:
        conn.execute(
            "INSERT OR IGNORE INTO content_types (name) VALUES (?)", (name,)
        )

    conn.commit()
    conn.close()


# ─── Tags (internal helpers) ──────────────────────────────────────────────────

def _get_or_create_tag(conn: sqlite3.Connection, name: str) -> int:
    """Return the id of a tag by name, creating it if necessary. Name is lowercased."""
    name = name.strip().lower()
    conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
    return conn.execute(
        "SELECT id FROM tags WHERE name = ?", (name,)
    ).fetchone()["id"]


def _set_item_tags(conn: sqlite3.Connection, item_id: int, tag_names: list) -> None:
    """Replace all tags on an item with the provided list."""
    conn.execute("DELETE FROM item_tags WHERE item_id = ?", (item_id,))
    for name in tag_names:
        if name.strip():
            tag_id = _get_or_create_tag(conn, name)
            conn.execute(
                "INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?, ?)",
                (item_id, tag_id),
            )


def _set_highlight_tags(conn: sqlite3.Connection, highlight_id: int, tag_names: list) -> None:
    """Replace all tags on a highlight with the provided list."""
    conn.execute("DELETE FROM highlight_tags WHERE highlight_id = ?", (highlight_id,))
    for name in tag_names:
        if name.strip():
            tag_id = _get_or_create_tag(conn, name)
            conn.execute(
                "INSERT OR IGNORE INTO highlight_tags (highlight_id, tag_id) VALUES (?, ?)",
                (highlight_id, tag_id),
            )


# ─── Tags (public) ────────────────────────────────────────────────────────────

def get_all_tags(conn: sqlite3.Connection) -> list:
    """Return a sorted list of all tag name strings."""
    rows = conn.execute("SELECT name FROM tags ORDER BY name").fetchall()
    return [r["name"] for r in rows]


def get_item_tags(conn: sqlite3.Connection, item_id: int) -> list:
    """Return sorted list of tag name strings for a single item."""
    rows = conn.execute(
        """
        SELECT t.name FROM tags t
        JOIN item_tags it ON it.tag_id = t.id
        WHERE it.item_id = ?
        ORDER BY t.name
        """,
        (item_id,),
    ).fetchall()
    return [r["name"] for r in rows]


def get_highlight_tags(conn: sqlite3.Connection, highlight_id: int) -> list:
    """Return sorted list of tag name strings for a single highlight."""
    rows = conn.execute(
        """
        SELECT t.name FROM tags t
        JOIN highlight_tags ht ON ht.tag_id = t.id
        WHERE ht.highlight_id = ?
        ORDER BY t.name
        """,
        (highlight_id,),
    ).fetchall()
    return [r["name"] for r in rows]


def get_tags_for_items_batch(conn: sqlite3.Connection, item_ids: list) -> dict:
    """
    Fetch tags for many items in a single query.
    Returns {item_id: [tag_name, ...]} for every id in item_ids.
    """
    if not item_ids:
        return {}
    placeholders = ",".join("?" * len(item_ids))
    rows = conn.execute(
        f"""
        SELECT it.item_id, t.name
        FROM item_tags it
        JOIN tags t ON t.id = it.tag_id
        WHERE it.item_id IN ({placeholders})
        ORDER BY t.name
        """,
        item_ids,
    ).fetchall()
    result: dict = {iid: [] for iid in item_ids}
    for row in rows:
        result[row["item_id"]].append(row["name"])
    return result


def get_tags_for_highlights_batch(conn: sqlite3.Connection, highlight_ids: list) -> dict:
    """
    Fetch tags for many highlights in a single query.
    Returns {highlight_id: [tag_name, ...]} for every id in highlight_ids.
    """
    if not highlight_ids:
        return {}
    placeholders = ",".join("?" * len(highlight_ids))
    rows = conn.execute(
        f"""
        SELECT ht.highlight_id, t.name
        FROM highlight_tags ht
        JOIN tags t ON t.id = ht.tag_id
        WHERE ht.highlight_id IN ({placeholders})
        ORDER BY t.name
        """,
        highlight_ids,
    ).fetchall()
    result: dict = {hid: [] for hid in highlight_ids}
    for row in rows:
        result[row["highlight_id"]].append(row["name"])
    return result


# ─── Content Types ────────────────────────────────────────────────────────────

def get_content_types(conn: sqlite3.Connection) -> list:
    """Return all content type rows, ordered by name."""
    return conn.execute(
        "SELECT id, name FROM content_types ORDER BY name"
    ).fetchall()


def add_content_type(conn: sqlite3.Connection, name: str) -> None:
    """Add a new content type (no-op if it already exists)."""
    conn.execute(
        "INSERT OR IGNORE INTO content_types (name) VALUES (?)", (name.strip(),)
    )
    conn.commit()


# ─── Items ────────────────────────────────────────────────────────────────────

def add_item(
    conn: sqlite3.Connection,
    title: str,
    content_type_id: int,
    url: str = None,
    body: str = None,
    tag_names: list = None,
) -> int:
    """Insert a new item and return its id."""
    cur = conn.execute(
        "INSERT INTO items (title, content_type_id, url, body) VALUES (?, ?, ?, ?)",
        (title.strip(), content_type_id, url or None, body or None),
    )
    item_id = cur.lastrowid
    if tag_names:
        _set_item_tags(conn, item_id, tag_names)
    conn.commit()
    return item_id


def get_items(
    conn: sqlite3.Connection,
    search: str = None,
    content_type_id: int = None,
    tag: str = None,
    limit: int = None,
) -> list:
    """
    Return items with optional filters.
    - search: keyword matched against title and body (case-insensitive LIKE)
    - content_type_id: filter to a specific type
    - tag: filter to items carrying this exact tag name
    - limit: cap the number of results (useful for the home page dashboard)
    """
    sql = """
        SELECT DISTINCT i.*, ct.name AS content_type_name
        FROM items i
        LEFT JOIN content_types ct ON ct.id = i.content_type_id
    """
    params: list = []

    if tag:
        # Join onto the tag tables to filter — must happen before WHERE
        sql += """
            JOIN item_tags it2 ON it2.item_id = i.id
            JOIN tags      t2  ON t2.id = it2.tag_id AND t2.name = ?
        """
        params.append(tag.lower())

    conditions = []
    if search:
        conditions.append("(i.title LIKE ? OR i.body LIKE ?)")
        params += [f"%{search}%", f"%{search}%"]
    if content_type_id:
        conditions.append("i.content_type_id = ?")
        params.append(content_type_id)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY i.created_at DESC"

    if limit:
        sql += f" LIMIT {int(limit)}"

    return conn.execute(sql, params).fetchall()


def get_item(conn: sqlite3.Connection, item_id: int):
    """Return a single item row by id, or None."""
    return conn.execute(
        """
        SELECT i.*, ct.name AS content_type_name
        FROM items i
        LEFT JOIN content_types ct ON ct.id = i.content_type_id
        WHERE i.id = ?
        """,
        (item_id,),
    ).fetchone()


def update_item(
    conn: sqlite3.Connection,
    item_id: int,
    title: str,
    content_type_id: int,
    url: str = None,
    body: str = None,
    tag_names: list = None,
) -> None:
    """Update an existing item's fields and replace its tags."""
    conn.execute(
        """
        UPDATE items
        SET title = ?, content_type_id = ?, url = ?, body = ?,
            updated_at = datetime('now')
        WHERE id = ?
        """,
        (title.strip(), content_type_id, url or None, body or None, item_id),
    )
    if tag_names is not None:
        _set_item_tags(conn, item_id, tag_names)
    conn.commit()


def delete_item(conn: sqlite3.Connection, item_id: int) -> None:
    """Delete an item. Cascades to item_tags and item_links automatically."""
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()


# ─── Highlights ───────────────────────────────────────────────────────────────

def add_highlight(
    conn: sqlite3.Connection,
    text: str,
    source_info: str = None,
    parent_item_id: int = None,
    tag_names: list = None,
) -> int:
    """Insert a new highlight and return its id."""
    cur = conn.execute(
        "INSERT INTO highlights (text, source_info, parent_item_id) VALUES (?, ?, ?)",
        (text.strip(), source_info or None, parent_item_id or None),
    )
    highlight_id = cur.lastrowid
    if tag_names:
        _set_highlight_tags(conn, highlight_id, tag_names)
    conn.commit()
    return highlight_id


def get_highlights(
    conn: sqlite3.Connection,
    search: str = None,
    parent_item_id: int = None,
    tag: str = None,
    limit: int = None,
) -> list:
    """
    Return highlights with optional filters.
    - search: keyword matched against text and source_info
    - parent_item_id: only highlights linked to a specific item
    - tag: filter to highlights carrying this exact tag name
    - limit: cap the number of results
    """
    sql = """
        SELECT DISTINCT h.*, i.title AS parent_item_title
        FROM highlights h
        LEFT JOIN items i ON i.id = h.parent_item_id
    """
    params: list = []

    if tag:
        sql += """
            JOIN highlight_tags ht2 ON ht2.highlight_id = h.id
            JOIN tags           t2  ON t2.id = ht2.tag_id AND t2.name = ?
        """
        params.append(tag.lower())

    conditions = []
    if search:
        conditions.append("(h.text LIKE ? OR h.source_info LIKE ?)")
        params += [f"%{search}%", f"%{search}%"]
    if parent_item_id:
        conditions.append("h.parent_item_id = ?")
        params.append(parent_item_id)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY h.created_at DESC"

    if limit:
        sql += f" LIMIT {int(limit)}"

    return conn.execute(sql, params).fetchall()


def delete_highlight(conn: sqlite3.Connection, highlight_id: int) -> None:
    """Delete a highlight. Cascades to highlight_tags automatically."""
    conn.execute("DELETE FROM highlights WHERE id = ?", (highlight_id,))
    conn.commit()


# ─── Phase 2: AI result storage ──────────────────────────────────────────────

def update_item_ai(
    conn: sqlite3.Connection,
    item_id: int,
    ai_summary: str,
    ai_insight: str,
) -> None:
    """Persist AI-generated summary and actionable insight for an item."""
    conn.execute(
        """
        UPDATE items
        SET ai_summary = ?, ai_insight = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (ai_summary or None, ai_insight or None, item_id),
    )
    conn.commit()


def update_highlight_ai(
    conn: sqlite3.Connection,
    highlight_id: int,
    ai_summary: str,
    ai_insight: str,
) -> None:
    """Persist AI-generated summary and actionable insight for a highlight."""
    conn.execute(
        """
        UPDATE highlights
        SET ai_summary = ?, ai_insight = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (ai_summary or None, ai_insight or None, highlight_id),
    )
    conn.commit()


# ─── Phase 2: User rating and synthesis ───────────────────────────────────────

def update_item_rating(
    conn: sqlite3.Connection,
    item_id: int,
    impact_rating: int,
    synthesis_note: str,
) -> None:
    """Save the user's impact rating (1-5) and synthesis note for an item."""
    conn.execute(
        """
        UPDATE items
        SET impact_rating = ?, synthesis_note = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (impact_rating or None, synthesis_note or None, item_id),
    )
    conn.commit()


def update_highlight_rating(
    conn: sqlite3.Connection,
    highlight_id: int,
    impact_rating: int,
    synthesis_note: str,
) -> None:
    """Save the user's impact rating (1-5) and synthesis note for a highlight."""
    conn.execute(
        """
        UPDATE highlights
        SET impact_rating = ?, synthesis_note = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (impact_rating or None, synthesis_note or None, highlight_id),
    )
    conn.commit()


# ─── Phase 2: Merge (not replace) tags ────────────────────────────────────────
# Used when applying AI-suggested tags — we add to existing tags, not overwrite.

def apply_suggested_tags_to_item(
    conn: sqlite3.Connection,
    item_id: int,
    new_tag_names: list,
) -> None:
    """Add new tags to an item without removing its existing tags."""
    existing = get_item_tags(conn, item_id)
    merged = list(set(existing + [t.strip().lower() for t in new_tag_names if t.strip()]))
    _set_item_tags(conn, item_id, merged)
    conn.commit()


def apply_suggested_tags_to_highlight(
    conn: sqlite3.Connection,
    highlight_id: int,
    new_tag_names: list,
) -> None:
    """Add new tags to a highlight without removing its existing tags."""
    existing = get_highlight_tags(conn, highlight_id)
    merged = list(set(existing + [t.strip().lower() for t in new_tag_names if t.strip()]))
    _set_highlight_tags(conn, highlight_id, merged)
    conn.commit()


# ─── Phase 2: Library context for AI ─────────────────────────────────────────

def get_library_for_ai_context(
    conn: sqlite3.Connection,
    exclude_id: int = None,
) -> list:
    """
    Return a compact list of dicts representing the whole item library,
    suitable for passing to ai.py as context for finding connections.
    Each dict: {id, title, content_type, tags: [...]}
    Excludes the item currently being processed (by exclude_id).
    """
    items = get_items(conn)
    filtered = [i for i in items if i["id"] != exclude_id]
    ids = [i["id"] for i in filtered]
    tags_map = get_tags_for_items_batch(conn, ids)

    return [
        {
            "id": i["id"],
            "title": i["title"],
            "content_type": i["content_type_name"] or "Unknown",
            "tags": tags_map.get(i["id"], []),
        }
        for i in filtered
    ]


# ─── Phase 3: Daily review ────────────────────────────────────────────────────

def get_daily_review_items(
    conn: sqlite3.Connection,
    n: int = 3,
    min_age_days: int = 7,
) -> list:
    """
    Return n random items at least min_age_days old.
    Falls back to any random items if not enough old ones exist.
    """
    rows = conn.execute(
        """
        SELECT i.*, ct.name AS content_type_name
        FROM items i
        LEFT JOIN content_types ct ON ct.id = i.content_type_id
        WHERE date(i.created_at) <= date('now', ?)
        ORDER BY RANDOM()
        LIMIT ?
        """,
        (f"-{min_age_days} days", n),
    ).fetchall()

    if not rows:
        rows = conn.execute(
            """
            SELECT i.*, ct.name AS content_type_name
            FROM items i
            LEFT JOIN content_types ct ON ct.id = i.content_type_id
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (n,),
        ).fetchall()
    return rows


def get_daily_review_highlights(
    conn: sqlite3.Connection,
    n: int = 2,
    min_age_days: int = 7,
) -> list:
    """
    Return n random highlights at least min_age_days old.
    Falls back to any random highlights if not enough old ones exist.
    """
    rows = conn.execute(
        """
        SELECT h.*, i.title AS parent_item_title
        FROM highlights h
        LEFT JOIN items i ON i.id = h.parent_item_id
        WHERE date(h.created_at) <= date('now', ?)
        ORDER BY RANDOM()
        LIMIT ?
        """,
        (f"-{min_age_days} days", n),
    ).fetchall()

    if not rows:
        rows = conn.execute(
            """
            SELECT h.*, i.title AS parent_item_title
            FROM highlights h
            LEFT JOIN items i ON i.id = h.parent_item_id
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (n,),
        ).fetchall()
    return rows


def get_forgotten_items(
    conn: sqlite3.Connection,
    days: int = 30,
    limit: int = 6,
) -> list:
    """
    Items captured at least `days` ago that have never been rated or synthesized.
    "Forgotten" = captured long ago + no engagement signal (rating or synthesis note).
    """
    return conn.execute(
        """
        SELECT i.*, ct.name AS content_type_name
        FROM items i
        LEFT JOIN content_types ct ON ct.id = i.content_type_id
        WHERE date(i.created_at) <= date('now', ?)
          AND i.impact_rating IS NULL
          AND i.synthesis_note IS NULL
        ORDER BY i.created_at ASC
        LIMIT ?
        """,
        (f"-{days} days", limit),
    ).fetchall()


# ─── Phase 3: Related items ────────────────────────────────────────────────────

def get_tag_related_items(
    conn: sqlite3.Connection,
    item_id: int,
    limit: int = 5,
) -> list:
    """
    Items sharing at least one tag with item_id.
    Ordered by number of shared tags (most related first).
    """
    return conn.execute(
        """
        SELECT i.id, i.title, ct.name AS content_type_name,
               COUNT(it.tag_id) AS shared_tags
        FROM items i
        LEFT JOIN content_types ct ON ct.id = i.content_type_id
        JOIN item_tags it ON it.item_id = i.id
        WHERE it.tag_id IN (
            SELECT tag_id FROM item_tags WHERE item_id = ?
        )
        AND i.id != ?
        GROUP BY i.id
        ORDER BY shared_tags DESC
        LIMIT ?
        """,
        (item_id, item_id, limit),
    ).fetchall()


# ─── Phase 3: Manual links ────────────────────────────────────────────────────

def get_item_links(conn: sqlite3.Connection, item_id: int) -> list:
    """
    All links involving item_id (as source or target).
    Each row: id, relationship_label, other_id, other_title, is_outgoing (1/0).
    """
    return conn.execute(
        """
        SELECT
            il.id,
            il.relationship_label,
            CASE WHEN il.source_id = ? THEN il.target_id ELSE il.source_id END AS other_id,
            CASE WHEN il.source_id = ? THEN t.title    ELSE s.title    END AS other_title,
            CASE WHEN il.source_id = ? THEN 1          ELSE 0          END AS is_outgoing
        FROM item_links il
        JOIN items s ON s.id = il.source_id
        JOIN items t ON t.id = il.target_id
        WHERE il.source_id = ? OR il.target_id = ?
        ORDER BY il.created_at DESC
        """,
        (item_id, item_id, item_id, item_id, item_id),
    ).fetchall()


def add_item_link(
    conn: sqlite3.Connection,
    source_id: int,
    target_id: int,
    relationship_label: str,
) -> int:
    """
    Create a directional link from source to target with a relationship label.
    Returns the link id. If a link already exists in either direction between
    these two items, returns the existing id without creating a duplicate.
    """
    existing = conn.execute(
        """
        SELECT id FROM item_links
        WHERE (source_id = ? AND target_id = ?)
           OR (source_id = ? AND target_id = ?)
        """,
        (source_id, target_id, target_id, source_id),
    ).fetchone()
    if existing:
        return existing["id"]

    cur = conn.execute(
        "INSERT INTO item_links (source_id, target_id, relationship_label) VALUES (?, ?, ?)",
        (source_id, target_id, relationship_label.strip()),
    )
    conn.commit()
    return cur.lastrowid


def delete_item_link(conn: sqlite3.Connection, link_id: int) -> None:
    conn.execute("DELETE FROM item_links WHERE id = ?", (link_id,))
    conn.commit()


# ─── Phase 4: Weekly captures ─────────────────────────────────────────────────

def get_weekly_captures(
    conn: sqlite3.Connection,
    days: int = 7,
) -> tuple:
    """
    Return (items, highlights) captured in the last `days` days, newest first.
    Used by the weekly digest page.
    """
    items = conn.execute(
        """
        SELECT i.*, ct.name AS content_type_name
        FROM items i
        LEFT JOIN content_types ct ON ct.id = i.content_type_id
        WHERE date(i.created_at) >= date('now', ?)
        ORDER BY i.created_at DESC
        """,
        (f"-{days} days",),
    ).fetchall()

    highlights = conn.execute(
        """
        SELECT h.*, i.title AS parent_item_title
        FROM highlights h
        LEFT JOIN items i ON i.id = h.parent_item_id
        WHERE date(h.created_at) >= date('now', ?)
        ORDER BY h.created_at DESC
        """,
        (f"-{days} days",),
    ).fetchall()

    return items, highlights


# ─── Graph ────────────────────────────────────────────────────────────────────

def get_graph_data(conn: sqlite3.Connection) -> tuple:
    """
    Return (items, links) for the visual graph page.
    items: list of dicts {id, title, content_type_name}
    links: list of dicts {source_id, target_id, relationship_label}
    """
    items = conn.execute(
        """
        SELECT i.id, i.title, ct.name AS content_type_name
        FROM items i
        LEFT JOIN content_types ct ON ct.id = i.content_type_id
        ORDER BY i.created_at DESC
        """
    ).fetchall()

    links = conn.execute(
        "SELECT source_id, target_id, relationship_label FROM item_links"
    ).fetchall()

    return [dict(r) for r in items], [dict(r) for r in links]


# ─── Stats ────────────────────────────────────────────────────────────────────

def get_stats(conn: sqlite3.Connection) -> dict:
    """Return counts for the home page dashboard."""
    return {
        "items": conn.execute(
            "SELECT COUNT(*) FROM items"
        ).fetchone()[0],
        "highlights": conn.execute(
            "SELECT COUNT(*) FROM highlights"
        ).fetchone()[0],
        "tags": conn.execute(
            "SELECT COUNT(*) FROM tags"
        ).fetchone()[0],
        "links": conn.execute(
            "SELECT COUNT(*) FROM item_links"
        ).fetchone()[0],
    }
