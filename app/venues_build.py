"""Keep the venues table in step with the free-text venues in shows.venue.

Same shape as productions_build: derived from a source table, rebuilt on app
start and lazily when the source moves, verified before it's trusted. The
difference is that venues are *partly* authored - a moderator sets the
capacity, corrects the town, merges two spellings - so a rebuild must never
overwrite what a person put there. It only ever:

  * creates a venue for a spelling nobody has seen before,
  * points each shows row at the venue its spelling resolves to,
  * removes a venue that no show refers to any more AND that nobody has
    edited (an edited one is kept; deleting a researched capacity because the
    last show using that spelling was retitled would be a bad trade).

Merging two venues is a moderator action, not something inferred here - see
app/blueprints/admin.py. The auto-merge that would be needed to do it here was
tested against the real archive and wrongly fused the Galway, Ballinasloe and
Claremorris Town Hall Theatres, which are three different buildings.
"""

from collections import Counter, defaultdict

from .venues import normalize_venue, town_from_name, venue_slug


class VenueBuildError(AssertionError):
    pass


# Columns only a person ever fills in. A venue with any of these set survives
# a rebuild even when no show points at it any more - throwing away a
# researched capacity because the last show using that spelling got retitled
# would be a bad trade.
#
# town and region are deliberately NOT here: the seeder derives both (town
# from the name, region from the productions staged there), so treating them
# as evidence of curation would make every venue permanent and nothing would
# ever be cleaned up. They're re-derivable, so losing them costs nothing.
CURATED_COLUMNS = (
    "county", "capacity", "auditorium_type",
    "latitude", "longitude", "website_url", "tech_spec_url", "notes",
)


def _unique_slug(db, name, taken):
    base = venue_slug(name)
    slug = base
    n = 2
    while slug in taken:
        slug = f"{base}-{n}"
        n += 1
    taken.add(slug)
    return slug


def collect(db):
    """Every distinct venue spelling in shows.venue, with the shows using it
    and the regions those shows are in."""
    spellings = {}
    for row in db.execute(
        "SELECT id, venue, region FROM shows WHERE venue IS NOT NULL AND trim(venue) != ''"
    ):
        key = normalize_venue(row["venue"])
        if not key:
            continue
        entry = spellings.setdefault(key, {"raw": Counter(), "show_ids": [], "regions": Counter()})
        entry["raw"][row["venue"].strip()] += 1
        entry["show_ids"].append(row["id"])
        if row["region"]:
            entry["regions"][row["region"]] += 1
    return spellings


def _seed_region(regions):
    """The region a venue is in, read off the productions staged there - a
    show carries its own region snapshot, so this is real evidence rather than
    a guess. NULL on a tie: 19 venues in the live archive have shows in more
    than one region (usually a mis-tagged show, occasionally a genuinely
    ambiguous name like "Astra Hall"), and a coin-flip would be worse than
    leaving it for a person."""
    if not regions:
        return None
    ranked = regions.most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]


def build(db, report=None):
    spellings = collect(db)

    aliases = {
        row["name_key"]: row["venue_id"]
        for row in db.execute("SELECT name_key, venue_id FROM venue_aliases")
    }
    taken_slugs = {row["slug"] for row in db.execute("SELECT slug FROM venues")}

    created = 0
    for key, entry in spellings.items():
        if key in aliases:
            continue
        # The spelling used most often becomes the venue's display name; ties
        # break on the longer one, which is nearly always the more complete
        # ("St. Michael's Theatre, New Ross" over "St Michael's Theatre").
        name = max(entry["raw"].items(), key=lambda kv: (kv[1], len(kv[0])))[0]
        venue_id = db.execute(
            "INSERT INTO venues (name, slug, name_key, town, region) VALUES (?, ?, ?, ?, ?)",
            (name, _unique_slug(db, name, taken_slugs), key,
             town_from_name(name), _seed_region(entry["regions"])),
        ).lastrowid
        db.execute(
            "INSERT INTO venue_aliases (name_key, raw, venue_id) VALUES (?, ?, ?)",
            (key, name, venue_id),
        )
        aliases[key] = venue_id
        created += 1

    # Point every show at the venue its own spelling resolves to. Only rows
    # whose link actually changes are written (shows has no FTS triggers, but
    # this keeps a no-op rebuild a no-op, same as productions_build).
    wanted = {}
    for key, entry in spellings.items():
        venue_id = aliases[key]
        for show_id in entry["show_ids"]:
            wanted[show_id] = venue_id
    current = {r["id"]: r["venue_id"] for r in db.execute("SELECT id, venue_id FROM shows")}
    changed = [(wanted.get(sid), sid) for sid, existing in current.items() if wanted.get(sid) != existing]
    if changed:
        db.executemany("UPDATE shows SET venue_id = ? WHERE id = ?", changed)

    # Drop venues nothing refers to any more - unless a person has put
    # something into them.
    curated = " OR ".join(f"{c} IS NOT NULL" for c in CURATED_COLUMNS)
    stale = [
        row["id"] for row in db.execute(
            f"""
            SELECT id FROM venues
             WHERE NOT EXISTS (SELECT 1 FROM shows WHERE shows.venue_id = venues.id)
               AND NOT ({curated})
            """
        )
    ]
    if stale:
        db.executemany("DELETE FROM venues WHERE id = ?", [(v,) for v in stale])

    verify(db, spellings)
    db.execute("DELETE FROM venues_build_state")
    db.execute("INSERT INTO venues_build_state (id, fingerprint) VALUES (1, ?)", (fingerprint(db),))

    if report:
        linked = db.execute("SELECT COUNT(*) FROM shows WHERE venue_id IS NOT NULL").fetchone()[0]
        total = db.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
        # Counted off shows.venue, not venue_aliases: an alias row is per
        # *normalized* key, so two spellings differing only in punctuation
        # share one alias and would never show up here otherwise.
        merged = db.execute(
            "SELECT COUNT(*) FROM (SELECT venue_id FROM shows WHERE venue_id IS NOT NULL "
            "GROUP BY venue_id HAVING COUNT(DISTINCT venue) > 1)"
        ).fetchone()[0]
        report(f"{total} venues from {len(spellings)} normalized spellings "
               f"({created} new this run, {len(stale)} removed)")
        report(f"  {merged} are recorded under more than one spelling in shows.venue")
        report(f"  {linked} shows linked to a venue")
    return spellings


