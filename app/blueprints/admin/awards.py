import re

from flask import abort, flash, redirect, render_template, request, url_for

from ... import productions_build
from ...auth import login_required
from ...constants import AWARD_RESULTS
from ...db import get_db
from ...search import escape_like
from ...similarity import find_close_title
from . import bp


def _award_categories(db):
    return [
        r[0] for r in db.execute(
            "SELECT DISTINCT category_name FROM historical_results "
            "WHERE category_name IS NOT NULL ORDER BY category_name"
        ).fetchall()
    ]


def _read_award_form(form):
    category = form.get("category", "")
    if category == "__other__":
        category = form.get("category_other", "").strip()
    return {
        "year": form.get("year", "").strip(),
        "tier": form.get("tier") or None,
        "category_name": category or None,
        "result": form.get("result") or None,
        "show": form.get("show", "").strip() or None,
        "society_id": form.get("society_id", "").strip() or None,
        "nominee_name": form.get("nominee_name", "").strip() or None,
        "role": form.get("role", "").strip() or None,
        "reason": form.get("reason", "").strip() or None,
    }


def _validate_award(fields):
    errors = []
    if not fields["year"].isdigit():
        errors.append("Enter a valid year.")
    if fields["tier"] and fields["tier"] not in ("Gilbert", "Sullivan"):
        errors.append("Choose a valid tier.")
    if fields["result"] and fields["result"] not in AWARD_RESULTS:
        errors.append("Choose a valid result.")
    if not fields["category_name"]:
        errors.append("Enter a category.")
    return errors


@bp.route("/awards")
@login_required
def awards_list():
    db = get_db()
    q = request.args.get("q", "").strip()
    year = request.args.get("year", "").strip()
    category = request.args.get("category", "")
    tier = request.args.get("tier", "")
    result = request.args.get("result", "")
    unmatched = request.args.get("unmatched", "")

    years = [r[0] for r in db.execute("SELECT DISTINCT year FROM historical_results ORDER BY year DESC").fetchall()]
    categories = _award_categories(db)

    query = """
        SELECT historical_results.*, societies.id AS resolved_society_id
        FROM historical_results
        LEFT JOIN societies ON societies.id = historical_results.society_id
        WHERE 1=1
    """
    params = []
    if year.isdigit():
        query += " AND year = ?"
        params.append(int(year))
    if category:
        query += " AND category_name = ?"
        params.append(category)
    if tier in ("Gilbert", "Sullivan"):
        query += " AND tier = ?"
        params.append(tier)
    if result in AWARD_RESULTS:
        query += " AND result = ?"
        params.append(result)
    if unmatched:
        query += " AND historical_results.society_name IS NOT NULL AND historical_results.society_id IS NULL"
    if q:
        query += """ AND (society_name LIKE ? ESCAPE '\\' OR show LIKE ? ESCAPE '\\'
                     OR nominee_name LIKE ? ESCAPE '\\' OR reason LIKE ? ESCAPE '\\')"""
        escaped = escape_like(q)
        like = f"%{escaped}%"
        params += [like, like, like, like]
    query += " ORDER BY year DESC, category_name, society_name"

    rows = db.execute(query, params).fetchall()

    return render_template(
        "admin/awards_list.html", rows=rows, years=years, categories=categories, results=AWARD_RESULTS,
        selected_year=year, selected_category=category, selected_tier=tier, selected_result=result,
        unmatched=unmatched, q=q,
    )


BULK_AWARD_ROWS = 5


@bp.route("/awards/bulk", methods=("GET", "POST"))
@login_required
def bulk_award():
    db = get_db()
    societies = db.execute("SELECT id, name FROM societies ORDER BY name").fetchall()
    categories = _award_categories(db)

    if request.method == "POST":
        year = request.form.get("year", "").strip()
        tier = request.form.get("tier") or None
        category = request.form.get("category", "")
        if category == "__other__":
            category = request.form.get("category_other", "").strip()
        category = category or None
        winner_row = request.form.get("winner_row", "")

        errors = []
        if not year.isdigit():
            errors.append("Enter a valid year.")
        if tier and tier not in ("Gilbert", "Sullivan"):
            errors.append("Choose a valid tier.")
        if not category:
            errors.append("Enter a category.")

        rows = []
        for i in range(BULK_AWARD_ROWS):
            society_id = request.form.get(f"society_id_{i}", "").strip() or None
            show = request.form.get(f"show_{i}", "").strip() or None
            nominee_name = request.form.get(f"nominee_name_{i}", "").strip() or None
            role = request.form.get(f"role_{i}", "").strip() or None

            if not any((society_id, show, nominee_name, role)):
                rows.append(None)
                continue

            society_name = None
            if society_id:
                society_row = db.execute("SELECT name FROM societies WHERE id = ?", (society_id,)).fetchone()
                if society_row is None:
                    errors.append(f"Row {i + 1}: choose a valid society.")
                else:
                    society_name = society_row["name"]

            result = "Winner" if winner_row == str(i) else "Nominee"
            rows.append({
                "society_id": society_id, "society_name": society_name, "show": show,
                "nominee_name": nominee_name, "role": role, "result": result,
            })

        filled_rows = [r for r in rows if r is not None]
        if not filled_rows:
            errors.append("Fill in at least one row.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/award_bulk_form.html", societies=societies, categories=categories,
                bulk_rows=BULK_AWARD_ROWS, form=request.form,
            )

        for row in filled_rows:
            db.execute(
                """
                INSERT INTO historical_results (
                    year, tier, category_name, result, show, society_name, society_id,
                    nominee_name, role, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual')
                """,
                (
                    int(year), tier, category, row["result"], row["show"],
                    row["society_name"], row["society_id"], row["nominee_name"], row["role"],
                ),
            )
        db.commit()
        flash(f"Added {len(filled_rows)} award record{'s' if len(filled_rows) != 1 else ''}.", "success")
        return redirect(url_for("admin.awards_list"))

    return render_template(
        "admin/award_bulk_form.html", societies=societies, categories=categories,
        bulk_rows=BULK_AWARD_ROWS, form={},
    )


