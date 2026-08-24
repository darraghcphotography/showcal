"""Admin CRUD for the public /faq page (see public.py's faq() and
schema.sql's faq_entries). A question stays a 'draft' - editable, but never
shown on the public page - until a moderator explicitly publishes it, same
idea as a draft blog post rather than every edit going live immediately.
sort_order is a plain integer moved up/down by hand: there's no natural
ordering (not alphabetical, not by date) for a page meant to read
top-to-bottom."""
from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for

from ...db import get_db
from ...auth import login_required
from . import bp


@bp.route("/faq")
@login_required
def faq_list():
    db = get_db()
    entries = db.execute("SELECT * FROM faq_entries ORDER BY sort_order, id").fetchall()
    return render_template("admin/faq.html", entries=entries)


@bp.route("/faq/new", methods=("GET", "POST"))
@login_required
def faq_new():
    if request.method == "POST":
        question = request.form.get("question", "").strip()
        answer = request.form.get("answer", "").strip()
        if not question or not answer:
            flash("Both a question and an answer are required.", "error")
            return render_template("admin/faq_form.html", entry=None, form=request.form)

        db = get_db()
        max_order = db.execute("SELECT COALESCE(MAX(sort_order), -1) FROM faq_entries").fetchone()[0]
        db.execute(
            "INSERT INTO faq_entries (question, answer, sort_order) VALUES (?, ?, ?)",
            (question, answer, max_order + 1),
        )
        db.commit()
        flash("FAQ entry added as a draft - publish it from the list when it's ready.", "success")
        return redirect(url_for("admin.faq_list"))

    return render_template("admin/faq_form.html", entry=None, form={})


@bp.route("/faq/<int:entry_id>/edit", methods=("GET", "POST"))
@login_required
def faq_edit(entry_id):
    db = get_db()
    entry = db.execute("SELECT * FROM faq_entries WHERE id = ?", (entry_id,)).fetchone()
    if entry is None:
        abort(404)

    if request.method == "POST":
        question = request.form.get("question", "").strip()
        answer = request.form.get("answer", "").strip()
        if not question or not answer:
            flash("Both a question and an answer are required.", "error")
            return render_template("admin/faq_form.html", entry=entry, form=request.form)

        db.execute(
            "UPDATE faq_entries SET question = ?, answer = ?, updated_at = datetime('now') WHERE id = ?",
            (question, answer, entry_id),
        )
        db.commit()
        flash("FAQ entry updated.", "success")
        return redirect(url_for("admin.faq_list"))

    return render_template("admin/faq_form.html", entry=entry, form=entry)


@bp.route("/faq/<int:entry_id>/publish", methods=("POST",))
@login_required
def faq_publish(entry_id):
    db = get_db()
    db.execute(
        "UPDATE faq_entries SET status = 'published', updated_at = datetime('now') WHERE id = ?",
        (entry_id,),
    )
    db.commit()
    flash("Published - now live on the public FAQ page.", "success")
    return redirect(url_for("admin.faq_list"))


@bp.route("/faq/<int:entry_id>/unpublish", methods=("POST",))
@login_required
def faq_unpublish(entry_id):
    db = get_db()
    db.execute(
        "UPDATE faq_entries SET status = 'draft', updated_at = datetime('now') WHERE id = ?",
        (entry_id,),
    )
    db.commit()
    flash("Unpublished - back to draft, no longer on the public page.", "success")
    return redirect(url_for("admin.faq_list"))


@bp.route("/faq/<int:entry_id>/delete", methods=("POST",))
@login_required
def faq_delete(entry_id):
    db = get_db()
    db.execute("DELETE FROM faq_entries WHERE id = ?", (entry_id,))
    db.commit()
    flash("FAQ entry deleted.", "success")
    return redirect(url_for("admin.faq_list"))


@bp.route("/faq/<int:entry_id>/move", methods=("POST",))
@login_required
def faq_move(entry_id):
    """Swaps this entry's sort_order with its neighbour in the given
    direction - the whole reordering mechanism, no drag-and-drop JS needed
    for what's normally a handful of questions."""
    direction = request.form.get("direction")
    if direction not in ("up", "down"):
        abort(400)

    db = get_db()
    entry = db.execute("SELECT * FROM faq_entries WHERE id = ?", (entry_id,)).fetchone()
    if entry is None:
        abort(404)

    if direction == "up":
        neighbour = db.execute(
            "SELECT * FROM faq_entries WHERE sort_order < ? ORDER BY sort_order DESC LIMIT 1",
            (entry["sort_order"],),
        ).fetchone()
    else:
        neighbour = db.execute(
            "SELECT * FROM faq_entries WHERE sort_order > ? ORDER BY sort_order ASC LIMIT 1",
            (entry["sort_order"],),
        ).fetchone()

    if neighbour is not None:
        db.execute("UPDATE faq_entries SET sort_order = ? WHERE id = ?", (neighbour["sort_order"], entry["id"]))
        db.execute("UPDATE faq_entries SET sort_order = ? WHERE id = ?", (entry["sort_order"], neighbour["id"]))
        db.commit()

    return redirect(url_for("admin.faq_list"))