def verify(db, spellings):
    problems = []

    def check(label, got, want):
        if got != want:
            problems.append(f"{label}: got {got}, expected {want}")

    # Every spelling currently in use must have an alias. Deliberately not an
    # equality check: an alias outlives the spelling that created it, so a
    # moderator's merge decision survives the last show using the losing
    # spelling being retitled and then typed again later. A stale alias costs
    # nothing and is cleaned up automatically when its venue goes (the FK
    # cascades).
    known = {row["name_key"] for row in db.execute("SELECT name_key FROM venue_aliases")}
    check("spellings with no alias", len(set(spellings) - known), 0)
    check(
        "shows with a venue string but no venue_id",
        db.execute(
            "SELECT COUNT(*) FROM shows WHERE venue IS NOT NULL AND trim(venue) != '' AND venue_id IS NULL"
        ).fetchone()[0],
        0,
    )
    check(
        "shows with no venue string but a venue_id",
        db.execute(
            "SELECT COUNT(*) FROM shows WHERE (venue IS NULL OR trim(venue) = '') AND venue_id IS NOT NULL"
        ).fetchone()[0],
        0,
    )
    check(
        "aliases pointing at a missing venue",
        db.execute(
            "SELECT COUNT(*) FROM venue_aliases WHERE venue_id NOT IN (SELECT id FROM venues)"
        ).fetchone()[0],
        0,
    )
    check(
        "shows pointing at a missing venue",
        db.execute(
            "SELECT COUNT(*) FROM shows WHERE venue_id IS NOT NULL AND venue_id NOT IN (SELECT id FROM venues)"
        ).fetchone()[0],
        0,
    )
    # A show's own spelling must resolve to the venue it's linked to - the one
    # way a merge could go wrong and silently move productions to the wrong
    # building.
    mislinked = db.execute(
        """
        SELECT COUNT(*) FROM shows
          JOIN venue_aliases ON venue_aliases.venue_id = shows.venue_id
         WHERE shows.venue_id IS NOT NULL
           AND NOT EXISTS (
               SELECT 1 FROM venue_aliases a
                WHERE a.venue_id = shows.venue_id AND a.name_key = venue_aliases.name_key
           )
        """
    ).fetchone()[0]
    check("shows linked to a venue that doesn't claim their spelling", mislinked, 0)

    if problems:
        raise VenueBuildError("venues rebuild failed verification:\n  - " + "\n  - ".join(problems))


# ---------------------------------------------------------------- staying current

# Cheap change detector, same idea as productions_build's. A venue string can
# only change through a shows row, and every route that edits one bumps
# updated_at.
FINGERPRINT_SQL = """
    SELECT (SELECT COUNT(*) FROM shows) || ':' ||
           (SELECT COALESCE(MAX(id), 0) FROM shows) || ':' ||
           (SELECT COALESCE(MAX(updated_at), '') FROM shows) || ':' ||
           (SELECT COUNT(*) FROM shows WHERE venue IS NOT NULL AND trim(venue) != '') || ':' ||
           (SELECT COALESCE(SUM(LENGTH(venue)), 0) FROM shows)
"""


def fingerprint(db):
    return db.execute(FINGERPRINT_SQL).fetchone()[0]


def mark_stale(db):
    db.execute("DELETE FROM venues_build_state")


def ensure_current(db):
    """Rebuild only if the venue strings have moved. Returns True if it did."""
    stored = db.execute("SELECT fingerprint FROM venues_build_state WHERE id = 1").fetchone()
    if stored is not None and stored["fingerprint"] == fingerprint(db):
        return False
    build(db)
    db.commit()
    return True
