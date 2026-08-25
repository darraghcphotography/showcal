from flask import flash, redirect, render_template, request, url_for

from ... import productions_build
from ...auth import login_required
from ...db import get_db
from ...dedupe import find_candidates
from . import bp

DUPLICATE_TITLES_DISPLAY_LIMIT = 60


@bp.route("/duplicate-titles")
@login_required
def duplicate_titles():
    db = get_db()
    titles = {
        r[0]
        for r in db.execute(
            """
            SELECT show FROM shows WHERE show IS NOT NULL AND moderation_status = 'approved'
            UNION
            SELECT show FROM historical_results WHERE show IS NOT NULL
            """
        ).fetchall()
    }
    dismissed = {
        (r[0], r[1]) for r in db.execute("SELECT title_a, title_b FROM dismissed_duplicate_pairs").fetchall()
    }
    all_candidates = find_candidates(titles, dismissed)
    total_candidates = len(all_candidates)
    candidates = all_candidates[:DUPLICATE_TITLES_DISPLAY_LIMIT]

    relevant = {t for pair in candidates for t in pair[:2]}
    counts = {}
    for title in relevant:
        cur = db.execute("SELECT COUNT(*) FROM shows WHERE show = ?", (title,)).fetchone()[0]
        hist = db.execute("SELECT COUNT(*) FROM historical_results WHERE show = ?", (title,)).fetchone()[0]
        counts[title] = cur + hist

    return render_template(
        "admin/duplicate_titles.html", candidates=candidates, counts=counts, all_titles=sorted(titles),
        total_candidates=total_candidates, display_limit=DUPLICATE_TITLES_DISPLAY_LIMIT,
    )


# show_info and show_links are keyed by the title string itself (both have
# `show` as their PRIMARY KEY - see schema.sql), so they don't follow a retitle
# the way a foreign key would. Until this existed, every merge left its
# synopsis/rights/Wikipedia link stranded under the old spelling, rendering
# nowhere and showing up later in /admin/data-quality's "Orphaned title data" -
# i.e. the merge tool was quietly manufacturing the very rows that page exists
# to report. Same drop-vs-carry rule as the shows loop above: if the canonical
# title already has a row the "other" one is redundant, otherwise rename it.
TITLE_KEYED_TABLES = ("show_info", "show_links")


def move_title_keyed_rows(db, canonical, other):
    for table in TITLE_KEYED_TABLES:
        if not db.execute(f"SELECT 1 FROM {table} WHERE show = ?", (other,)).fetchone():
            continue
        if db.execute(f"SELECT 1 FROM {table} WHERE show = ?", (canonical,)).fetchone():
            db.execute(f"DELETE FROM {table} WHERE show = ?", (other,))
        else:
            db.execute(f"UPDATE {table} SET show = ? WHERE show = ?", (canonical, other))


def _merge_titles(db, canonical, other):
    # shows has a UNIQUE index on (society_id, season, show) - if the same
    # society already logged both the canonical and "other" title for the
    # same season (a real possibility, since that's exactly the situation
    # this tool exists to clean up), a blind UPDATE would collide with that
    # constraint and crash. Move rows one at a time instead: where renaming
    # would collide, the canonical row already covers that production, so
    # the "other" row is a redundant duplicate - delete it rather than
    # update it. Where there's no collision, rename as normal.
    rows = db.execute("SELECT id, society_id, season FROM shows WHERE show = ?", (other,)).fetchall()
    for row in rows:
        collision = db.execute(
            "SELECT id FROM shows WHERE society_id = ? AND season = ? AND show = ?",
            (row["society_id"], row["season"], canonical),
        ).fetchone()
        if collision:
            # A ShowTimes review can be attached to the row about to be
            # deleted (historical_reviews.show_id references shows.id), so
            # deleting it outright raises a FOREIGN KEY constraint failure -
            # confirmed, this 500'd the bulk merge against real data once
            # the review import had created skeleton shows. Move the review
            # onto the surviving row first: it's the same production either
            # way, which is the whole premise of merging these two titles.
            db.execute(
                "UPDATE historical_reviews SET show_id = ? WHERE show_id = ?",
                (collision["id"], row["id"]),
            )
            db.execute("DELETE FROM shows WHERE id = ?", (row["id"],))
        else:
            db.execute("UPDATE shows SET show = ? WHERE id = ?", (canonical, row["id"]))
    db.execute("UPDATE historical_results SET show = ? WHERE show = ?", (canonical, other))
    move_title_keyed_rows(db, canonical, other)
    db.execute(
        "DELETE FROM dismissed_duplicate_pairs WHERE title_a IN (?, ?) OR title_b IN (?, ?)",
        (canonical, other, canonical, other),
    )
    # Retitling rows in place changes which production they belong to, and
    # historical_results has no updated_at for the freshness check to notice.
    productions_build.mark_stale(db)


def _dismiss_pair(db, title_a, title_b):
    pair = tuple(sorted((title_a, title_b)))
    db.execute("INSERT OR IGNORE INTO dismissed_duplicate_pairs (title_a, title_b) VALUES (?, ?)", pair)


@bp.route("/duplicate-titles/merge", methods=("POST",))
@login_required
def merge_duplicate_titles():
    db = get_db()
    canonical = request.form.get("canonical", "").strip()
    other = request.form.get("other", "").strip()
    if not canonical or not other or canonical == other:
        flash("Something went wrong picking which title is correct - try again.", "error")
        return redirect(url_for("admin.duplicate_titles"))

    _merge_titles(db, canonical, other)
    db.commit()
    flash(f'Merged "{other}" into "{canonical}".', "success")
    return redirect(url_for("admin.duplicate_titles"))


@bp.route("/duplicate-titles/dismiss", methods=("POST",))
@login_required
def dismiss_duplicate_pair():
    db = get_db()
    title_a = request.form.get("title_a", "").strip()
    title_b = request.form.get("title_b", "").strip()
    if title_a and title_b:
        _dismiss_pair(db, title_a, title_b)
        db.commit()
    return redirect(url_for("admin.duplicate_titles"))


@bp.route("/duplicate-titles/bulk", methods=("POST",))
@login_required
def bulk_duplicate_titles():
    db = get_db()
    merged = 0
    dismissed = 0
    i = 0
    while f"pair_{i}_a" in request.form:
        a = request.form.get(f"pair_{i}_a", "").strip()
        b = request.form.get(f"pair_{i}_b", "").strip()
        decision = request.form.get(f"decision_{i}", "skip")
        if a and b:
            if decision == "keep_a":
                _merge_titles(db, a, b)
                merged += 1
            elif decision == "keep_b":
                _merge_titles(db, b, a)
                merged += 1
            elif decision == "dismiss":
                _dismiss_pair(db, a, b)
                dismissed += 1
        i += 1
    db.commit()
    if merged or dismissed:
        flash(f"Merged {merged} pair(s), dismissed {dismissed} pair(s).", "success")
    else:
        flash("No changes selected.", "warning")
    return redirect(url_for("admin.duplicate_titles"))
