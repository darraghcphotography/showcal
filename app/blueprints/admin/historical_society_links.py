"""Queue for linking historical award records to a current society.

~540 rows in historical_results carry a printed society_name that never matched
a societies row on import - but only ~69 *distinct* names, so this works one
name at a time and applies each decision to all of that name's rows at once,
the same tedium-saving idea as historical_reviews' group_needs_society().

Two things make this queue different from the review one, and both shape the UI:

  * **Most names have no answer.** Fuzzy matching finds a candidate for only
    about 9 of the 69; the rest are genuinely defunct societies that will never
    match anything. "No match exists" is therefore the *common* action, not the
    exception, and it's bulk-selectable for that reason.

  * **A wrong link is worse than no link.** Filling in society_id re-keys
    productions (app/productions.py's society_key), so it publishes one
    society's award history on another's public page. distinctive_score is not
    safe to trust blindly here: it scores "Headford Choral Society" against
    "Headford Musical Society" at 1.00, because society_names._ORG_WORDS_RE
    strips 'choral' and 'musical' alike and leaves a bare town name. So nothing
    is ever pre-selected, town-only matches are flagged, and every link is
    reversible.

The decision is stored in historical_society_links keyed on the printed name,
not written only onto the rows - see that table's comment in schema.sql for why
(import_awards.py wipes and reloads every row this queue touches).
"""
from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for

import society_names

from ... import productions_build
from ...auth import current_user, login_required
from ...db import get_db
from . import bp
from .historical_reviews import SOCIETY_MATCH_THRESHOLD, _all_societies, find_society_candidates_batch
from .societies import _match_society_exact

# Names still awaiting a decision: an award row with no society_id, whose
# printed name has no row in historical_society_links yet.
UNDECIDED_WHERE = """
    historical_results.society_name IS NOT NULL
    AND historical_results.society_id IS NULL
    AND NOT EXISTS (
        SELECT 1 FROM historical_society_links
        WHERE historical_society_links.society_name = historical_results.society_name
    )
"""


def undecided_name_count(db):
    """How many distinct printed names still need a decision. Unlike the
    dashboard's existing unmatched_award_societies_count (a *row* count that is
    correctly permanent, since most of these societies are defunct), this one
    can genuinely reach zero - "no match exists" is a real answer that removes a
    name from the queue."""
    return db.execute(
        f"SELECT COUNT(DISTINCT historical_results.society_name) FROM historical_results WHERE {UNDECIDED_WHERE}"
    ).fetchone()[0]


def _town_only(name):
    """True when the distinctive part of a name is a single word - almost always
    a town. A match on that alone ("Headford" vs "Headford") says nothing about
    whether it's the same society, so the queue flags it rather than trusting
    the score."""
    return len(society_names.distinctive_part(name).split()) <= 1


@bp.route("/historical-society-links")
@login_required
def historical_society_links_queue():
    db = get_db()

    rows = db.execute(
        f"""
        SELECT historical_results.society_name AS society_name,
               COUNT(*) AS row_count,
               MIN(historical_results.year) AS first_year,
               MAX(historical_results.year) AS last_year
          FROM historical_results
         WHERE {UNDECIDED_WHERE}
      GROUP BY historical_results.society_name
      ORDER BY row_count DESC, historical_results.society_name
        """
    ).fetchall()

    # ONE batched call for every undecided name - never one per row. The
    # per-row version of this is what took the site down with a 524 when the
    # historical-reviews queue first shipped (see find_society_candidates_batch).
    candidates_by_name = find_society_candidates_batch(db, (r["society_name"] for r in rows))

    entries = []
    for row in rows:
        entry = dict(row)
        # _match_society_exact returns an id, not a row - look up the name so
        # the template can show which society the button would link to.
        exact_id = _match_society_exact(db, row["society_name"])
        exact = db.execute("SELECT id, name FROM societies WHERE id = ?", (exact_id,)).fetchone() \
            if exact_id is not None else None
        entry["exact_match"] = exact
        entry["candidates"] = [
            (name, score, section)
            for name, score, section in candidates_by_name.get(row["society_name"], [])
            if score >= SOCIETY_MATCH_THRESHOLD and (exact is None or name != exact["name"])
        ][:3]
        entry["town_only"] = _town_only(row["society_name"])
        entries.append(entry)

    decided = db.execute(
        """
        SELECT l.*, s.name AS society_name_linked,
               (SELECT COUNT(*) FROM historical_results h WHERE h.society_name = l.society_name) AS row_count
          FROM historical_society_links l
          LEFT JOIN societies s ON s.id = l.society_id
      ORDER BY l.updated_at DESC
        """
    ).fetchall()

    return render_template(
        "admin/historical_society_links.html", entries=entries, decided=decided,
        societies=_all_societies(db),
        total_rows=sum(e["row_count"] for e in entries),
    )


