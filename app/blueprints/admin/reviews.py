from flask import flash, redirect, render_template, request, url_for

from ...auth import login_required
from ...db import get_db
from . import bp
from ._shared import NEEDS_REVIEW_WHERE, URL_RE, needs_review_params


@bp.route("/reviews-queue")
@login_required
def reviews_queue():
    db = get_db()

    # Same definition as the dashboard's own "Shows missing a review link"
    # counter and the shows-list filter behind it - see NEEDS_REVIEW_WHERE.
    # This page's own version was the one that had it right; the shared
    # fragment is essentially it, with undated-but-past shows no longer
    # dropped for having no closing_date to test.
    rows = db.execute(
        f"""
        SELECT shows.id, shows.show, shows.season, shows.review_status,
               COALESCE(shows.closing_date, shows.opening_date) AS finished_on,
               societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE {NEEDS_REVIEW_WHERE}
        ORDER BY finished_on DESC
        """,
        needs_review_params(db),
    ).fetchall()

    return render_template("admin/reviews_queue.html", rows=rows)


@bp.route("/reviews-queue/<int:show_id>/save", methods=("POST",))
@login_required
def save_review_link(show_id):
    url = request.form.get("review_url", "").strip()
    author = request.form.get("review_author", "").strip() or None
    if url and URL_RE.match(url):
        get_db().execute(
            "UPDATE shows SET review_url = ?, review_author = ?, review_status = 'Published', "
            "updated_at = datetime('now') WHERE id = ?",
            (url, author, show_id),
        )
        get_db().commit()
        flash("Review link saved.", "success")
    else:
        flash("Enter a valid http(s) URL.", "error")
    return redirect(url_for("admin.reviews_queue"))


@bp.route("/reviews-queue/<int:show_id>/not-adjudicated", methods=("POST",))
@login_required
def mark_review_not_adjudicated(show_id):
    get_db().execute(
        "UPDATE shows SET review_status = 'Not adjudicated', updated_at = datetime('now') WHERE id = ?",
        (show_id,),
    )
    get_db().commit()
    flash("Marked not adjudicated.", "success")
    return redirect(url_for("admin.reviews_queue"))