HISTORICAL_PRODUCTION_LINE_RE = re.compile(r"^\s*(\d{4})\s+(.+?)\s*$")
HISTORICAL_PRODUCTION_NOTE_RE = re.compile(r"^(.*?)\s*\(([^()]+)\)\s*$")
# See bulk_historical_productions' docstring - "autumn" (Jul-Dec) shows are
# recorded under the following calendar year; "spring" (Jan-Jun) shows and
# already-AIMS-year input both need no adjustment.
HISTORICAL_YEAR_OFFSETS = {"autumn": 1, "spring": 0, "exact": 0}


@bp.route("/historical-productions/bulk", methods=("GET", "POST"))
@login_required
def bulk_historical_productions():
    """Paste a society's own "previous productions" list (one "YEAR Title"
    per line, straight off their website) and add whichever aren't already
    on record as bare historical_results rows - no award/category attached,
    just "this happened". Existing exact (year, show, society) rows are
    skipped rather than duplicated, so the same list can be re-pasted safely
    if it's ever extended.

    AIMS's own year convention is the season's *ending* calendar year, not
    the year the show actually opened (matches how season "23/24" maps to
    SHOWS_COVERAGE_START_YEAR = 2024) - for a society that stages its show
    July-December, that's one year after the production (season "25/26"
    ends in 2026, so an Oct 2025 show is recorded as 2026); for a society
    that stages Jan-June, the production year already IS the AIMS year, no
    adjustment needed. This is a per-society (sometimes per-show) fact, not
    a universal +1 - HISTORICAL_YEAR_OFFSETS below turns the moderator's
    plain-language choice into the right arithmetic."""
    db = get_db()
    societies = db.execute("SELECT id, name FROM societies ORDER BY name").fetchall()

    if request.method == "POST":
        society_id = request.form.get("society_id", "").strip()
        lines_raw = request.form.get("lines", "")
        year_convention = request.form.get("year_convention", "autumn")
        if year_convention not in HISTORICAL_YEAR_OFFSETS:
            year_convention = "autumn"

        society = db.execute("SELECT id, name FROM societies WHERE id = ?", (society_id,)).fetchone()
        if society is None:
            flash("Choose a valid society.", "error")
            return render_template(
                "admin/historical_bulk_form.html", societies=societies, form=request.form
            )

        inserted, skipped, unparsed = 0, 0, []
        for raw_line in lines_raw.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = HISTORICAL_PRODUCTION_LINE_RE.match(line)
            if not match:
                unparsed.append(raw_line)
                continue

            year = int(match.group(1))
            title = match.group(2)
            note = None
            note_match = HISTORICAL_PRODUCTION_NOTE_RE.match(title)
            if note_match:
                title, note = note_match.group(1).strip(), note_match.group(2).strip()
            if not title:
                unparsed.append(raw_line)
                continue

            stored_year = year + HISTORICAL_YEAR_OFFSETS[year_convention]

            # Matches ANY existing row for this (year, show, society) - not just
            # a bare one. A society with award-archive coverage for some years
            # (e.g. a Best Overall Show nomination) already has that production
            # on record; inserting a second, bare "this happened" row for the
            # same show would double-count it in every production-count stat.
            already_present = db.execute(
                """
                SELECT 1 FROM historical_results
                WHERE year = ? AND show = ? AND society_id = ?
                """,
                (stored_year, title, society["id"]),
            ).fetchone()
            # Also check the shows table (23/24+) - it has no "year" column,
            # just opening_date, and this tool has no reliable way to know
            # which season a bare "YEAR Title" line would land in, so this
            # matches on title + either the typed or offset-adjusted year
            # appearing anywhere in that show's opening_date. A production
            # already recorded there shouldn't also get a bare
            # historical_results row - same show, counted twice.
            if not already_present:
                already_present = db.execute(
                    """
                    SELECT 1 FROM shows
                    WHERE society_id = ? AND show = ?
                      AND (substr(opening_date, 1, 4) = ? OR substr(opening_date, 1, 4) = ?)
                    """,
                    (society["id"], title, str(year), str(stored_year)),
                ).fetchone()
            if already_present:
                skipped += 1
                continue

            db.execute(
                """
                INSERT INTO historical_results (year, show, society_name, society_id, reason, source)
                VALUES (?, ?, ?, ?, ?, 'manual')
                """,
                (stored_year, title, society["name"], society["id"], note),
            )
            inserted += 1

        db.commit()
        flash(
            f"Added {inserted} production{'s' if inserted != 1 else ''} for {society['name']}"
            f"{f', skipped {skipped} already on record' if skipped else ''}.",
            "success" if inserted else "warning",
        )
        if unparsed:
            flash(
                "Couldn't parse " + str(len(unparsed)) + " line(s) (expected \"YEAR Title\") - "
                "nothing else was skipped because of these: " + "; ".join(unparsed[:5])
                + ("..." if len(unparsed) > 5 else ""),
                "error",
            )
        return redirect(url_for("admin.bulk_historical_productions"))

    return render_template("admin/historical_bulk_form.html", societies=societies, form={})


