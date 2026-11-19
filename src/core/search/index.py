import sqlite3
from pathlib import Path
from typing import Any

from core.storage.blob_store import BlobStore


def _match_query(raw: str) -> str:
    terms = [term for term in raw.replace('"', " ").split() if term]
    if not terms:
        return ""
    return " AND ".join(f'"{term}"*' for term in terms)


class SearchIndex:
    def __init__(self, path: Path, blobs: BlobStore) -> None:
        self._path = path
        self._blobs = blobs
        self._ensure()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    space TEXT NOT NULL,
                    path TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    UNIQUE(space, path)
                )
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
                USING fts5(doc_id UNINDEXED, space UNINDEXED, path UNINDEXED, content)
                """
            )

    def _put(
        self,
        conn: sqlite3.Connection,
        space: str,
        path: str,
        content: str,
        blob: str,
    ) -> None:
        row = conn.execute(
            "SELECT id FROM documents WHERE space = ? AND path = ?",
            (space, path),
        ).fetchone()
        if row is None:
            cursor = conn.execute(
                "INSERT INTO documents(space, path, content, content_hash) VALUES (?, ?, ?, ?)",
                (space, path, content, blob),
            )
            doc_id = int(cursor.lastrowid or 0)
        else:
            doc_id = int(row[0])
            conn.execute(
                "UPDATE documents SET content = ?, content_hash = ? WHERE id = ?",
                (content, blob, doc_id),
            )
            conn.execute("DELETE FROM documents_fts WHERE doc_id = ?", (doc_id,))
        conn.execute(
            "INSERT INTO documents_fts(doc_id, space, path, content) VALUES (?, ?, ?, ?)",
            (doc_id, space, path, content),
        )

    def index_tree(self, space: str, tree: dict[str, str]) -> int:
        count = 0
        with self._connect() as conn:
            for path, blob_hash in tree.items():
                content = self._blobs.read(blob_hash).decode("utf-8", "replace")
                self._put(conn, space, path, content, blob_hash)
                count += 1
        return count

    def search(self, query: str, space: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        match = _match_query(query)
        if not match:
            return []
        sql = (
            "SELECT d.space, d.path, snippet(documents_fts, 3, '[', ']', '...', 20) "
            "FROM documents_fts JOIN documents d ON d.id = documents_fts.doc_id "
            "WHERE documents_fts MATCH ?"
        )
        params: list[Any] = [match]
        if space is not None:
            sql += " AND d.space = ?"
            params.append(space)
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [{"space": row[0], "path": row[1], "snippet": row[2]} for row in rows]

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM documents_fts")
            conn.execute("DELETE FROM documents")

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM documents").fetchone()
        return int(row[0]) if row else 0
