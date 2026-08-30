import sqlite3
from datetime import date, datetime

from flask import abort, current_app, flash, redirect, render_template, request, url_for

from ...clock import utcnow_iso
from ...auth import current_user, login_required
from ...constants import REGIONS, REVIEW_STATUSES, RIGHTS_STATUSES, SHOW_SECTIONS
from ... import notify
from ...db import get_db
from ...search import escape_like
from ...production_credits import suggest_credits, suggest_venue
from ...season import current_season, season_range
from ...redirects import came_from, return_to
from ...uploads import save_poster
from . import bp
from ._shared import (
    DATE_RE,
    MISSING_POSTER_WHERE,
    NEEDS_REVIEW_WHERE,
    back_to,
    missing_poster_params,
    needs_review_params,
)

@bp.route("/queue")
@login_required
def queue():
    db = get_db()
    pending = db.execute(
        """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.moderation_status = 'pending'
        ORDER BY shows.created_at
        """
    ).fetchall()
    recent_done = db.execute(
        """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.moderation_status IN ('approved', 'rejected') AND shows.moderated_at IS NOT NULL
        ORDER BY shows.moderated_at DESC LIMIT 20
        """
    ).fetchall()
    return render_template("admin/queue.html", shows=pending, recent_done=recent_done)


@bp.route("/queue/<int:show_id>/approve", methods=("POST",))
@login_required
def approve(show_id):
    db = get_db()
    user = current_user()
    db.execute(
        """
        UPDATE shows
        SET moderation_status = 'approved', moderated_by = ?, moderated_at = ?, updated_at = ?
        WHERE id = ? AND moderation_status = 'pending'
        """,
        (user["username"], utcnow_iso(), utcnow_iso(), show_id),
    )
    db.commit()
    flash("Show approved and now live.", "success")
    return redirect(url_for("admin.queue"))


@bp.route("/queue/<int:show_id>/reject", methods=("POST",))
@login_required
def reject(show_id):
    db = get_db()
    user = current_user()
    db.execute(
        """
        UPDATE shows
        SET moderation_status = 'rejected', moderated_by = ?, moderated_at = ?, updated_at = ?
        WHERE id = ? AND moderation_status = 'pending'
        """,
        (user["username"], utcnow_iso(), utcnow_iso(), show_id),
    )
    db.commit()
    flash("Submission rejected.", "success")
    return redirect(url_for("admin.queue"))


@bp.route("/shows")
@login_required
def shows_list():
    db = get_db()
    q = request.args.get("q", "").strip()
    needs_review = request.args.get("needs_review", "")
    # "" (default) = current season and earlier only - keeps seasons still mostly
    # placeholder "TBA" slots (e.g. next season, signalled early) out of the way.
    # "all" = no season filter. Anything else = an exact season match.
    season = request.args.get("season", "")
    current = current_season(db)
    if needs_review:
        pass

    # Named params throughout, not positional - NEEDS_REVIEW_WHERE below uses
    # them, and sqlite3 won't mix the two styles in one statement.
    query = """
        SELECT shows.*, societies.name AS society_name
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.moderation_status = 'approved'
    """
    params = needs_review_params(db)
    if q:
        query += " AND (shows.show LIKE :like ESCAPE '\\' OR societies.name LIKE :like ESCAPE '\\')"
        escaped = escape_like(q)
        params["like"] = f"%{escaped}%"
    if needs_review:
        # Exactly the dashboard counter's own definition, so the number on the
        # card and the number of rows on this page can't disagree - see
        # NEEDS_REVIEW_WHERE.
        query += f" AND {NEEDS_REVIEW_WHERE}"
    if season == "":
        query += " AND shows.season <= :current_season"
    elif season != "all":
        query += " AND shows.season = :season"
        params["season"] = season
    query += " ORDER BY shows.season DESC, societies.name"

    shows = db.execute(query, params).fetchall()

    seasons = [
        r["season"]
        for r in db.execute("SELECT DISTINCT season FROM shows ORDER BY season DESC").fetchall()
    ]

    return render_template(
        "admin/shows_list.html", shows=shows, q=q, needs_review=needs_review,
        season=season, seasons=seasons, current_season=current,
    )


