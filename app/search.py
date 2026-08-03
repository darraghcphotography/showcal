"""Shared helper for querying an FTS5 virtual table for matching rowids.

Splits the query into words, treating each as a quoted prefix match (so
"kilk mus" matches "Kilkenny Musical Society") - quoting each term sidesteps
FTS5's own query-syntax special characters (AND/OR/NOT/-/* etc.), which a
raw user search string could otherwise trip over.

Returns None (not an empty list) if the query couldn't be run at all - the
caller should fall back to a plain LIKE query in that case. Search should
never hard-fail just because this optimization couldn't be used.
"""
import sqlite3


def fts_match_ids(db, table, q):
    terms = [t for t in q.split() if t]
    if not terms:
        return None
    match_query = " ".join('"' + t.replace('"', '""') + '"*' for t in terms)
    try:
        rows = db.execute(f"SELECT rowid FROM {table} WHERE {table} MATCH ?", (match_query,)).fetchall()
    except sqlite3.OperationalError:
        return None
    return [r[0] for r in rows]
