"""Review queue for /admin/logo-candidates - candidate society logos staged
by import_logo_candidates.py from a delegated web search (see schema.sql's
logo_candidates table). A moderator looks at each already-fetched-and-
validated image and approves or rejects it; approving is the only thing that
ever writes societies.logo_filename here - nothing upstream of this queue
does."""
from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for

from ...auth import current_user, login_required
from ...db import get_db
from . import bp


@bp.route("/logo-candidates")
@login_required
def logo_candidates_queue():
    db = get_db()
    pending = db.execute(
        """
        SELECT logo_candidates.*, societies.name AS society_name
        FROM logo_candidates JOIN societies ON societies.id = logo_candidates.society_id
        WHERE logo_candidates.status = 'pending'
        ORDER BY societies.name
        """
    ).fetchall()
    recent_done = db.execute(
        """
        SELECT logo_candidates.*, societies.name AS society_name
        FROM logo_candidates JOIN societies ON societies.id = logo_candidates.society_id
        WHERE logo_candidates.status != 'pending'
        ORDER BY logo_candidates.moderated_at DESC LIMIT 20
        """
    ).fetchall()
    return render_template(
        "admin/logo_candidates_queue.html", pending=pending, recent_done=recent_done,
    )


@bp.route("/logo-candidates/<int:candidate_id>/approve", methods=("POST",))
@login_required
def approve_logo_candidate(candidate_id):
    db = get_db()
    candidate = db.execute(
        "SELECT * FROM logo_candidates WHERE id = ? AND status = 'pending'", (candidate_id,)
    ).fetchone()
    if candidate is None:
        abort(404)
    if not candidate["filename"]:
        # Nothing was actually fetched for this row (fetch_error is set
        # instead) - approving it would set a logo the site can't render.
        flash("This candidate couldn't be fetched, so there's nothing to approve - reject it or find the logo another way.", "error")
        return redirect(url_for("admin.logo_candidates_queue"))

    user = current_user()
    now = datetime.utcnow().isoformat()
    db.execute(
        "UPDATE societies SET logo_filename = ? WHERE id = ?",
        (candidate["filename"], candidate["society_id"]),
    )
    db.execute(
        "UPDATE logo_candidates SET status = 'approved', moderated_by = ?, moderated_at = ? WHERE id = ?",
        (user["username"], now, candidate_id),
    )
    db.commit()
    flash("Logo approved and set.", "success")
    return redirect(url_for("admin.logo_candidates_queue"))


@bp.route("/logo-candidates/<int:candidate_id>/reject", methods=("POST",))
@login_required
def reject_logo_candidate(candidate_id):
    db = get_db()
    user = current_user()
    moderator_notes = request.form.get("moderator_notes", "").strip() or None
    row = db.execute(
        "UPDATE logo_candidates SET status = 'rejected', moderator_notes = ?, moderated_by = ?, moderated_at = ? "
        "WHERE id = ? AND status = 'pending'",
        (moderator_notes, user["username"], datetime.utcnow().isoformat(), candidate_id),
    )
    db.commit()
    if row.rowcount == 0:
        abort(404)
    flash("Candidate rejected.", "success")
    return redirect(url_for("admin.logo_candidates_queue"))
