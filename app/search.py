"""Shared helpers for querying an FTS5 virtual table for matching rowids.

Terms are joined into a single quoted phrase, not separate quoted terms -
FTS5 requires phrase tokens to appear together and in order, so "april kelly"
only matches text where those words are adjacent, not any document that
happens to contain both "April" and "Kelly" somewhere in unrelated sentences.
Quoting the whole phrase (rather than each term) also sidesteps FTS5's own
query-syntax special characters (AND/OR/NOT/-/* etc.), which a raw user
search string could otherwise trip over. Each token keeps its own trailing
prefix wildcard - FTS5 supports per-token prefixes inside a quoted phrase -
so partial words ("kilk mus") still match ("Kilkenny Musical Society").
"""
import sqlite3


def build_phrase_query(q):
    """Turn a raw search string into an FTS5 phrase-match MATCH argument, or
    None if there are no real search terms."""
    terms = [t for t in q.split() if t]
    if not terms:
        return None
    return '"' + " ".join(t.replace('"', '""') + "*" for t in terms) + '"'


def fts_match_ids(db, table, q):
    """Returns None (not an empty list) if the query couldn't be run at all -
    the caller should fall back to a plain LIKE query in that case. Search
    should never hard-fail just because this optimization couldn't be used."""
    match_query = build_phrase_query(q)
    if match_query is None:
        return None
    try:
        rows = db.execute(f"SELECT rowid FROM {table} WHERE {table} MATCH ?", (match_query,)).fetchall()
    except sqlite3.OperationalError:
        return None
    return [r[0] for r in rows]
