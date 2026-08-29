"""Person identity, internal only: saying that two spellings are one human.

The same person is in this database several times over - as an award nominee,
as a show credit a society typed in, with and without an honorific, with and
without a fada. `/admin/backfill-credits` keeps adding free-text names, so the
problem grows on its own.

**Nothing here is public.** There are no person pages and no public route; the
question of whether to build them was asked and answered separately, and this
does not reopen it. What it gives a moderator is the ability to record "these
are the same person" once, so the answer survives.

**Nothing is rewritten either.** `historical_results.nominee_name` and the
shows credit columns keep the exact text the programme used, forever - a
`people` row plus its aliases is a join, not an edit. That means a merge here
is always reversible, and the archive never stops saying what it actually said.

Same three-way contract as the venue directory and the duplicate-titles queue:
a suggestion is either confirmed (both spellings join one person), dismissed
(they are different people, remembered so it never comes back), or left alone.
"""
from flask import flash, redirect, render_template, request, url_for

from ...auth import current_user, login_required
from ...clock import utcnow_iso
from ...db import get_db
from ...people import find_candidates, name_parts
from . import bp

# The queue shows a screenful at a time; the count above it is always the true
# total. find_candidates deliberately returns everything - see its docstring on
# why truncating inside the finder makes a counter look permanently stuck.
PEOPLE_DISPLAY_LIMIT = 40

# Every column that holds a person's name as free text. One place, because
# three separate readers of this list is how one of them gets forgotten.
CREDIT_COLUMNS = ("director", "musical_director", "choreographer")


def all_person_names(db):
    """Every distinct name string in the database that names a person."""
    names = {
        r[0]
        for r in db.execute(
            "SELECT DISTINCT nominee_name FROM historical_results "
            "WHERE nominee_name IS NOT NULL AND TRIM(nominee_name) != ''"
        )
    }
    for column in CREDIT_COLUMNS:
        names |= {
            r[0]
            for r in db.execute(
                f"SELECT DISTINCT {column} FROM shows "
                f"WHERE {column} IS NOT NULL AND TRIM({column}) != ''"
            )
        }
    return names


def name_appearances(db, name):
    """How many rows across the database use this exact spelling."""
    total = db.execute(
        "SELECT COUNT(*) FROM historical_results WHERE nominee_name = ?", (name,)
    ).fetchone()[0]
    for column in CREDIT_COLUMNS:
        total += db.execute(
            f"SELECT COUNT(*) FROM shows WHERE {column} = ?", (name,)
        ).fetchone()[0]
    return total


def open_candidates(db):
    """Suggested same-person pairs that are still open.

    A pair is closed once it has been dismissed, or once both spellings are
    already aliases of the same person - otherwise every merge would leave its
    own pair sitting in the queue forever.
    """
    dismissed = {
        (r["name_a"], r["name_b"])
        for r in db.execute("SELECT name_a, name_b FROM dismissed_person_pairs")
    }
    resolved = {
        r["alias"]: r["person_id"]
        for r in db.execute("SELECT alias, person_id FROM person_aliases")
    }
    return [
        c for c in find_candidates(all_person_names(db), dismissed)
        if not (c[0] in resolved and resolved[c[0]] == resolved.get(c[1]))
    ]


@bp.route("/people")
@login_required
def people_queue():
    db = get_db()
    candidates = open_candidates(db)

    # One appearance count per name shown, not per pair - a name in three
    # pairs was otherwise counted three times, and this runs per request.
    shown = candidates[:PEOPLE_DISPLAY_LIMIT]
    counts = {name: name_appearances(db, name) for pair in shown for name in pair[:2]}

    people = db.execute(
        """
        SELECT p.id, p.canonical_name, p.created_by, p.created_at,
               COUNT(a.alias) AS alias_count
          FROM people p
          LEFT JOIN person_aliases a ON a.person_id = p.id
         GROUP BY p.id
         ORDER BY p.canonical_name
        """
    ).fetchall()
    aliases = {}
    for r in db.execute("SELECT person_id, alias FROM person_aliases ORDER BY alias"):
        aliases.setdefault(r["person_id"], []).append(r["alias"])

    return render_template(
        "admin/people.html",
        candidates=shown,
        total_candidates=len(candidates),
        display_limit=PEOPLE_DISPLAY_LIMIT,
        counts=counts,
        people=people,
        aliases=aliases,
    )