@bp.route("/societies/<int:society_id>/shows/new", methods=("GET", "POST"))
@login_required
def new_show(society_id):
    db = get_db()
    society = db.execute("SELECT * FROM societies WHERE id = ?", (society_id,)).fetchone()
    if society is None:
        abort(404)

    if request.method == "POST":
        errors = []
        season = request.form.get("season", "").strip()
        region = request.form.get("region", "")
        section = request.form.get("section") or None
        show_title = request.form.get("show", "").strip() or None
        opening_date = request.form.get("opening_date", "").strip() or None
        closing_date = request.form.get("closing_date", "").strip() or None
        adjudication_date = request.form.get("adjudication_date", "").strip() or None
        venue = request.form.get("venue", "").strip() or None
        director = request.form.get("director", "").strip() or None
        musical_director = request.form.get("musical_director", "").strip() or None
        choreographer = request.form.get("choreographer", "").strip() or None
        review_url = request.form.get("review_url", "").strip() or None
        review_status = request.form.get("review_status", "None")
        ticket_url = request.form.get("ticket_url", "").strip() or None

        if not season:
            errors.append("Choose a season.")
        if region not in REGIONS:
            errors.append("Choose a valid region.")
        if section is not None and section not in SHOW_SECTIONS:
            errors.append("Choose a valid tier.")
        for label, value in (
            ("Opening date", opening_date),
            ("Closing date", closing_date),
            ("Adjudication date", adjudication_date),
        ):
            if value and not DATE_RE.match(value):
                errors.append(f"{label} must be a valid date.")

        if review_url:
            review_status = "Published"
        elif review_status not in REVIEW_STATUSES:
            errors.append("Choose a valid review status.")

        poster_filename = None
        poster_file = request.files.get("poster")
        if poster_file and poster_file.filename:
            try:
                poster_filename = save_poster(poster_file, current_app.config["UPLOAD_DIR"])
            except ValueError as e:
                errors.append(str(e))

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/new_show.html", society=society, regions=REGIONS, sections=SHOW_SECTIONS,
                review_statuses=REVIEW_STATUSES, seasons=season_range(db), form=request.form,
            )

        try:
            db.execute(
                """
                INSERT INTO shows (
                    society_id, season, region, section, show,
                    opening_date, closing_date, adjudication_date,
                    venue, director, musical_director, choreographer,
                    review_url, review_status, ticket_url, poster_filename,
                    moderation_status, source, moderated_by, moderated_at
                ) VALUES (
                    :society_id, :season, :region, :section, :show,
                    :opening_date, :closing_date, :adjudication_date,
                    :venue, :director, :musical_director, :choreographer,
                    :review_url, :review_status, :ticket_url, :poster_filename,
                    'approved', 'submission', :moderated_by, :moderated_at
                )
                """,
                {
                    "society_id": society_id,
                    "season": season,
                    "region": region,
                    "section": section,
                    "show": show_title,
                    "opening_date": opening_date,
                    "closing_date": closing_date,
                    "adjudication_date": adjudication_date,
                    "venue": venue or society["default_venue"],
                    "director": director,
                    "musical_director": musical_director,
                    "choreographer": choreographer,
                    "review_url": review_url,
                    "review_status": review_status,
                    "ticket_url": ticket_url,
                    "poster_filename": poster_filename,
                    "moderated_by": current_user()["username"],
                    "moderated_at": utcnow_iso(),
                },
            )
        except sqlite3.IntegrityError:
            flash("This society already has a show with that exact title in that season.", "error")
            return render_template(
                "admin/new_show.html", society=society, regions=REGIONS, sections=SHOW_SECTIONS,
                review_statuses=REVIEW_STATUSES, seasons=season_range(db), form=request.form,
            )

        db.commit()
        flash("Show added.", "success")
        return redirect(url_for("admin.edit_society", society_id=society_id))

    return render_template(
        "admin/new_show.html", society=society, regions=REGIONS, sections=SHOW_SECTIONS,
        review_statuses=REVIEW_STATUSES, seasons=season_range(db),
        form={"region": society["region"]},
    )