def _record(db, society_name, society_id, no_match, note=None):
    db.execute(
        "INSERT INTO historical_society_links (society_name, society_id, no_match, note, decided_by, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(society_name) DO UPDATE SET society_id = excluded.society_id, "
        "no_match = excluded.no_match, note = excluded.note, decided_by = excluded.decided_by, "
        "updated_at = excluded.updated_at",
        (society_name, society_id, no_match, note, current_user()["username"],
         datetime.utcnow().isoformat()),
    )


@bp.route("/historical-society-links/link", methods=("POST",))
@login_required
def link_historical_society():
    db = get_db()
    society_name = request.form.get("society_name", "").strip()
    if not society_name:
        abort(400)

    # Accepts either an id (the suggestion buttons, which already know it) or a
    # typed name (the manual picker). The name form exists because rendering a
    # 194-option <select> once per queue row made the page 1.5MB - one shared
    # <datalist> plus a text input is the same affordance for ~13KB.
    society_id = request.form.get("society_id", type=int)
    if society_id is not None:
        society = db.execute("SELECT id, name FROM societies WHERE id = ?", (society_id,)).fetchone()
    else:
        typed = request.form.get("society", "").strip()
        society = db.execute("SELECT id, name FROM societies WHERE name = ?", (typed,)).fetchone()
        if society is None and typed:
            flash(f'"{typed}" isn\'t a society on the list - pick one from the suggestions.', "error")
            return redirect(url_for("admin.historical_society_links_queue"))
    if society is None:
        abort(400)

    _record(db, society_name, society["id"], 0)
    # Scoped to rows still unmatched, so this can never re-point a row a
    # moderator already matched by hand via /admin/awards.
    n = db.execute(
        "UPDATE historical_results SET society_id = ? WHERE society_name = ? AND society_id IS NULL",
        (society["id"], society_name),
    ).rowcount
    # An in-place UPDATE moves neither COUNT(*) nor MAX(id), which is all
    # productions_build's freshness fingerprint looks at - so it would never
    # notice this on its own. Same reason admin/awards.py marks stale.
    productions_build.mark_stale(db)
    db.commit()
    flash(f'Linked {n} award record{"" if n == 1 else "s"} printed as "{society_name}" '
          f'to {society["name"]}.', "success")
    return redirect(url_for("admin.historical_society_links_queue"))


@bp.route("/historical-society-links/no-match", methods=("POST",))
@login_required
def mark_no_match():
    """Settles one or more names as "no current society is this one". Touches no
    historical_results row, so no rebuild is needed. Bulk-submittable because
    this is the answer for most of the queue, not the rare one."""
    db = get_db()
    names = [n.strip() for n in request.form.getlist("society_name") if n.strip()]
    if not names:
        flash("Nothing selected.", "warning")
        return redirect(url_for("admin.historical_society_links_queue"))
    for name in names:
        _record(db, name, None, 1)
    db.commit()
    flash(f'Marked {len(names)} name{"" if len(names) == 1 else "s"} as having no current society.',
          "success")
    return redirect(url_for("admin.historical_society_links_queue"))


@bp.route("/historical-society-links/clear", methods=("POST",))
@login_required
def clear_historical_society_link():
    """Undo. Not optional given the stakes: a wrong link publishes one society's
    award history on another society's page, and without this that needs a
    database shell to reverse."""
    db = get_db()
    society_name = request.form.get("society_name", "").strip()
    if not society_name:
        abort(400)
    link = db.execute(
        "SELECT * FROM historical_society_links WHERE society_name = ?", (society_name,)
    ).fetchone()
    if link is None:
        abort(404)

    if link["society_id"] is not None:
        # Only rows pointing at the id this link set - never blanks a row a
        # moderator later pointed somewhere else by hand.
        db.execute(
            "UPDATE historical_results SET society_id = NULL WHERE society_name = ? AND society_id = ?",
            (society_name, link["society_id"]),
        )
        productions_build.mark_stale(db)
    db.execute("DELETE FROM historical_society_links WHERE society_name = ?", (society_name,))
    db.commit()
    flash(f'Undone - "{society_name}" is back in the queue.', "success")
    return redirect(url_for("admin.historical_society_links_queue"))
