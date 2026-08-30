"""Moderation queue for /submit/photo - old review clippings and production
photos sent in by the public (see schema.sql's photo_submissions table for
why nothing here matches an existing show/society automatically). A
moderator looks at the photo, enters whatever it confirms into the real
tables by hand (show_info, historical_reviews, a show's own edit form,
whatever fits), then marks the row here 'done' or 'rejected' purely to keep
this queue clean - neither action touches shows/historical_reviews/show_info
itself."""
from flask import abort, flash, redirect, render_template, request, url_for

from ...clock import utcnow_iso
from ...constants import ALL_PHOTO_KIND_LABELS
from ...auth import current_user, login_required
from ...db import get_db
from . import bp


@bp.route("/photo-submissions")
@login_required
def photo_submissions_queue():
    db = get_db()
    pending = db.execute(
        "SELECT * FROM photo_submissions WHERE status = 'pending' ORDER BY created_at"
    ).fetchall()
    recent_done = db.execute(
        "SELECT * FROM photo_submissions WHERE status != 'pending' ORDER BY moderated_at DESC LIMIT 20"
    ).fetchall()
    return render_template(
        "admin/photo_submissions_queue.html", pending=pending, recent_done=recent_done,
        kind_labels=ALL_PHOTO_KIND_LABELS,
    )


def _set_status(submission_id, status):
    db = get_db()
    user = current_user()
    moderator_notes = request.form.get("moderator_notes", "").strip() or None
    row = db.execute(
        "UPDATE photo_submissions SET status = ?, moderator_notes = ?, moderated_by = ?, moderated_at = ? "
        "WHERE id = ? AND status = 'pending'",
        (status, moderator_notes, user["username"], utcnow_iso(), submission_id),
    )
    db.commit()
    if row.rowcount == 0:
        abort(404)


@bp.route("/photo-submissions/<int:submission_id>/done", methods=("POST",))
@login_required
def mark_photo_submission_done(submission_id):
    _set_status(submission_id, "done")
    flash("Marked done.", "success")
    return redirect(url_for("admin.photo_submissions_queue"))


@bp.route("/photo-submissions/<int:submission_id>/reject", methods=("POST",))
@login_required
def reject_photo_submission(submission_id):
    _set_status(submission_id, "rejected")
    flash("Submission rejected.", "success")
    return redirect(url_for("admin.photo_submissions_queue"))