def _show_field_suggestions(db, show):
    """Best-effort suggestions for this show's blank production-team/venue
    fields, pulled from its linked ShowTimes review and the society's own
    known default venue (see app/production_credits.py). Only computed for
    fields that are actually blank, and only ever shown to a moderator to
    accept, edit, or ignore on the edit-show form - never written
    automatically. Returns {field: suggested_value}, only for fields with
    an actual suggestion."""
    suggestions = {}
    review = db.execute(
        "SELECT review_text FROM historical_reviews WHERE show_id = ? AND moderation_status = 'approved' LIMIT 1",
        (show["id"],),
    ).fetchone()
    review_text = review["review_text"] if review else None

    if review_text:
        credits = suggest_credits(review_text)
        for field in ("director", "musical_director", "choreographer"):
            if credits[field] and not show[field]:
                suggestions[field] = credits[field]

    if not show["venue"]:
        if show["society_default_venue"]:
            suggestions["venue"] = show["society_default_venue"]
        elif review_text:
            known_venues = [
                r["venue"] for r in db.execute(
                    "SELECT DISTINCT venue FROM shows WHERE venue IS NOT NULL AND venue != ''"
                ).fetchall()
            ]
            venue = suggest_venue(review_text, known_venues)
            if venue:
                suggestions["venue"] = venue

    return suggestions


