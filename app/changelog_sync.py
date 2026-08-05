"""Publish CHANGELOG.md (git-tracked, one entry per '---'-separated block)
into changelog_entries automatically on app startup - so shipping a round
of work means writing it into the file once, not logging in and pasting it
into /admin/changelog by hand every redeploy.

See schema.sql's changelog_synced_entries for why a manually-deleted entry
never comes back: sync only checks "has this exact text ever been synced
before," not "is it still present" - deleting it from /admin/changelog is
final, same as today, it just won't be re-published from the file.
"""
import re
from pathlib import Path

ENTRY_SEPARATOR = re.compile(r"(?m)^-{3,}\s*$")


def parse_entries(text):
    entries = []
    for block in ENTRY_SEPARATOR.split(text):
        lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
        if lines:
            entries.append("\n".join(lines))
    return entries


def sync(conn, changelog_path):
    """Insert any entry from `changelog_path` not already synced. Returns
    how many were newly published."""
    path = Path(changelog_path)
    if not path.exists():
        return 0

    published = 0
    for entry in parse_entries(path.read_text(encoding="utf-8")):
        already_synced = conn.execute(
            "SELECT 1 FROM changelog_synced_entries WHERE entry = ?", (entry,)
        ).fetchone()
        if already_synced:
            continue
        conn.execute("INSERT INTO changelog_entries (entry) VALUES (?)", (entry,))
        conn.execute("INSERT INTO changelog_synced_entries (entry) VALUES (?)", (entry,))
        published += 1

    if published:
        conn.commit()
    return published
