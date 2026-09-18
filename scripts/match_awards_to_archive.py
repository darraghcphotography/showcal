"""Check our award rows against the official lists harvested from aims.ie.

`docs/collapsed-societies.md` explains the problem: some award rows are filed
under a society that did not stage the show, because two societies were merged
into one name before the data reached us. The structural test (two sections in
one season) finds the suspects; it cannot say which rows belong to whom.

The harvested pre-Wix aims.ie can, because AIMS published the nominations by
section with the society printed beside each nominee. This script takes a
society's rows, looks each nominee up in the harvested text, and reports the
society name the official page prints alongside.

    py scripts/match_awards_to_archive.py --society "Clara Musical Society"
    py scripts/match_awards_to_archive.py --all-collapsed

It reports, it does not write. Every line it prints names the capture and the
URL it came from, so a claim can be read back against the source before anyone
touches an award row. "show too" means the row's show title also appears
between the nominee and the society - three points matching, not one - which is
the difference between an attribution and a name that happens to be nearby.
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "aims.db"
DEFAULT_HARVEST = ROOT / "archive_harvest" / "text"

COLLAPSED = [
    "Clara Musical Society",
    "Athlone Musical Society",
    "Tralee Musical Society",
    "Avonmore Musical Society",
    "Kilcock Musical & Dramatic Society",
    "UCC Musical Theatre Society",
    "Twin Productions",
]

# The suffixes Irish musical societies actually use. A name is only usable here
# if we can recognise where it ends.
SOCIETY_SUFFIX = (
    r"(?:Musical|Mus|Choral|Operatic|Drama|Dramatic|Variety|Theatre|Stage|Music)?\s*"
    r"(?:&|and)?\s*"
    r"(?:Musical|Choral|Operatic|Dramatic|Theatre|Variety)?\s*"
    r"(?:Society|Group|Productions|Company|Players|Guild|Association|Singers|Team|Limited|Ltd)"
)
SOCIETY_RE = re.compile(
    r"\b([A-Z][\w'’.\-]*(?:\s+(?:of|the|na|on|Na|[A-Z][\w'’.\-]*)){0,4}"
    r"\s+" + SOCIETY_SUFFIX + r"(?:,\s*[A-Z][\w'’.\-]+)?)"
)

# How far after a nominee's name the official page prints their society. These
# are (nominee, role, show, society) rows flattened onto one line, so the
# society follows closely; a wider window just picks up the neighbouring rows.
WINDOW = 160

DESCRIPTOR_WORD = re.compile(
    r"(?:Musical|Mus|Choral|Operatic|Drama|Dramatic|Variety|Theatre|Stage|Music|"
    r"The|And|&|Society|Group|Company|Productions|Players)", re.I)

NOISE_WORDS = re.compile(
    r"\b(musical|dramatic|drama|and|the|society|group|company|productions|"
    r"choral|operatic|mus|theatre|variety|players|ltd|limited)\b"
)


def load_pages(harvest_dir):
    """Every harvested page as (filename, source, capture, flattened text).

    The text is flattened to single spaces because the official pages are
    two-column tables: a society name is routinely split across three lines,
    and a nominee is separated from their society by the row's other cells.
    """
    pages = []
    for path in sorted(Path(harvest_dir).glob("*.txt")):
        raw = path.read_text(encoding="utf-8", errors="replace")
        source = capture = ""
        for line in raw.splitlines()[:4]:
            if line.startswith("# source: "):
                source = line[len("# source: "):]
            elif line.startswith("# captured: "):
                capture = line[len("# captured: "):]
        pages.append((path.name, source, capture, re.sub(r"\s+", " ", raw)))
    return pages


def normalise(name):
    """A society name reduced to the part that identifies it.

    "Clara Mus Society" and "Clara Musical Society" are the same society; the
    old site spelled it both ways in the same season.
    """
    name = re.sub(r"\s+", " ", (name or "")).strip().lower()
    name = name.replace("&", "and").replace(".", "")
    return re.sub(r"\s+", " ", NOISE_WORDS.sub(" ", name)).strip()


def title_words(title):
    title = re.sub(r"[^a-z0-9 ]", " ", (title or "").lower())
    return [w for w in title.split() if w not in ("the", "a", "an", "of", "and")]


def shortest_name(candidate):
    """Trim the row's other cells off the front of a matched society name.

    The pattern allows a few capitalised words before the suffix, because
    "St. Mary's Choral Society, Clonmel" needs them - but on a flattened row it
    also swallows the show title, giving "Hot Mikado Clane Musical Society".
    Drop leading words while what is left still reads as a society name.
    """
    words = candidate.split()
    # Shortest first, but a name has to start with something that identifies
    # it: trimming all the way down leaves the bare descriptor "Musical
    # Society", which names no one.
    for start in range(len(words) - 1, -1, -1):
        if DESCRIPTOR_WORD.fullmatch(words[start]):
            continue
        tail = " ".join(words[start:])
        if SOCIETY_RE.fullmatch(tail):
            return tail
    return candidate


def attribution(body, start, end, show):
    """The societies printed either side of a nominee, as a list.

    It deliberately does not choose between them. These pages are table rows
    flattened to one line and they do not agree on column order: the 2001
    nominations print nominee, show, society, while the 2003 results print the
    society first. So the nearest name in one direction is the row's own
    society and in the other it is the neighbouring row's, and nothing local
    says which is which - picking by distance just produces a confident wrong
    answer, which is the one outcome this exercise cannot afford.

    What settles it is repetition: the real society recurs across rows, seasons
    and pages, and a neighbouring-row name does not. So both are returned, and
    the caller tallies.
    """
    after = body[end:end + WINDOW]
    before = body[max(0, start - WINDOW):start]
    words = title_words(show)
    candidates = []

    match = SOCIETY_RE.search(after)
    if match:
        # Up to where the *name* starts, not where the match does - the match
        # swallows the show title, so measuring to it leaves nothing between
        # and no row ever looked like a three-point match.
        trimmed = shortest_name(match.group(1))
        name_at = match.start() + len(match.group(1)) - len(trimmed)
        between = after[:name_at].lower()
        candidates.append((trimmed, bool(words) and all(w in between for w in words)))

    nearest = None
    for match in SOCIETY_RE.finditer(before):
        nearest = match
    if nearest:
        between = before[nearest.end():].lower()
        candidates.append((shortest_name(nearest.group(1)),
                           bool(words) and all(w in between for w in words)))
    return candidates


def attributions_for(pages, nominee, show):
    """Every distinct society the harvest prints beside this nominee."""
    pattern = re.compile(re.escape(nominee), re.I)
    found = {}
    for _filename, source, capture, body in pages:
        for match in pattern.finditer(body):
            for candidate, confirmed in attribution(body, match.start(),
                                                    match.end(), show):
                key = normalise(candidate)
                previous = found.get(key)
                if previous is None or (confirmed and not previous[1]):
                    found[key] = (candidate, confirmed, capture, source)
    return found


def report(db, pages, society_name, first_year, last_year, log=print):
    row = db.execute("SELECT id, name FROM societies WHERE name = ?",
                     (society_name,)).fetchone()
    if row is None:
        row = db.execute("SELECT id, name FROM societies WHERE name LIKE ?",
                         (society_name + "%",)).fetchone()
    if row is None:
        log("No society matching {!r}".format(society_name))
        return
    society_id, name = row["id"], row["name"]
    log("")
    log(name)
    log("=" * len(name))

    rows = db.execute(
        """SELECT year, tier, category_name, show, nominee_name
           FROM historical_results
           WHERE society_id = ? AND year BETWEEN ? AND ?
             AND nominee_name IS NOT NULL AND TRIM(nominee_name) <> ''
           ORDER BY year, tier, category_name""",
        (society_id, first_year, last_year)).fetchall()

    ours = normalise(name)
    for award in rows:
        found = attributions_for(pages, award["nominee_name"], award["show"])
        confirmed = {k: v for k, v in found.items() if v[1]}
        shown = confirmed or found
        log("")
        log("  {} {} - {} - {} ({})".format(
            award["year"], award["tier"] or "-", award["category_name"],
            award["nominee_name"], award["show"] or "?"))
        if not shown:
            log("      not found in the harvest")
            continue
        for key, (candidate, matched_show, capture, source) in sorted(
                shown.items(), key=lambda kv: (not kv[1][1], kv[0])):
            log("      {:9} {:9} {:<38} {}  {}".format(
                "OURS" if key == ours else "DIFFERENT",
                "show too" if matched_show else "name only",
                candidate[:38], capture, source.replace("http://", "")))


def summarise(db, pages, society_name, first_year, last_year, log=print):
    """One line per season and section: who the official lists actually name.

    This is the shape the question is really asked in. A collapsed society's
    rows split by section, and it is the section - not the individual row -
    that belongs to one body or the other.
    """
    row = db.execute("SELECT id, name FROM societies WHERE name = ?",
                     (society_name,)).fetchone()
    if row is None:
        row = db.execute("SELECT id, name FROM societies WHERE name LIKE ?",
                         (society_name + "%",)).fetchone()
    if row is None:
        log("No society matching {!r}".format(society_name))
        return
    society_id, name = row["id"], row["name"]
    ours = normalise(name)

    rows = db.execute(
        """SELECT year, tier, show, nominee_name
           FROM historical_results
           WHERE society_id = ? AND year BETWEEN ? AND ?
             AND nominee_name IS NOT NULL AND TRIM(nominee_name) <> ''
           ORDER BY year, tier""",
        (society_id, first_year, last_year)).fetchall()

    groups = {}
    for award in rows:
        groups.setdefault((award["year"], award["tier"] or "-"),
                          {"shows": set(), "names": {}, "rows": 0})
        group = groups[(award["year"], award["tier"] or "-")]
        group["rows"] += 1
        group["shows"].add(award["show"] or "?")
        for key, (candidate, matched_show, _capture, _source) in attributions_for(
                pages, award["nominee_name"], award["show"]).items():
            # Only a three-point match votes. A bare name match is a person
            # with a common name appearing somewhere else on the site.
            if matched_show:
                tally = group["names"].setdefault(key, [candidate, 0])
                tally[1] += 1

    log("")
    log(name)
    log("=" * len(name))
    for (year, tier), group in sorted(groups.items()):
        votes = sorted(group["names"].values(), key=lambda v: -v[1])
        if not votes:
            verdict = "no three-point match in the harvest"
        else:
            top = votes[0]
            verdict = "{} ({} of {} rows){}".format(
                "OURS" if normalise(top[0]) == ours else top[0].upper(),
                top[1], group["rows"],
                "" if len(votes) == 1 else " - also " + ", ".join(
                    "{} x{}".format(v[0], v[1]) for v in votes[1:]))
        log("  {} {:<9} {:<34} {}".format(
            year, tier, ", ".join(sorted(group["shows"]))[:34], verdict))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--harvest", default=str(DEFAULT_HARVEST))
    parser.add_argument("--society", action="append", default=[],
                        help="society name (repeatable)")
    parser.add_argument("--all-collapsed", action="store_true",
                        help="the seven societies the tier test flags")
    parser.add_argument("--from-year", type=int, default=2001)
    parser.add_argument("--to-year", type=int, default=2010)
    parser.add_argument("--summary", action="store_true",
                        help="one line per season and section instead of per row")
    args = parser.parse_args(argv)

    names = list(args.society) or COLLAPSED
    if args.all_collapsed:
        names = COLLAPSED

    harvest = Path(args.harvest)
    if not harvest.exists():
        print("No harvest at {} - run scripts/harvest_aims_archive.py first.".format(harvest))
        return 2

    pages = load_pages(harvest)
    print("{} harvested pages".format(len(pages)))

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    for name in names:
        if args.summary:
            summarise(db, pages, name, args.from_year, args.to_year)
        else:
            report(db, pages, name, args.from_year, args.to_year)
    return 0


if __name__ == "__main__":
    sys.exit(main())