def _link(db, canonical, other, username):
    """Put both spellings on one person, creating or reusing as needed.

    Handles the case that makes this fiddly: either name may already belong to
    a person from an earlier merge. Reusing that person (rather than creating a
    second one) is what stops a three-spelling name becoming two half-merged
    records.
    """
    existing = {
        r["alias"]: r["person_id"]
        for r in db.execute(
            "SELECT alias, person_id FROM person_aliases WHERE alias IN (?, ?)",
            (canonical, other),
        )
    }
    person_id = existing.get(canonical) or existing.get(other)

    if person_id is None:
        row = db.execute(
            "SELECT id FROM people WHERE canonical_name = ?", (canonical,)
        ).fetchone()
        if row:
            person_id = row["id"]
        else:
            cur = db.execute(
                "INSERT INTO people (canonical_name, created_by, created_at) VALUES (?, ?, ?)",
                (canonical, username, utcnow_iso()),
            )
            person_id = cur.lastrowid

    for alias in (canonical, other):
        db.execute(
            "INSERT OR IGNORE INTO person_aliases (alias, person_id, added_by, added_at) "
            "VALUES (?, ?, ?, ?)",
            (alias, person_id, username, utcnow_iso()),
        )
    return person_id


@bp.route("/people/merge", methods=("POST",))
@login_required
def merge_people():
    db = get_db()
    canonical = request.form.get("canonical", "").strip()
    other = request.form.get("other", "").strip()

    if not canonical or not other or canonical == other:
        flash("Pick which spelling is the correct one.", "error")
        return redirect(url_for("admin.people_queue"))
    if name_parts(canonical) is None:
        flash(f"{canonical!r} doesn't look like one person's name.", "error")
        return redirect(url_for("admin.people_queue"))

    _link(db, canonical, other, current_user()["username"])
    db.commit()
    flash(f"{other} and {canonical} are now recorded as one person.", "success")
    return redirect(url_for("admin.people_queue"))


@bp.route("/people/dismiss", methods=("POST",))
@login_required
def dismiss_person_pair():
    db = get_db()
    name_a = request.form.get("name_a", "").strip()
    name_b = request.form.get("name_b", "").strip()
    if not name_a or not name_b:
        flash("Nothing to dismiss.", "error")
        return redirect(url_for("admin.people_queue"))

    # Stored sorted so the same pair can't be dismissed twice under two orders.
    first, second = sorted((name_a, name_b))
    db.execute(
        "INSERT OR IGNORE INTO dismissed_person_pairs (name_a, name_b, dismissed_by, dismissed_at) "
        "VALUES (?, ?, ?, ?)",
        (first, second, current_user()["username"], utcnow_iso()),
    )
    db.commit()
    flash(f"{name_a} and {name_b} marked as different people.", "success")
    return redirect(url_for("admin.people_queue"))


@bp.route("/people/<int:person_id>/unlink", methods=("POST",))
@login_required
def unlink_person_alias(person_id):
    """Take one spelling back off a person.

    A merge is a judgement and judgements get made wrong, so it has to be
    undoable. Removing the last alias removes the person too - an identity with
    no spellings attached is not a record of anything.
    """
    db = get_db()
    alias = request.form.get("alias", "").strip()
    db.execute(
        "DELETE FROM person_aliases WHERE person_id = ? AND alias = ?", (person_id, alias)
    )
    remaining = db.execute(
        "SELECT COUNT(*) FROM person_aliases WHERE person_id = ?", (person_id,)
    ).fetchone()[0]
    if remaining == 0:
        db.execute("DELETE FROM people WHERE id = ?", (person_id,))
    db.commit()
    flash(f"{alias} is on its own again.", "success")
    return redirect(url_for("admin.people_queue"))