@bp.route("/awards/new", methods=("GET", "POST"))
@login_required
def new_award():
    db = get_db()
    societies = db.execute("SELECT id, name FROM societies ORDER BY name").fetchall()
    categories = _award_categories(db)

    if request.method == "POST":
        fields = _read_award_form(request.form)
        errors = _validate_award(fields)

        society_id = fields["society_id"]
        society_name = None
        if society_id:
            society_row = db.execute("SELECT name FROM societies WHERE id = ?", (society_id,)).fetchone()
            if society_row is None:
                errors.append("Choose a valid society.")
            else:
                society_name = society_row["name"]

        similar_title = None
        if fields["show"] and not request.form.get("confirm_new_title"):
            similar_title = find_close_title(db, fields["show"])
            if similar_title:
                flash(
                    f'A show already on record is titled "{similar_title}" - if that\'s this '
                    "production, use that exact spelling. If it's genuinely a different show, "
                    "tick the box below and save again.",
                    "warning",
                )

        if errors or similar_title:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/award_form.html", societies=societies, categories=categories, results=AWARD_RESULTS,
                form=request.form, similar_title=similar_title, mode="new",
            )

        db.execute(
            """
            INSERT INTO historical_results (
                year, tier, category_name, result, show, society_name, society_id,
                nominee_name, role, reason, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual')
            """,
            (
                int(fields["year"]), fields["tier"], fields["category_name"], fields["result"],
                fields["show"], society_name, society_id,
                fields["nominee_name"], fields["role"], fields["reason"],
            ),
        )
        db.commit()
        flash("Award result added.", "success")
        return redirect(url_for("admin.awards_list"))

    return render_template(
        "admin/award_form.html", societies=societies, categories=categories, results=AWARD_RESULTS,
        form={}, mode="new",
    )


@bp.route("/awards/<int:award_id>/edit", methods=("GET", "POST"))
@login_required
def edit_award(award_id):
    db = get_db()
    award = db.execute("SELECT * FROM historical_results WHERE id = ?", (award_id,)).fetchone()
    if award is None:
        abort(404)

    societies = db.execute("SELECT id, name FROM societies ORDER BY name").fetchall()
    categories = _award_categories(db)

    if request.method == "POST":
        fields = _read_award_form(request.form)
        errors = _validate_award(fields)

        society_id = fields["society_id"]
        society_name = None
        if society_id:
            society_row = db.execute("SELECT name FROM societies WHERE id = ?", (society_id,)).fetchone()
            if society_row is None:
                errors.append("Choose a valid society.")
            else:
                society_name = society_row["name"]

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/award_form.html", societies=societies, categories=categories, results=AWARD_RESULTS,
                award=award, form=request.form, mode="edit",
            )

        # Editing through this form - regardless of where the row originally
        # came from - makes it 'manual' from now on, so a future re-run of
        # import_awards.py can never silently discard the edit.
        db.execute(
            """
            UPDATE historical_results SET
                year = ?, tier = ?, category_name = ?, result = ?, show = ?,
                society_name = ?, society_id = ?, nominee_name = ?, role = ?, reason = ?, source = 'manual'
            WHERE id = ?
            """,
            (
                int(fields["year"]), fields["tier"], fields["category_name"], fields["result"],
                fields["show"], society_name, society_id,
                fields["nominee_name"], fields["role"], fields["reason"], award_id,
            ),
        )
        # An edited year/show/society moves this record to a different
        # production, and historical_results has no updated_at column for the
        # productions freshness check to spot the change on its own.
        productions_build.mark_stale(db)
        db.commit()
        flash("Award result updated.", "success")
        return redirect(url_for("admin.awards_list"))

    return render_template(
        "admin/award_form.html", societies=societies, categories=categories, results=AWARD_RESULTS,
        award=award, form=dict(award), mode="edit",
    )


@bp.route("/awards/<int:award_id>/delete", methods=("POST",))
@login_required
def delete_award(award_id):
    db = get_db()
    db.execute("DELETE FROM historical_results WHERE id = ?", (award_id,))
    db.commit()
    flash("Award result deleted.", "success")
    return redirect(url_for("admin.awards_list"))
