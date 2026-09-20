"""Queue for award rows filed under the wrong society.

`docs/collapsed-societies.md` is the background: two societies merged into one
name before the data reached us, so one society's record carries another's
nominations. Seven societies are affected and two of them - Athlone/Athenry and
Clara/Clane - are now confirmed from the official AIMS lists published on the
pre-Wix aims.ie.

This is a propose-don't-apply queue, the same shape as the venue and people
ones, and the reasons are sharper here than in either:

  * **The evidence is external and has to travel with the proposal.** The
    harvest lives outside the repo, so a suggestion is only worth acting on if
    it carries the capture date and URL it came from. Every row on this page
    links back to the page it was read off.

  * **The right answer is often a society we do not hold.** Athenry has no
    `societies` row - that is half the reason nobody noticed for twenty years.
    So a suggestion can be correct and still not be applicable, and the queue
    says so plainly instead of hiding it.

  * **A wrong move is worse than no move.** It publishes one society's history
    on another's public page, and the rows being moved are decades old and not
    reconstructible from anywhere else. So nothing is pre-selected, the group's
    own rows are listed before the button that moves them, and every decision
    is reversible from this page.

The unit is a season and a section, never a single row - see
`app/collapsed_societies.py` for why.
"""
from flask import abort, flash, redirect, render_template, request, url_for

from ... import collapsed_societies, productions_build
from ...auth import current_user, login_required
from ...clock import utcnow_iso
from ...db import get_db
from . import bp


def _society_or_404(db, society_id):
    society = db.execute("SELECT id, name FROM societies WHERE id = ?", (society_id,)).fetchone()
    if society is None:
        abort(404)
    return society


def _group_rows(db, society_id, year, tier):
    """The award rows a decision would move, newest category first."""
    return db.execute(
        """
        SELECT id, category_name, result, show, nominee_name, role
          FROM historical_results
         WHERE society_id = ? AND year = ? AND tier = ?
      ORDER BY category_name
        """,
        (society_id, year, tier),
    ).fetchall()


@bp.route("/collapsed-societies")
@login_required
def collapsed_societies_queue():
    # By default only the seasons somebody could actually decide about: the ones
    # in conflict, and the ones the archive has something to say about. A
    # flagged society's untroubled 2024 season is not a decision, and rendering
    # all 124 of them with their forms took the page past 600KB - the same
    # mistake the society-links queue made once with a per-row <select>.
    # ?all=1 shows every season, because a season with neither flag can still be
    # misfiled: that is exactly where 2008 was hiding.
    show_all = request.args.get("all") == "1"
    db = get_db()
    societies = []
    for row in collapsed_societies.societies_in_scope(db):
        suggestions = collapsed_societies.suggestions_for(row["id"], db)
        decisions = collapsed_societies.decisions_for(row["id"], db)
        groups = []
        hidden = 0
        for group in collapsed_societies.groups_for(row["id"], db):
            key = (group["year"], group["tier"])
            entry = dict(group)
            entry["suggestions"] = suggestions.get(key, [])
            entry["decision"] = decisions.get(key)
            if not (show_all or group["in_conflict"] or entry["suggestions"]
                    or entry["decision"]):
                hidden += 1
                continue
            entry["rows"] = _group_rows(db, row["id"], group["year"], group["tier"])
            if not entry["rows"] and entry["decision"] and entry["decision"]["moved_to_id"]:
                # Already moved: read the rows from where they went, so the
                # season still says what it is rather than showing as empty.
                entry["rows"] = _group_rows(db, entry["decision"]["moved_to_id"],
                                            group["year"], group["tier"])
                entry["row_count"] = len(entry["rows"])
                entry["shows"] = ", ".join(sorted({r["show"] for r in entry["rows"] if r["show"]}))
            groups.append(entry)
        recurring = collapsed_societies.recurring_names(row["id"], db)
        # Built once, outside the loop. Rebuilding a lookup per row is what took
        # the site down with a 524 when the historical-reviews queue shipped.
        recurring_seasons = {r["suggested_name"]: r["seasons"] for r in recurring}
        for group in groups:
            # A suggestion that appears against this society in only one season
            # is flagged on the page rather than dropped. Dropping it would be
            # deciding, which is not this queue's job - but it is worth saying
            # out loud that one hit is not the same kind of evidence as seven.
            group["suggestions"] = [
                dict(s, one_off=recurring_seasons.get(s["suggested_name"], 0) < 2)
                for s in group["suggestions"]
            ]

        societies.append({
            "society": row,
            "groups": groups,
            "hidden": hidden,
            "recurring": [r for r in recurring if r["seasons"] > 1],
            # A society with no evidence against any of its groups is still
            # listed - the conflict is real and worth seeing - but it sorts
            # below the ones somebody can actually act on.
            "actionable": sum(1 for g in groups if g["suggestions"] and not g["decision"]),
        })

    societies.sort(key=lambda s: (-s["actionable"], -s["society"]["award_rows"]))
    return render_template(
        "admin/collapsed_societies.html",
        societies=societies,
        show_all=show_all,
        undecided=collapsed_societies.undecided_count(db),
        all_societies=db.execute("SELECT id, name FROM societies ORDER BY name").fetchall(),
    )