@bp.route("/shows/<int:show_id>/edit", methods=("GET", "POST"))
@login_required
def edit_show(show_id):
    db = get_db()
    show = db.execute(
        """
        SELECT shows.*, societies.name AS society_name, societies.default_venue AS society_default_venue
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE shows.id = ?
        """,
        (show_id,),
    ).fetchone()
    if show is None:
        abort(404)

    suggestions = _show_field_suggestions(db, show)
    existing_review = db.execute(
        """
        SELECT historical_reviews.*, adjudicators.name AS adjudicator_name
        FROM historical_reviews
        LEFT JOIN adjudicators ON adjudicators.id = historical_reviews.adjudicator_id
        WHERE historical_reviews.show_id = ? AND historical_reviews.moderation_status = 'approved'
        ORDER BY historical_reviews.id ASC LIMIT 1
        """,
        (show_id,),
    ).fetchone()
    adjudicators = db.execute("SELECT id, name FROM adjudicators ORDER BY name").fetchall()

    if request.method == "POST":
        errors = []
        season = request.form.get("season", "").strip()
        region = request.form.get("region", "")
        section = request.form.get("section") or None
        show_title = request.form.get("show", "").strip() or None
        opening_date = request.form.get("opening_date", "").strip() or None
        closing_date = request.form.get("closing_date", "").strip() or None
        adjudication_date = request.form.get("adjudication_date", "").strip() or None
        venue = request.form.get("venue", "").strip() or None
        director = request.form.get("director", "").strip() or None
        musical_director = request.form.get("musical_director", "").strip() or None
        choreographer = request.form.get("choreographer", "").strip() or None
        review_url = request.form.get("review_url", "").strip() or None
        review_author = request.form.get("review_author", "").strip() or None
        review_status = request.form.get("review_status", "None")
        ticket_url = request.form.get("ticket_url", "").strip() or None

        if region not in REGIONS:
            errors.append("Choose a valid region.")
        if section is not None and section not in SHOW_SECTIONS:
            errors.append("Choose a valid tier.")
        for label, value in (
            ("Opening date", opening_date),
            ("Closing date", closing_date),
            ("Adjudication date", adjudication_date),
        ):
            if value and not DATE_RE.match(value):
                errors.append(f"{label} must be a valid date.")

        # Attaching a review URL is what makes a review "Published" - this is
        # the one thing that overrides whatever was picked in the dropdown,
        # per the moderation workflow (attach link -> flips to Published).
        if review_url:
            review_status = "Published"
        elif review_status not in REVIEW_STATUSES:
            errors.append("Choose a valid review status.")

        poster_filename = show["poster_filename"]
        poster_file = request.files.get("poster")
        if poster_file and poster_file.filename:
            try:
                poster_filename = save_poster(poster_file, current_app.config["UPLOAD_DIR"])
            except ValueError as e:
                errors.append(str(e))
        elif request.form.get("remove_poster"):
            poster_filename = None

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("admin/edit_show.html", show=show, regions=REGIONS,
                                    sections=SHOW_SECTIONS, review_statuses=REVIEW_STATUSES,
                                    suggestions=suggestions, existing_review=existing_review,
                                    adjudicators=adjudicators,
                                    return_path=request.form.get("next"))

        db.execute(
            """
            UPDATE shows SET
                season = ?, region = ?, section = ?, show = ?,
                opening_date = ?, closing_date = ?, adjudication_date = ?,
                venue = ?, director = ?, musical_director = ?, choreographer = ?,
                review_url = ?, review_author = ?, review_status = ?, ticket_url = ?, poster_filename = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                season, region, section, show_title,
                opening_date, closing_date, adjudication_date,
                venue, director, musical_director, choreographer,
                review_url, review_author, review_status, ticket_url, poster_filename,
                utcnow_iso(), show_id,
            ),
        )
        db.commit()
        flash("Show updated.", "success")
        # Back to whatever page the edit was opened from - normally the show's
        # own public page, since that is where "Edit this show" lives.
        return redirect(return_to(url_for("admin.shows_list")))

    return render_template("admin/edit_show.html", show=show, regions=REGIONS,
                            sections=SHOW_SECTIONS, review_statuses=REVIEW_STATUSES,
                            suggestions=suggestions, existing_review=existing_review,
                            adjudicators=adjudicators, return_path=came_from())


def _credit_backfill_proposals(db):
    """Every approved historical show with a linked review, a blank
    production-team/venue field, and something extractable to put in it.
    Read-only - building this changes nothing. Only ever proposes for fields
    that are actually blank, so a value a moderator (or the CSV import)
    already set is never contradicted."""
    rows = db.execute(
        """
        SELECT shows.id AS show_id, shows.show, shows.season, shows.venue,
               shows.director, shows.musical_director, shows.choreographer,
               societies.name AS society_name, societies.default_venue,
               historical_reviews.review_text
        FROM shows
        JOIN societies ON societies.id = shows.society_id
        JOIN historical_reviews ON historical_reviews.show_id = shows.id
                               AND historical_reviews.moderation_status = 'approved'
        WHERE shows.moderation_status = 'approved'
          AND (shows.venue IS NULL OR shows.director IS NULL
               OR shows.musical_director IS NULL OR shows.choreographer IS NULL)
        ORDER BY shows.season DESC, societies.name
        """
    ).fetchall()
    if not rows:
        return []
    known_venues = [
        r["venue"] for r in db.execute(
            "SELECT DISTINCT venue FROM shows WHERE venue IS NOT NULL AND venue != ''"
        ).fetchall()
    ]

    proposals = []
    for row in rows:
        credits = suggest_credits(row["review_text"])
        fields = {
            field: credits[field]
            for field in ("director", "musical_director", "choreographer")
            if credits[field] and not row[field]
        }
        if not row["venue"]:
            venue = row["default_venue"] or suggest_venue(row["review_text"], known_venues)
            if venue:
                fields["venue"] = venue
        if fields:
            proposals.append({
                "show_id": row["show_id"],
                "show": row["show"],
                "season": row["season"],
                "society_name": row["society_name"],
                "fields": fields,
            })
    return proposals


@bp.route("/backfill-credits")
@login_required
def backfill_credits():
    db = get_db()
    proposals = _credit_backfill_proposals(db)
    field_counts = {}
    for p in proposals:
        for field in p["fields"]:
            field_counts[field] = field_counts.get(field, 0) + 1
    return render_template(
        "admin/backfill_credits.html", proposals=proposals, field_counts=field_counts,
        total_values=sum(len(p["fields"]) for p in proposals),
    )


@bp.route("/backfill-credits/apply", methods=("POST",))
@login_required
def apply_backfill_credits():
    """Writes the selected proposals. Recomputed here rather than trusting
    values posted back from the form, so what gets written is always what
    the server itself derived from the review text - the form only chooses
    *which* shows to apply. Still only ever fills a field that is blank at
    the moment of writing."""
    db = get_db()
    selected = {int(v) for v in request.form.getlist("show_id") if v.isdigit()}
    if not selected:
        flash("Nothing selected - no changes made.", "error")
        return redirect(url_for("admin.backfill_credits"))

    applied_shows = 0
    applied_values = 0
    for proposal in _credit_backfill_proposals(db):
        if proposal["show_id"] not in selected:
            continue
        assignments = ", ".join(f"{field} = ?" for field in proposal["fields"])
        values = list(proposal["fields"].values())
        db.execute(
            f"UPDATE shows SET {assignments}, updated_at = ? WHERE id = ?",
            (*values, utcnow_iso(), proposal["show_id"]),
        )
        applied_shows += 1
        applied_values += len(proposal["fields"])
    db.commit()
    flash(
        f"Filled {applied_values} field{'' if applied_values == 1 else 's'} "
        f"across {applied_shows} show{'' if applied_shows == 1 else 's'}.",
        "success",
    )
    return redirect(url_for("admin.backfill_credits"))


@bp.route("/shows/<int:show_id>/delete", methods=("POST",))
@login_required
def delete_show(show_id):
    db = get_db()
    show = db.execute("SELECT id FROM shows WHERE id = ?", (show_id,)).fetchone()
    if show is None:
        abort(404)
    db.execute("DELETE FROM shows WHERE id = ?", (show_id,))
    db.commit()
    flash("Show deleted.", "success")
    return redirect(url_for("admin.shows_list"))


@bp.route("/shows/<int:show_id>/add-review", methods=("POST",))
@login_required
def add_show_review(show_id):
    """A moderator pasting in a review nobody could pull from the ShowTimes
    PDF archive or an aims.ie link - same shape as a real historical_reviews
    row (adjudicator credit, citation, moderation trail), so it renders
    through the exact same show-page component, just tagged source='manual'
    so the citation reads correctly (see show_detail.html). Written straight
    to moderation_status='approved': this only reaches a moderator's own
    Edit Show screen, which is already the human review step every other
    entry point (the ShowTimes queue, a public submission) exists to reach."""
    db = get_db()
    show = db.execute(
        "SELECT shows.*, societies.name AS society_name, societies.id AS society_id "
        "FROM shows JOIN societies ON societies.id = shows.society_id WHERE shows.id = ?",
        (show_id,),
    ).fetchone()
    if show is None:
        abort(404)

    review_text = request.form.get("review_text", "").strip()
    adjudicator_id = request.form.get("adjudicator_id") or None
    source_issue = request.form.get("source_issue", "").strip() or None

    if not review_text:
        flash("Review text can't be blank.", "error")
        return redirect(url_for("admin.edit_show", show_id=show_id))
    if not show["show"]:
        flash("Add a title for this show before attaching a review.", "error")
        return redirect(url_for("admin.edit_show", show_id=show_id))
    # A show can only ever have one approved review at once in practice -
    # nothing at the schema level stops a second, but show_detail() only
    # ever renders one (see its own ORDER BY id ASC LIMIT 1, added the same
    # session this route was, after a batch re-extraction left ten shows
    # silently carrying two). Refusing here rather than silently creating
    # exactly that state again.
    already = db.execute(
        "SELECT 1 FROM historical_reviews WHERE show_id = ? AND moderation_status = 'approved'",
        (show_id,),
    ).fetchone()
    if already:
        flash("This show already has a review attached - remove it first if you need to replace it.", "error")
        return redirect(url_for("admin.edit_show", show_id=show_id))

    db.execute(
        """
        INSERT INTO historical_reviews
            (season, tier, show_raw, society_raw, adjudicator_id, review_text, source_issue,
             show_id, society_id, moderation_status, moderated_by, moderated_at, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', ?, ?, 'manual')
        """,
        (
            show["season"], show["section"], show["show"], show["society_name"], adjudicator_id,
            review_text, source_issue, show_id, show["society_id"],
            current_user()["username"], utcnow_iso(),
        ),
    )
    db.commit()
    flash("Review added.", "success")
    return redirect(url_for("admin.edit_show", show_id=show_id))


@bp.route("/shows/<int:show_id>/remove-review", methods=("POST",))
@login_required
def remove_show_review(show_id):
    """Only ever removes a manually-added review (source='manual') - a
    ShowTimes-extracted one belongs to the archive and has its own
    moderation-queue history; pulling it back off a show isn't something
    this button is for."""
    db = get_db()
    db.execute(
        "DELETE FROM historical_reviews WHERE show_id = ? AND moderation_status = 'approved' AND source = 'manual'",
        (show_id,),
    )
    db.commit()
    flash("Review removed.", "success")
    return redirect(url_for("admin.edit_show", show_id=show_id))


@bp.route("/show-links/set", methods=("POST",))
@login_required
def set_show_link():
    show = request.form.get("show", "").strip()
    url = request.form.get("url", "").strip()
    if show and url:
        get_db().execute(
            "INSERT INTO show_links (show, url, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(show) DO UPDATE SET url = excluded.url, updated_at = excluded.updated_at",
            (show, url),
        )
        get_db().commit()
        flash(f'Link set for "{show}".', "success")
    return redirect(url_for("public.titles_list"))


@bp.route("/show-links/clear", methods=("POST",))
@login_required
def clear_show_link():
    show = request.form.get("show", "").strip()
    if show:
        get_db().execute("DELETE FROM show_links WHERE show = ?", (show,))
        get_db().commit()
    return redirect(back_to(url_for("public.titles_list")))


@bp.route("/titles/<path:title>/info", methods=("GET", "POST"))
@login_required
def edit_show_info(title):
    db = get_db()
    info = db.execute("SELECT * FROM show_info WHERE show = ?", (title,)).fetchone()

    if request.method == "POST":
        synopsis = request.form.get("synopsis", "").strip() or None
        rights_url = request.form.get("rights_url", "").strip() or None
        rights_status = request.form.get("rights_status") or None
        premiere_year_raw = request.form.get("premiere_year", "").strip()
        premiere_place = request.form.get("premiere_place", "").strip() or None
        composer = request.form.get("composer", "").strip() or None
        lyricist = request.form.get("lyricist", "").strip() or None
        book_author = request.form.get("book_author", "").strip() or None
        licensing_house = request.form.get("licensing_house", "").strip() or None
        key_songs = request.form.get("key_songs", "").strip() or None

        if rights_status and rights_status not in RIGHTS_STATUSES:
            flash("Choose a valid rights status.", "error")
            return render_template(
                "admin/show_info_form.html", title=title, statuses=RIGHTS_STATUSES, form=request.form
            )

        premiere_year = None
        if premiere_year_raw:
            try:
                premiere_year = int(premiere_year_raw)
            except ValueError:
                flash("World premiere year must be a number.", "error")
                return render_template(
                    "admin/show_info_form.html", title=title, statuses=RIGHTS_STATUSES, form=request.form
                )

        db.execute(
            """
            INSERT INTO show_info (
                show, synopsis, rights_url, rights_status, premiere_year, premiere_place,
                composer, lyricist, book_author, licensing_house, key_songs, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(show) DO UPDATE SET
                synopsis = excluded.synopsis, rights_url = excluded.rights_url,
                rights_status = excluded.rights_status, premiere_year = excluded.premiere_year,
                premiere_place = excluded.premiere_place, composer = excluded.composer,
                lyricist = excluded.lyricist, book_author = excluded.book_author,
                licensing_house = excluded.licensing_house, key_songs = excluded.key_songs,
                updated_at = excluded.updated_at
            """,
            (
                title, synopsis, rights_url, rights_status, premiere_year, premiere_place,
                composer, lyricist, book_author, licensing_house, key_songs,
            ),
        )
        db.commit()
        flash("Show info updated.", "success")
        return redirect(url_for("public.title_detail", title=title))

    return render_template(
        "admin/show_info_form.html", title=title, statuses=RIGHTS_STATUSES,
        form=dict(info) if info else {},
    )


@bp.route("/titles/<path:title>/info/clear", methods=("POST",))
@login_required
def clear_show_info(title):
    get_db().execute("DELETE FROM show_info WHERE show = ?", (title,))
    get_db().commit()
    flash("Show info cleared.", "success")
    # Default lands on the title's own page, which is right when this was
    # invoked from there - but an orphaned title has no page worth landing on,
    # so /admin/data-quality passes ?next= to come back to its own list.
    return redirect(back_to(url_for("public.title_detail", title=title)))


@bp.route("/missing-posters")
@login_required
def missing_posters():
    """Upcoming shows with nothing to show on the homepage.

    Not a queue a moderator can clear alone - Darragh does not have these
    posters, the societies do. So this is a chasing list: soonest first
    (a run that opens next week is the urgent one), with each society's own
    login code surfaced where one exists, since handing that over is what
    actually lets them upload it themselves.
    """
    db = get_db()
    shows = db.execute(
        f"""
        SELECT shows.id, shows.show, shows.season, shows.opening_date, shows.closing_date,
               shows.ticket_url, societies.id AS society_id, societies.name AS society_name,
               (SELECT code FROM invite_codes
                 WHERE invite_codes.society_id = societies.id AND invite_codes.is_active = 1
                   AND (invite_codes.expires_at IS NULL OR invite_codes.expires_at >= :today)
                 ORDER BY invite_codes.created_at DESC LIMIT 1) AS society_code
        FROM shows JOIN societies ON societies.id = shows.society_id
        WHERE {MISSING_POSTER_WHERE}
        ORDER BY shows.opening_date
        """,
        missing_poster_params(),
    ).fetchall()

    # How much of the upcoming slate this actually represents - a bare "55"
    # doesn't say whether that's most of them or a handful.
    total_upcoming = db.execute(
        """
        SELECT COUNT(*) FROM shows
        WHERE moderation_status = 'approved' AND show IS NOT NULL
          AND opening_date IS NOT NULL AND opening_date >= ?
        """,
        (date.today().isoformat(),),
    ).fetchone()[0]

    # Built here, not in the template, so it reuses notify.py's SITE_URL
    # handling - url_for(..., _external=True) can't be trusted behind the
    # Cloudflare Tunnel/PrefixMiddleware setup (same reason society_detail
    # builds its copy of this link this way).
    society_login_url = notify.link(url_for("society.login"))

    return render_template(
        "admin/missing_posters.html", shows=shows, total_upcoming=total_upcoming,
        society_login_url=society_login_url,
    )
