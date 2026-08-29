from flask import abort, flash, jsonify, redirect, render_template, request, url_for

from ...auth import login_required
from ...constants import REGIONS, VENUE_TYPES
from ...db import get_db
from ...venues import (
    dismiss_venue_pair,
    dismissed_venue_pairs,
    looks_unresolved,
    merge_candidates,
    merge_venue_into,
)
from . import bp
from ._shared import URL_RE

VENUE_FIELDS = (
    "name", "town", "county", "region", "capacity", "auditorium_type",
    "latitude", "longitude", "website_url", "tech_spec_url", "notes",
    "box_office_phone", "box_office_url", "venue_type",
)
AUDITORIUM_TYPES = ["Proscenium", "Thrust", "End-on", "Flat floor", "In the round", "Other"]


@bp.route("/venues")
@login_required
def venues():
    db = get_db()
    # has_evidence: has this society got at least one of its own shows with
    # venue text recorded? shows.venue is the only place venue text lives
    # (historical_results/historical_reviews carry no venue column at all -
    # see backfill_default_venues_round2.py). A society with none isn't
    # something a moderator can fill in from the data on hand, so it's kept
    # out of the main list/progress bar entirely rather than sitting there
    # unresolved next to ones that are actually actionable.
    societies = db.execute(
        """
        SELECT s.id, s.name, s.region, s.default_venue,
               EXISTS (
                 SELECT 1 FROM shows sh
                 WHERE sh.society_id = s.id AND sh.venue IS NOT NULL AND sh.venue != ''
               ) AS has_evidence
        FROM societies s
        WHERE s.section != 'Inactive'
        ORDER BY s.region, s.name
        """
    ).fetchall()
    by_region = {r: [] for r in REGIONS}
    no_evidence = []
    for s in societies:
        if not s["default_venue"] and not s["has_evidence"]:
            no_evidence.append(s)
        else:
            by_region.setdefault(s["region"], []).append(s)
    filled_count = sum(1 for s in societies if s["default_venue"])
    actionable_total = len(societies) - len(no_evidence)
    return render_template(
        "admin/venues.html", by_region=by_region, regions=REGIONS,
        no_evidence=no_evidence, total=actionable_total, filled_count=filled_count,
    )


@bp.route("/venues/save", methods=("POST",))
@login_required
def save_venue():
    db = get_db()
    society_id = request.form.get("society_id", type=int)
    if not society_id:
        return jsonify(ok=False, error="Missing society_id"), 400
    venue = request.form.get("venue", "").strip() or None
    updated = db.execute(
        "UPDATE societies SET default_venue = ? WHERE id = ?", (venue, society_id)
    ).rowcount
    db.commit()
    if not updated:
        return jsonify(ok=False, error="Society not found"), 404
    return jsonify(ok=True, venue=venue)


@bp.route("/venue-directory")
@login_required
def venue_directory():
    """Every real venue on record, with the merge queue up front.

    Distinct from /admin/venues, which is the per-society default_venue
    backfill - this is the venues table itself (see schema.sql): the thing
    /venues is built on and the thing a capacity or a map pin hangs off.
    """
    db = get_db()

    rows = db.execute(
        """
        SELECT venues.*,
               (SELECT COUNT(*) FROM shows WHERE shows.venue_id = venues.id) AS productions,
               (SELECT COUNT(DISTINCT society_id) FROM shows WHERE shows.venue_id = venues.id) AS societies,
               (SELECT GROUP_CONCAT(DISTINCT venue) FROM shows WHERE shows.venue_id = venues.id) AS spellings
          FROM venues
         ORDER BY productions DESC, name
        """
    ).fetchall()

    # One pass over the whole list, not a lookup per row - the same O(n^2)
    # helper called inside an admin list loop is what caused a live 524 once
    # already (see ROADMAP, 19 Aug).
    suggestions = merge_candidates(rows, dismissed=dismissed_venue_pairs(db))
    by_id = {r["id"]: r for r in rows}

    entries = []
    for row in rows:
        entry = dict(row)
        entry["unresolved"] = looks_unresolved(row["name"])
        entry["suggestions"] = [by_id[i] for i in suggestions.get(row["id"], [])]
        entry["detail_filled"] = sum(
            1 for f in ("town", "county", "region", "capacity", "auditorium_type",
                        "latitude", "website_url", "tech_spec_url")
            if row[f] is not None
        )
        entries.append(entry)

    # Three groups, not two. Lumping the place-name entries in with the merge
    # suggestions made a 104-item queue out of a 51-item job, and most of that
    # 104 can never be cleared - a show recorded only as "Cork" can't be traced
    # to a building without evidence that doesn't exist. Same
    # permanent-vs-fixable distinction the dashboard's own counters draw.
    duplicates = [e for e in entries if e["suggestions"]]
    place_names = [e for e in entries if e["unresolved"] and not e["suggestions"]]
    settled = [e for e in entries if not (e["suggestions"] or e["unresolved"])]
    return render_template(
        "admin/venue_directory.html", duplicates=duplicates, place_names=place_names,
        settled=settled, total=len(entries),
    )