def _record_decision(db, society_id, year, tier, moved_to_id, no_change,
                     previous_name, note=None):
    db.execute(
        """
        INSERT INTO collapsed_society_decisions
               (society_id, year, tier, moved_to_id, no_change, previous_name,
                note, decided_by, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(society_id, year, tier) DO UPDATE SET
               moved_to_id = excluded.moved_to_id,
               no_change   = excluded.no_change,
               previous_name = excluded.previous_name,
               note        = excluded.note,
               decided_by  = excluded.decided_by,
               updated_at  = excluded.updated_at
        """,
        (society_id, year, tier, moved_to_id, no_change, previous_name, note,
         current_user()["username"], utcnow_iso()),
    )


def _group_params(form):
    society_id = form.get("society_id", type=int)
    year = form.get("year", type=int)
    tier = (form.get("tier") or "").strip()
    if society_id is None or year is None or tier not in collapsed_societies.SECTIONS:
        abort(400)
    return society_id, year, tier


@bp.route("/collapsed-societies/move", methods=("POST",))
@login_required
def move_collapsed_group():
    """Reassign one season-and-section of award rows to another society."""
    db = get_db()
    society_id, year, tier = _group_params(request.form)
    from_society = _society_or_404(db, society_id)

    target_id = request.form.get("moved_to_id", type=int)
    if target_id is None:
        typed = request.form.get("moved_to", "").strip()
        target = db.execute("SELECT id, name FROM societies WHERE name = ?", (typed,)).fetchone()
        if target is None:
            flash(f'"{typed}" is not a society on the list. Add it first if it is '
                  f'genuinely missing - Athenry is, which is part of the problem.', "error")
            return redirect(url_for("admin.collapsed_societies_queue"))
    else:
        target = _society_or_404(db, target_id)

    if target["id"] == from_society["id"]:
        flash("That is the society the rows are already under.", "warning")
        return redirect(url_for("admin.collapsed_societies_queue"))

    # society_name is the printed name carried through from the source CSV. It
    # is moved with the rows so the archive still records what the source said,
    # rather than leaving the old society's name attached to the new one's rows.
    moved = db.execute(
        """
        UPDATE historical_results
           SET society_id = ?, society_name = ?
         WHERE society_id = ? AND year = ? AND tier = ?
        """,
        (target["id"], target["name"], from_society["id"], year, tier),
    ).rowcount
    if not moved:
        flash("Nothing to move - those rows have already been reassigned.", "warning")
        return redirect(url_for("admin.collapsed_societies_queue"))

    _record_decision(db, from_society["id"], year, tier, target["id"], 0,
                     from_society["name"], request.form.get("note") or None)
    # An in-place UPDATE moves neither COUNT(*) nor MAX(id), so the derived
    # productions table would never notice this on its own - same reason
    # historical_society_links marks stale after a link.
    productions_build.mark_stale(db)
    db.commit()
    flash(f'Moved {moved} award record{"" if moved == 1 else "s"} - '
          f'{from_society["name"]} {year} {tier} - to {target["name"]}. '
          f'Undo is on this page.', "success")
    return redirect(url_for("admin.collapsed_societies_queue"))


@bp.route("/collapsed-societies/keep", methods=("POST",))
@login_required
def keep_collapsed_group():
    """Settle a group as correctly filed. Touches no award row."""
    db = get_db()
    society_id, year, tier = _group_params(request.form)
    society = _society_or_404(db, society_id)
    _record_decision(db, society_id, year, tier, None, 1, society["name"],
                     request.form.get("note") or None)
    db.commit()
    flash(f'{society["name"]} {year} {tier} settled as correctly filed.', "success")
    return redirect(url_for("admin.collapsed_societies_queue"))


@bp.route("/collapsed-societies/undo", methods=("POST",))
@login_required
def undo_collapsed_decision():
    """Put a group back where it was.

    Not optional. These rows are decades old, they are not reconstructible from
    anywhere else, and without this an over-confident click needs a database
    shell to reverse.
    """
    db = get_db()
    society_id, year, tier = _group_params(request.form)
    decision = db.execute(
        "SELECT * FROM collapsed_society_decisions WHERE society_id = ? AND year = ? AND tier = ?",
        (society_id, year, tier),
    ).fetchone()
    if decision is None:
        abort(404)

    if decision["moved_to_id"] is not None:
        # Scoped to rows still sitting where this decision put them, so a row
        # moved on somewhere else afterwards is left alone.
        db.execute(
            """
            UPDATE historical_results
               SET society_id = ?, society_name = ?
             WHERE society_id = ? AND year = ? AND tier = ?
            """,
            (society_id, decision["previous_name"], decision["moved_to_id"], year, tier),
        )
        productions_build.mark_stale(db)
    db.execute(
        "DELETE FROM collapsed_society_decisions WHERE society_id = ? AND year = ? AND tier = ?",
        (society_id, year, tier),
    )
    db.commit()
    flash("Undone - that season is back in the queue.", "success")
    return redirect(url_for("admin.collapsed_societies_queue"))
