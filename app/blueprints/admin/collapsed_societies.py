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
    society = db.execute(
        "SELECT id, name, region FROM societies WHERE id = ?", (society_id,)).fetchone()
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

        # Decisions first in the sense that matters: the seasons somebody can
        # act on go to the top. Sorting purely by year buried the eight
        # evidenced Clara seasons under six rows of "nothing in the archive",
        # so the work was below the noise.
        groups.sort(key=lambda g: (
            0 if (g["suggestions"] and not g["decision"]) else 2 if g["decision"] else 1,
            -g["year"], g["tier"]))

        societies.append({
            "society": row,
            "groups": groups,
            "hidden": hidden,
            "recurring": [r for r in recurring if r["seasons"] > 1],
            # What a bulk accept would act on: the recurring name, and how many
            # of its seasons are still undecided.
            "bulk": next(
                ({"name": r["suggested_name"], "id": r["suggested_id"],
                  "seasons": len(collapsed_societies.seasons_attributed_to(
                      db, row["id"], r["suggested_id"]))}
                 for r in recurring if r["seasons"] > 1 and r["suggested_id"]), None),
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
                     previous_name, note=None, moved_show_ids=None):
    db.execute(
        """
        INSERT INTO collapsed_society_decisions
               (society_id, year, tier, moved_to_id, no_change, previous_name,
                moved_show_ids, note, decided_by, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(society_id, year, tier) DO UPDATE SET
               moved_to_id = excluded.moved_to_id,
               no_change   = excluded.no_change,
               previous_name = excluded.previous_name,
               moved_show_ids = excluded.moved_show_ids,
               note        = excluded.note,
               decided_by  = excluded.decided_by,
               updated_at  = excluded.updated_at
        """,
        (society_id, year, tier, moved_to_id, no_change, previous_name,
         moved_show_ids or None, note, current_user()["username"], utcnow_iso()),
    )


def _group_params(form):
    society_id = form.get("society_id", type=int)
    year = form.get("year", type=int)
    tier = (form.get("tier") or "").strip()
    if society_id is None or year is None or tier not in collapsed_societies.SECTIONS:
        abort(400)
    return society_id, year, tier


def _move_group(db, from_society, target, year, tier, note=None):
    """Move one season-and-section, award records and production alike.

    Returns (award_rows_moved, show_rows_moved), or (0, 0) if there was nothing
    left to move. Shared by the single button and the bulk accept so the two
    cannot drift - a bulk action that did less than the button it replaces
    would be the worst kind of shortcut.
    """
    # Found BEFORE the award records move, because the titles to match on are
    # read from those very rows - afterwards there is nothing left under this
    # society to read. A test caught that; the productions silently stayed put.
    shows = collapsed_societies.historical_shows_for(db, from_society["id"], year, tier)

    # society_name is the printed name carried through from the source CSV. It
    # moves with the rows so the record still says who staged the show, rather
    # than leaving the old society's name attached to the new one's records.
    moved = db.execute(
        """
        UPDATE historical_results
           SET society_id = ?, society_name = ?
         WHERE society_id = ? AND year = ? AND tier = ?
        """,
        (target["id"], target["name"], from_society["id"], year, tier),
    ).rowcount
    if not moved:
        return 0, 0

    # The collapse is in `shows` too. Without this the award records move and
    # the productions stay, so the other society's shows keep appearing on the
    # wrong public page - the half-fix a visitor notices first.
    if shows:
        db.execute(
            "UPDATE shows SET society_id = ?, region = ? WHERE id IN ({})".format(
                ",".join("?" * len(shows))),
            [target["id"], target["region"]] + [row["id"] for row in shows])

    _record_decision(db, from_society["id"], year, tier, target["id"], 0,
                     from_society["name"], note,
                     ",".join(str(row["id"]) for row in shows))
    return moved, len(shows)


@bp.route("/collapsed-societies/move", methods=("POST",))
@login_required
def move_collapsed_group():
    """Reassign one season-and-section of award records to another society."""
    db = get_db()
    society_id, year, tier = _group_params(request.form)
    from_society = _society_or_404(db, society_id)

    target_id = request.form.get("moved_to_id", type=int)
    if target_id is None:
        typed = request.form.get("moved_to", "").strip()
        target = db.execute(
            "SELECT id, name, region FROM societies WHERE name = ?", (typed,)).fetchone()
        if target is None:
            flash(f'"{typed}" is not a society on the list. Add it first if it is '
                  f'genuinely missing - Athenry was, which is part of the problem.', "error")
            return redirect(url_for("admin.collapsed_societies_queue"))
    else:
        target = _society_or_404(db, target_id)

    if target["id"] == from_society["id"]:
        flash("That is the society the records are already under.", "warning")
        return redirect(url_for("admin.collapsed_societies_queue"))

    moved, shows = _move_group(db, from_society, target, year, tier,
                               request.form.get("note") or None)
    if not moved:
        flash("Nothing to move - those records have already been reassigned.", "warning")
        return redirect(url_for("admin.collapsed_societies_queue"))

    # An in-place UPDATE moves neither COUNT(*) nor MAX(id), so the derived
    # productions table would never notice this on its own.
    productions_build.mark_stale(db)
    db.commit()
    flash("Moved {} award record{} - {} {} {} - to {}{}. Undo is on this page.".format(
        moved, "" if moved == 1 else "s", from_society["name"], year, tier,
        target["name"],
        "" if not shows else ", with {} production{}".format(
            shows, "" if shows == 1 else "s")), "success")
    return redirect(url_for("admin.collapsed_societies_queue"))


@bp.route("/collapsed-societies/accept-all", methods=("POST",))
@login_required
def accept_all_for_society():
    """Move every undecided season the archive attributes to one society.

    Deliberately not an "accept everything" button. It acts only on seasons
    whose evidence names *this* society, and only where that name recurs across
    more than one season - the signal that separates a finding from a
    coincidence. A name that appears against a single season is left alone for
    a human to look at, because one page naming somebody once is exactly what a
    common surname produces.
    """
    db = get_db()
    society_id = request.form.get("society_id", type=int)
    target_id = request.form.get("moved_to_id", type=int)
    if society_id is None or target_id is None:
        abort(400)
    from_society = _society_or_404(db, society_id)
    target = _society_or_404(db, target_id)
    if target["id"] == from_society["id"]:
        abort(400)

    seasons = collapsed_societies.seasons_attributed_to(db, society_id, target["id"])
    moved_groups = moved_rows = moved_shows = 0
    for year, tier in seasons:
        rows, shows = _move_group(
            db, from_society, target, year, tier,
            "Accepted in bulk: the archive names {} across {} seasons of this "
            "society's record.".format(target["name"], len(seasons)))
        if rows:
            moved_groups += 1
            moved_rows += rows
            moved_shows += shows

    if not moved_groups:
        flash("Nothing to accept - those seasons are already decided.", "warning")
        return redirect(url_for("admin.collapsed_societies_queue"))

    productions_build.mark_stale(db)
    db.commit()
    flash("Moved {} season{} - {} award record{} and {} production{} - from {} to {}. "
          "Each one is undoable individually on this page.".format(
              moved_groups, "" if moved_groups == 1 else "s",
              moved_rows, "" if moved_rows == 1 else "s",
              moved_shows, "" if moved_shows == 1 else "s",
              from_society["name"], target["name"]), "success")
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
        # The exact production rows this decision moved, by id. Matching on
        # title instead would be a guess: two societies can stage the same show
        # in the same season, which is precisely the situation here.
        show_ids = [int(i) for i in (decision["moved_show_ids"] or "").split(",") if i.strip()]
        if show_ids:
            region = db.execute("SELECT region FROM societies WHERE id = ?",
                                (society_id,)).fetchone()["region"]
            db.execute(
                "UPDATE shows SET society_id = ?, region = ? WHERE id IN ({}) "
                "AND society_id = ?".format(",".join("?" * len(show_ids))),
                [society_id, region] + show_ids + [decision["moved_to_id"]])
        productions_build.mark_stale(db)
    db.execute(
        "DELETE FROM collapsed_society_decisions WHERE society_id = ? AND year = ? AND tier = ?",
        (society_id, year, tier),
    )
    db.commit()
    flash("Undone - that season is back in the queue.", "success")
    return redirect(url_for("admin.collapsed_societies_queue"))
