"""Fills `venues.venue_type` by reading the venue's own name.

Irish performance venues almost always say what they are on the tin - "Town
Hall Theatre", "Solstice Arts Centre", "St. Jarlath's College", "Aghada
Community Centre". That makes the venue's own name, which is already ground
truth in this database, a better source than external research: it's
deterministic, re-runnable, auditable line-by-line, and can't invent anything.

This deliberately does NOT use the `venue_type` values in
enrichment/venues_worklist.json. Those came from the same delegated pass whose
coordinate half was found fabricated on 2026-08-25 (OSM way ids that resolve to
a fence, a 404 and an unnamed building), and its categories didn't match the
agreed set anyway - it never once used "Arts Centre" despite a dozen venues
being literally named that. The worklist's values are still on disk if anyone
wants to diff them.

Only ever fills a blank - a moderator's correction via /admin/venue-directory
always wins, and re-running never overwrites one.

RULES are ordered, first match wins, and the order matters:
  * "Arts Centre" before "Theatre", or "Riverbank Arts Centre" reads as a
    theatre on the word "theatre" appearing nowhere in it but "arts" being
    swallowed by a looser rule.
  * "Theatre" before "Hall", or "Town Hall Theatre" (a real theatre) is filed
    as a parish hall on the word "hall".
  * "School or College" before "Hall", or "St. Mary's Secondary School Hall"
    lands as a hall rather than a school.

Usage:
    py classify_venue_types.py [--db aims.db] [--dry-run]

    docker compose exec aims-web python classify_venue_types.py --db /data/aims.db
"""
import argparse
import re
import sqlite3
from pathlib import Path

# Repo root is two levels up since this moved into scripts/<group>/
# (2026-08-29). It was Path(__file__).parent when this lived at the root.
ROOT = Path(__file__).resolve().parents[2]

RULES = [
    ("Arts Centre", r"arts?\s*(centre|center)|\bvisual\b|garter lane|market place"),
    # "dra.ocht" covers every spelling of Draiocht/Draiocht/Draoicht the archive
    # uses - the accent gets dropped inconsistently, and an override keyed on one
    # spelling silently missed production's own (unaccented) version.
    ("Theatre", r"theatre|theater|opera house|playhouse|\bforum\b|concert hall|siamsa|gl[oó]r|dra.ocht"),
    ("School or College", r"school|coll[eè]ge|colái?ste|colaiste|university|campus|aula maxima|"
                          r"comprehensive|\bcbs\b|convent|institute|academy"),
    # No "leisure" here: "Mitchelstown Community Leisure Centre" is a community
    # venue that happens to have a leisure wing, and the community rule below
    # reads it correctly. "church" is likewise a parish hall in this context -
    # a church hall hosting a musical is the parish-hall case, not an "Other".
    ("Other", r"\bgaa\b|sports|arena|big top|marquee"),
    # Deliberately no bare "centre"/"center": that swallowed real arts venues
    # ("The Barbican Centre") and schools ("Coláiste Bríde / IFA Centre") on a
    # word that says nothing about what the building is. Every genuine
    # community centre in the archive also carries the word "community".
    ("Community or Parish Hall", r"community|parish|church|\bhall\b|scout|complex"),
]

# Venues whose name gives nothing away, or gives the wrong answer. Each one is
# a decision, not a guess - noted so a re-reader can check rather than trust.
OVERRIDES = {
    "The Everyman, Cork": "Theatre",                      # Cork's landmark Victorian theatre
    "The Helix, Dublin": "Theatre",                       # DCU's 1,200-seat auditorium
    "The Riverbank": "Arts Centre",                       # The Riverbank Arts Centre, Newbridge
    "St. Pat's DCU": "School or College",                 # DCU St Patrick's Campus
    "The Abbey Clane": "Community or Parish Hall",        # The Abbey Community Centre, Clane
    "The Hub Castlerea": "Community or Parish Hall",      # The Hub Community Centre
    "Draoícht Blanchardstown": "Arts Centre",             # Draíocht, Blanchardstown's arts centre
    "The Barbican Centre, Drogheda": "Arts Centre",       # Drogheda's arts centre and theatre
    "Swift Cultural Centre, Trim": "Arts Centre",         # Trim's arts/cultural venue
    "UCD Astra Hall": "School or College",                # UCD student centre; "UCD" isn't a rule word
}

# Left untyped on purpose. These name no building at all - they're artifacts of
# the archive's free-text venue field (a county, a run description). Giving them
# a type would both assert something false and, because venue_type is a
# CURATED_COLUMN, make them permanent survivors of the venues rebuild's stale
# sweep. See ROADMAP: they need a source-level fix, not a classification.
NEVER_CLASSIFY = {"Cork", "Wexford", "Cork run", "40th Anniversary (March run)",
                  "Dublin Venue (Community/Theatre Stage)"}


def classify(name):
    if name in NEVER_CLASSIFY:
        return None
    if name in OVERRIDES:
        return OVERRIDES[name]
    low = name.lower()
    for label, pattern in RULES:
        if re.search(pattern, low):
            return label
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--dry-run", action="store_true",
                        help="say what would change, then roll back")
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    rows = db.execute("SELECT id, name, venue_type FROM venues ORDER BY name").fetchall()
    set_now, already, unclassified = [], 0, []

    for row in rows:
        if row["venue_type"]:
            already += 1
            continue
        label = classify(row["name"])
        if label is None:
            unclassified.append(row["name"])
            continue
        db.execute("UPDATE venues SET venue_type = ?, updated_at = datetime('now') WHERE id = ?",
                   (label, row["id"]))
        set_now.append((row["name"], label))

    by_type = {}
    for _, label in set_now:
        by_type[label] = by_type.get(label, 0) + 1

    for name, label in set_now:
        print(f"  {label:26s} {name}")
    print(f"\nClassified {len(set_now)}, already set {already}, left blank {len(unclassified)}")
    for label, n in sorted(by_type.items(), key=lambda kv: -kv[1]):
        print(f"  {label:26s} {n}")
    if unclassified:
        print("\nLeft blank (no rule matched, and not an override):")
        for name in unclassified:
            print(f"  {name}")

    if args.dry_run:
        db.rollback()
        print("\n--dry-run: rolled back, nothing written")
    else:
        db.commit()
        print(f"\nCommitted {len(set_now)} classifications")
    db.close()


if __name__ == "__main__":
    main()