@bp.route("/venue-directory/<int:venue_id>/edit", methods=("GET", "POST"))
@login_required
def edit_venue_record(venue_id):
    db = get_db()
    venue = db.execute("SELECT * FROM venues WHERE id = ?", (venue_id,)).fetchone()
    if venue is None:
        abort(404)

    if request.method == "POST":
        fields = {f: request.form.get(f, "").strip() or None for f in VENUE_FIELDS}
        errors = []
        if not fields["name"]:
            errors.append("A venue needs a name.")
        if fields["region"] and fields["region"] not in REGIONS:
            errors.append("That isn't one of the AIMS regions.")
        if fields["venue_type"] and fields["venue_type"] not in VENUE_TYPES:
            errors.append("That isn't one of the venue types.")
        for numeric, label, cast in (("capacity", "Capacity", int),
                                     ("latitude", "Latitude", float),
                                     ("longitude", "Longitude", float)):
            if fields[numeric] is not None:
                try:
                    fields[numeric] = cast(fields[numeric])
                except ValueError:
                    errors.append(f"{label} must be a number.")
        for url_field, label in (
            ("website_url", "Website"), ("tech_spec_url", "Technical spec"), ("box_office_url", "Box office"),
        ):
            if fields[url_field] and not URL_RE.match(fields[url_field]):
                errors.append(f"{label} must be a full http(s) link.")
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template(
                "admin/venue_form.html", venue=venue, form=request.form,
                regions=REGIONS, auditorium_types=AUDITORIUM_TYPES, venue_types=VENUE_TYPES,
            )

        assignments = ", ".join(f"{f} = :{f}" for f in VENUE_FIELDS)
        db.execute(
            f"UPDATE venues SET {assignments}, updated_at = datetime('now') WHERE id = :id",
            dict(fields, id=venue_id),
        )
        db.commit()
        flash(f'Saved "{fields["name"]}".', "success")
        return redirect(url_for("admin.venue_directory"))

    return render_template(
        "admin/venue_form.html", venue=venue, form=dict(venue),
        regions=REGIONS, auditorium_types=AUDITORIUM_TYPES, venue_types=VENUE_TYPES,
    )


@bp.route("/venue-directory/merge", methods=("POST",))
@login_required
def merge_venue_records():
    """Fold one venue into another: the same building recorded under two
    spellings. The merge itself is merge_venue_into() in app/venues.py, shared
    with enrich_venues.py so a merge means the same thing however it's applied;
    this route is the moderator's confirmation of a pair the suggestion queue
    only guessed at."""
    db = get_db()
    source_id = request.form.get("source_id", type=int)
    target_id = request.form.get("target_id", type=int)
    if not source_id or not target_id or source_id == target_id:
        abort(400)
    try:
        source_name, target_name = merge_venue_into(db, source_id, target_id)
    except LookupError:
        abort(404)
    db.commit()
    flash(f'Merged "{source_name}" into "{target_name}".', "success")
    return redirect(url_for("admin.venue_directory"))


@bp.route("/venue-directory/dismiss", methods=("POST",))
@login_required
def dismiss_venue_match():
    """"These are two different buildings." merge_candidates() is deliberately
    loose (see its docstring) and proposes real non-matches - the Galway,
    Ballinasloe and Claremorris Town Hall Theatres among them. Without a way
    to say no, those sit in the queue forever and its count can never reach
    zero, which is the permanent-vs-fixable trap the dashboard's other
    counters go out of their way to avoid."""
    db = get_db()
    venue_a = request.form.get("venue_a_id", type=int)
    venue_b = request.form.get("venue_b_id", type=int)
    if not venue_a or not venue_b or venue_a == venue_b:
        abort(400)
    names = {
        r["id"]: r["name"]
        for r in db.execute(
            "SELECT id, name FROM venues WHERE id IN (?, ?)", (venue_a, venue_b)
        )
    }
    if len(names) != 2:
        abort(404)
    dismiss_venue_pair(db, venue_a, venue_b)
    db.commit()
    flash(f'"{names[venue_a]}" and "{names[venue_b]}" marked as different venues.', "success")
    return redirect(url_for("admin.venue_directory"))
