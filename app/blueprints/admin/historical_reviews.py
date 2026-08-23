import sqlite3
from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for

import society_names

from ... import productions_build
from ...auth import current_user, login_required
from ...constants import SHOW_SECTIONS
from ...db import get_db
from ...dedupe import find_candidates
from ...season import historical_results_year
from ...similarity import normalize_title
from . import bp

HISTORICAL_RESULTS_MATCH_THRESHOLD = 0.85
# Deliberately lower than it looks: quality is enforced by
# SOCIETY_DISTINCTIVE_THRESHOLD below, which is the check that actually
# distinguishes a real name variant from a different society. This is only a
# floor against absurd whole-string matches. It used to be 0.85, which threw
# away a large class of genuine matches, since this archive abbreviates
# constantly - "Dun Laoghaire Mus. & Dram. Society" scores just 0.84 against
# its own real record, "St Patrick's Hall MS, Strabane" 0.81.
SOCIETY_MATCH_THRESHOLD = 0.70

# Whether two society spellings name the same society - shared with
# extract_historical_reviews.py, which needs the identical judgement on the
# other side of the pipeline (see society_names.py for why a whole-string
# ratio can't do this).
SOCIETY_DISTINCTIVE_THRESHOLD = society_names.DISTINCTIVE_THRESHOLD
_society_distinctive_score = society_names.distinctive_score


def categorize_pending_reviews(db):
    """Groups every pending review by *why* it's stuck, instead of one flat
    list a moderator has to read every row of to find the ones actually
    worth their attention:
      - needs_society: no society matched at all - needs Edit fields.
      - conflict: shares a (society, season, show) natural key with another
        still-pending review (a production extracted twice from two
        different source issues - confirmed, 9 real cases in the archive) -
        approving one links it to a fresh skeleton show; approving the
        other should link to that same show instead of erroring (see
        _approve_historical_review_row), but the two need to actually be
        looked at together first, since one might be a better transcription
        of the same review than the other.
      - history_match: no *existing* shows row (there rarely is one before
        23/24 - see SHOWS_COVERAGE_START_YEAR), but a plausible match in
        the older historical_results awards archive - approving as-is would
        create a skeleton show whose title doesn't line up with that
        record, orphaning the review from the production's real award
        history instead of enriching it. Needs a quick title confirm
        first (see apply_historical_results_match below), not blocked
        from ever approving, just from *bulk*-approving blind.
      - ready: everything else - either no plausible existing record at
        all (a brand new skeleton is exactly right), or already matched to
        a real shows row directly. Safe to bulk-approve.
    Returns {category: [review dict, ...]}, each dict carrying the row's
    own columns plus (for history_match) a 'history_candidates' list."""
    reviews = db.execute(
        """
        SELECT historical_reviews.*, adjudicators.name AS adjudicator_name,
               societies.name AS matched_society_name, shows.show AS matched_show_title
        FROM historical_reviews
        LEFT JOIN adjudicators ON adjudicators.id = historical_reviews.adjudicator_id
        LEFT JOIN societies ON societies.id = historical_reviews.society_id
        LEFT JOIN shows ON shows.id = historical_reviews.show_id
        WHERE historical_reviews.moderation_status = 'pending'
        ORDER BY historical_reviews.season, historical_reviews.tier, historical_reviews.society_raw
        """
    ).fetchall()

    natural_key_counts = {}
    for r in reviews:
        if r["society_id"] is not None:
            key = (r["society_id"], r["season"], r["show_raw"])
            natural_key_counts[key] = natural_key_counts.get(key, 0) + 1

    society_candidates_by_raw = find_society_candidates_batch(
        db, (r["society_raw"] for r in reviews if r["society_id"] is None)
    )

    grouped = {"needs_society": [], "conflict": [], "history_match": [], "ready": []}
    for r in reviews:
        entry = dict(r)
        if r["society_id"] is None:
            entry["society_candidates"] = [
                (name, score, section)
                for name, score, section in society_candidates_by_raw.get(r["society_raw"], [])
                if score >= SOCIETY_MATCH_THRESHOLD
            ]
            grouped["needs_society"].append(entry)
            continue
        key = (r["society_id"], r["season"], r["show_raw"])
        if natural_key_counts[key] > 1:
            grouped["conflict"].append(entry)
            continue
        if r["show_id"] is None:
            candidates = [
                (title, score) for title, score in
                find_historical_results_candidates(db, r["society_id"], r["season"], r["show_raw"])
                if title != r["show_raw"] and score >= HISTORICAL_RESULTS_MATCH_THRESHOLD
            ]
            if candidates:
                entry["history_candidates"] = candidates
                grouped["history_match"].append(entry)
                continue
        grouped["ready"].append(entry)
    return grouped


def group_needs_society(reviews):
    """Collapses the needs_society pile into one entry per distinct
    society_raw, so a printed name that appears across several reviews
    ('Fusion Theatre' turns up 8 times) is matched once for the whole group
    instead of review-by-review. Matching one at a time was the single most
    tedious part of working this queue - roughly a third of the pile shares
    its society_raw with at least one other review.

    Returns [{society_raw, count, review_ids, candidates}, ...], largest
    group first (most tedium saved per click), then alphabetically. Groups
    with no suggestion at all are still listed - they're exactly the ones
    needing a hand-typed name, and hiding them would hide real work."""
    groups = {}
    for r in reviews:
        raw = r["society_raw"] or ""
        g = groups.setdefault(raw, {
            "society_raw": raw,
            "count": 0,
            "review_ids": [],
            "candidates": r.get("society_candidates") or [],
        })
        g["count"] += 1
        g["review_ids"].append(r["id"])
    return sorted(groups.values(), key=lambda g: (-g["count"], g["society_raw"].lower()))


@bp.route("/historical-reviews")
@login_required
def historical_reviews_queue():
    db = get_db()
    grouped = categorize_pending_reviews(db)
    total_pending = sum(len(v) for v in grouped.values())
    society_groups = group_needs_society(grouped["needs_society"])
    return render_template(
        "admin/historical_reviews_queue.html", grouped=grouped, total_pending=total_pending,
        bulk_approvable_count=len(grouped["ready"]),
        society_groups=society_groups,
        multi_society_groups=[g for g in society_groups if g["count"] > 1],
    )


def _approve_historical_review_row(db, review, username):
    """Shared by the single-review and bulk approve routes. Assumes the
    caller already checked review['society_id'] is set - the bulk route only
    ever selects rows that guarantee this. Doesn't commit; the caller does,
    once per request (a single commit for a whole bulk batch, not one per
    row)."""
    show_id = review["show_id"]
    if show_id is None:
        # Two reviews of the same real production (society, season, show)
        # sometimes got extracted twice from two different source issues (a
        # near-identical reprint - confirmed, 9 real cases in the archive) -
        # approving the second one should link it to the skeleton the first
        # one already created, not try to create a second, colliding row.
        # Checked by the same natural key the unique index enforces, so this
        # always finds it if it exists.
        existing = db.execute(
            "SELECT id FROM shows WHERE society_id = ? AND season = ? AND show = ?",
            (review["society_id"], review["season"], review["show_raw"]),
        ).fetchone()
        if existing is not None:
            show_id = existing["id"]
        else:
            # No existing shows/historical_results row for this production -
            # a minimal "skeleton" row (source='historical') gives the
            # review a real page to live on, same idea as a society
            # backfilling their own history, just moderator-triggered.
            # Deliberately excluded from every stats/leaderboard query (see
            # schema.sql) so it can't double-count.
            society = db.execute("SELECT region FROM societies WHERE id = ?", (review["society_id"],)).fetchone()
            show_id = db.execute(
                """
                INSERT INTO shows (society_id, season, region, section, show, source, moderation_status)
                VALUES (?, ?, ?, ?, ?, 'historical', 'approved')
                """,
                (review["society_id"], review["season"], society["region"], review["tier"], review["show_raw"]),
            ).lastrowid

    db.execute(
        """
        UPDATE historical_reviews
        SET show_id = ?, moderation_status = 'approved', moderated_by = ?, moderated_at = ?
        WHERE id = ?
        """,
        (show_id, username, datetime.utcnow().isoformat(), review["id"]),
    )


@bp.route("/historical-reviews/<int:review_id>/approve", methods=("POST",))
@login_required
def approve_historical_review(review_id):
    db = get_db()
    user = current_user()
    review = db.execute(
        "SELECT * FROM historical_reviews WHERE id = ? AND moderation_status = 'pending'", (review_id,)
    ).fetchone()
    if review is None:
        abort(404)
    if review["society_id"] is None:
        flash("This review needs a society matched (use Edit fields) before it can be approved.", "error")
        return redirect(url_for("admin.historical_reviews_queue"))

    _approve_historical_review_row(db, review, user["username"])
    db.commit()
    flash("Review approved and published.", "success")
    return redirect(url_for("admin.historical_reviews_queue"))


@bp.route("/historical-reviews/bulk-approve", methods=("POST",))
@login_required
def bulk_approve_historical_reviews():
    """Approves every review in the 'ready' category (see
    categorize_pending_reviews) - a confident society match, and either no
    plausible existing record at all or an already-exact show match, so
    there's genuinely nothing left for a moderator to individually decide.
    Reviews needing a society picked, sharing a natural key with another
    pending review, or matching the older awards archive under a different
    title are never touched here - each of those needs an actual look."""
    db = get_db()
    user = current_user()
    reviews = categorize_pending_reviews(db)["ready"]
    approved = 0
    conflicts = 0
    for review in reviews:
        # categorize_pending_reviews already excludes reviews sharing a
        # natural key with another *pending* one, so a collision here would
        # only happen from something outside this batch (a genuine race, or
        # a show approved through a different path since the page loaded) -
        # rare, but the per-row SAVEPOINT still means one such collision
        # leaves that single review pending instead of 500ing the batch.
        db.execute("SAVEPOINT bulk_approve_row")
        try:
            _approve_historical_review_row(db, review, user["username"])
        except sqlite3.IntegrityError:
            db.execute("ROLLBACK TO SAVEPOINT bulk_approve_row")
            conflicts += 1
        else:
            db.execute("RELEASE SAVEPOINT bulk_approve_row")
            approved += 1
    db.commit()
    message = f"{approved} review{'s' if approved != 1 else ''} approved and published."
    if conflicts:
        message += (
            f" {conflicts} left pending - each already shares a show with another approved "
            "review and needs a moderator to pick which one is right."
        )
    flash(message, "success")
    return redirect(url_for("admin.historical_reviews_queue"))


@bp.route("/historical-reviews/<int:review_id>/apply-title-match", methods=("POST",))
@login_required
def apply_historical_review_title_match(review_id):
    """One-click accept for a history_match suggestion (see
    categorize_pending_reviews) - corrects show_raw to the awards archive's
    own title for the same production, so the skeleton show this creates on
    approval lines up with that existing record instead of forking a
    second, differently-titled entry for it. Doesn't approve on its own -
    same separation as Edit fields, where fixing the data and publishing
    it are two distinct steps."""
    db = get_db()
    review = db.execute(
        "SELECT * FROM historical_reviews WHERE id = ? AND moderation_status = 'pending'", (review_id,)
    ).fetchone()
    if review is None:
        abort(404)
    title = request.form.get("title", "").strip()
    if not title:
        abort(400)

    show_id = match_show_for_edit(db, review["society_id"], review["season"], title)
    flag = None if show_id is not None else ("no_show_match" if review["society_id"] is not None else "needs_check")
    db.execute(
        "UPDATE historical_reviews SET show_raw = ?, show_id = ?, flag = ? WHERE id = ?",
        (title, show_id, flag, review_id),
    )
    db.commit()
    flash(f'Title corrected to "{title}" - ready to approve.', "success")
    return redirect(url_for("admin.historical_reviews_queue"))


@bp.route("/historical-reviews/<int:review_id>/apply-society-match", methods=("POST",))
@login_required
def apply_historical_review_society_match(review_id):
    """One-click accept for a needs_society suggestion (see
    categorize_pending_reviews/find_society_candidates_batch) - matches a review
    whose printed society name has a real spelling/punctuation variant
    against the current record ("Harold's Cross Tallaght Musical Society"
    vs "Harolds Cross Tallaght Musical Society", the case that prompted
    this - a missing apostrophe) without a moderator having to type the
    correct name in by hand via Edit fields. Doesn't approve on its own,
    same separation as the title-match equivalent."""
    db = get_db()
    review = db.execute(
        "SELECT * FROM historical_reviews WHERE id = ? AND moderation_status = 'pending'", (review_id,)
    ).fetchone()
    if review is None:
        abort(404)
    name = request.form.get("name", "").strip()
    if not name:
        abort(400)
    society = db.execute("SELECT id FROM societies WHERE name = ?", (name,)).fetchone()
    if society is None:
        abort(400)

    show_id = match_show_for_edit(db, society["id"], review["season"], review["show_raw"])
    flag = None if show_id is not None else "no_show_match"
    db.execute(
        "UPDATE historical_reviews SET society_id = ?, show_id = ?, flag = ? WHERE id = ?",
        (society["id"], show_id, flag, review_id),
    )
    db.commit()
    flash(f'Society matched to "{name}" - ready to approve.', "success")
    return redirect(url_for("admin.historical_reviews_queue"))


@bp.route("/historical-reviews/bulk-apply-society-match", methods=("POST",))
@login_required
def bulk_apply_historical_review_society_match():
    """Applies one society match to every pending review sharing the same
    printed society_raw (see group_needs_society) - the same per-review work
    apply_historical_review_society_match does, just not once per review.
    Matched on society_raw rather than a list of ids so it can't silently
    act on a review that changed category since the page was rendered; each
    row still gets its own show match looked up, since that depends on the
    review's own season/show_raw, not on the society alone. Sets the society
    only - nothing is approved here, same separation as everywhere else in
    this queue."""
    db = get_db()
    society_raw = request.form.get("society_raw", "").strip()
    name = request.form.get("name", "").strip()
    if not society_raw or not name:
        abort(400)
    society = db.execute("SELECT id FROM societies WHERE name = ?", (name,)).fetchone()
    if society is None:
        abort(400)

    reviews = db.execute(
        """
        SELECT * FROM historical_reviews
        WHERE moderation_status = 'pending' AND society_id IS NULL AND society_raw = ?
        """,
        (society_raw,),
    ).fetchall()
    for review in reviews:
        show_id = match_show_for_edit(db, society["id"], review["season"], review["show_raw"])
        db.execute(
            "UPDATE historical_reviews SET society_id = ?, show_id = ?, flag = ? WHERE id = ?",
            (society["id"], show_id, None if show_id is not None else "no_show_match", review["id"]),
        )
    db.commit()
    n = len(reviews)
    flash(f'Matched {n} review{"" if n == 1 else "s"} to "{name}" - ready to approve.', "success")
    return redirect(url_for("admin.historical_reviews_queue"))


@bp.route("/historical-reviews/<int:review_id>/reject", methods=("POST",))
@login_required
def reject_historical_review(review_id):
    db = get_db()
    user = current_user()
    db.execute(
        """
        UPDATE historical_reviews
        SET moderation_status = 'rejected', moderated_by = ?, moderated_at = ?
        WHERE id = ? AND moderation_status = 'pending'
        """,
        (user["username"], datetime.utcnow().isoformat(), review_id),
    )
    db.commit()
    flash("Review skipped.", "success")
    return redirect(url_for("admin.historical_reviews_queue"))


@bp.route("/historical-reviews/<int:review_id>/edit", methods=("GET", "POST"))
@login_required
def edit_historical_review(review_id):
    db = get_db()
    review = db.execute(
        "SELECT * FROM historical_reviews WHERE id = ? AND moderation_status = 'pending'", (review_id,)
    ).fetchone()
    if review is None:
        abort(404)

    if request.method == "POST":
        season = request.form.get("season", "").strip()
        tier = request.form.get("tier") or None
        show_raw = request.form.get("show_raw", "").strip()
        society_raw = request.form.get("society_raw", "").strip()
        society_id = request.form.get("society_id") or None
        review_text = request.form.get("review_text", "").strip()
        source_issue = request.form.get("source_issue", "").strip() or None

        errors = []
        if not season:
            errors.append("Season is required.")
        if tier is not None and tier not in SHOW_SECTIONS:
            errors.append("Choose a valid tier.")
        if not show_raw:
            errors.append("Show title is required.")
        if not society_raw:
            errors.append("Society name is required.")
        if not review_text:
            errors.append("Review text is required.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/historical_review_edit.html", review=review, societies=_all_societies(db), form=request.form,
            )

        society_id = int(society_id) if society_id else None
        show_id = match_show_for_edit(db, society_id, season, show_raw)
        flag = None if show_id is not None else ("no_show_match" if society_id is not None else "needs_check")

        db.execute(
            """
            UPDATE historical_reviews
            SET season = ?, tier = ?, show_raw = ?, society_raw = ?, society_id = ?, show_id = ?,
                review_text = ?, source_issue = ?, flag = ?
            WHERE id = ?
            """,
            (season, tier, show_raw, society_raw, society_id, show_id, review_text, source_issue, flag, review_id),
        )
        db.commit()
        flash("Review updated.", "success")
        return redirect(url_for("admin.historical_reviews_queue"))

    return render_template(
        "admin/historical_review_edit.html", review=review, societies=_all_societies(db), form=review,
    )


def _all_societies(db):
    return db.execute("SELECT id, name FROM societies ORDER BY name").fetchall()


def find_society_candidates_batch(db, society_raws):
    """Fuzzy society-name suggestions for every review whose society_raw
    didn't exactly match anything (flag='needs_check') - real name variants
    are common across 14 years of hand-typed magazine text ("Harold's Cross
    Tallaght Musical Society" vs "Harolds Cross Tallaght Musical Society",
    confirmed - just a missing apostrophe, scores 0.99). Reuses the same
    scorer as find_historical_results_candidates (app.dedupe.find_candidates,
    the admin dashboard's own duplicate-society/-show tool) rather than a
    third fuzzy-matching implementation.

    Takes every raw name at once and scores them against the society list in
    a single find_candidates call, rather than one call per raw name - the
    per-review version of this (one find_candidates([society_raw] + names)
    call per review) redid the full O(names^2) society-vs-society comparison
    from scratch on every single pending review, which with 175 pending
    reviews and 179 societies meant ~2.8M SequenceMatcher calls on every
    load of the moderation queue - slow enough to time out the page and, in
    production, hang waitress's worker threads until the container was
    killed and restarted (the cause of the 524 right after this shipped).
    Batching still does the society-vs-society comparisons, but only once.

    Returns {society_raw: [(name, score, section), ...]}, each list sorted
    highest-first - a moderator still picks, this only suggests. section is
    the society's own societies.section, carried through so the queue can
    flag a suggestion that's an 'Inactive' (defunct/not currently competing)
    society - a real and useful distinction when matching decade-old reviews,
    where the right answer often *is* a society that no longer competes."""
    raws = sorted({r for r in society_raws if r})
    if not raws:
        return {}
    society_rows = db.execute("SELECT name, section FROM societies").fetchall()
    names = [r["name"] for r in society_rows]
    section_by_name = {r["name"]: r["section"] for r in society_rows}
    if not names:
        return {}
    raw_set = set(raws)
    pairs = find_candidates(raws + names, dismissed=set())
    best_by_raw = {raw: {} for raw in raws}
    for a, b, score in pairs:
        if a in raw_set and b not in raw_set:
            best_by_raw[a][b] = max(best_by_raw[a].get(b, 0), score)
        elif b in raw_set and a not in raw_set:
            best_by_raw[b][a] = max(best_by_raw[b].get(a, 0), score)
    # Re-rank on the distinctive (town/identity) part rather than the raw
    # whole-string score, and drop candidates that only look close because
    # they share a generic suffix - see _society_distinctive_score. This
    # matters much more here than it did when these were only ever eyeballed
    # one review at a time: a single bulk action applies one match to every
    # review sharing that printed name, so a plausible-looking wrong
    # suggestion at the top of the list is worth several bad rows, not one.
    ranked = {}
    for raw, candidates in best_by_raw.items():
        scored = []
        for name, score in candidates.items():
            distinctive = _society_distinctive_score(raw, name)
            if distinctive < SOCIETY_DISTINCTIVE_THRESHOLD:
                continue
            scored.append((distinctive, score, name))
        scored.sort(key=lambda t: (-t[0], -t[1]))
        ranked[raw] = [(name, score, section_by_name.get(name)) for _, score, name in scored]
    return ranked


def find_historical_results_candidates(db, society_id, season, show_raw):
    """Reviews before 23/24 can never match an existing `shows` row (see
    SHOWS_COVERAGE_START_YEAR) - but the production itself very often
    already exists in the older, pre-existing `historical_results` awards
    archive (back to ~2005), just under a slightly different title than
    the one printed in the ShowTimes review heading ('Titanic' vs the
    awards archive's 'Titanic The Musical', confirmed - both are the same
    2011 Marian Choral Society production). Reuses the site's own existing
    duplicate-title scorer (app.dedupe.find_candidates, built for the
    admin "possible duplicate societies/shows" tool) rather than writing a
    second fuzzy-matching implementation - it already strips exactly this
    kind of generic suffix ('the musical', 'jr.', ...) before scoring, so
    'Titanic' vs 'Titanic The Musical' comes back a perfect 1.0 for free.
    Returns [(title, score), ...] sorted highest-first, scores in [0, 1] -
    an empty list means no plausible history exists at all, not that
    matching failed."""
    if society_id is None:
        return []
    year = historical_results_year(season)
    rows = db.execute(
        "SELECT DISTINCT show FROM historical_results WHERE society_id = ? AND year = ? AND show IS NOT NULL",
        (society_id, year),
    ).fetchall()
    candidate_titles = [r["show"] for r in rows]
    if not candidate_titles:
        return []
    pairs = find_candidates([show_raw] + candidate_titles, dismissed=set())
    best_by_title = {}
    for a, b, score in pairs:
        if show_raw not in (a, b):
            continue
        other = b if a == show_raw else a
        best_by_title[other] = max(best_by_title.get(other, 0), score)
    return sorted(best_by_title.items(), key=lambda kv: -kv[1])


def find_mismatched_skeleton_shows(db):
    """Skeleton shows (source='historical', created by approving a
    historical review - see _approve_historical_review_row) whose own
    title doesn't line up with a plausible existing historical_results
    record for the same production. public.show_detail's own award-history
    lookup already tolerates a pure case/punctuation difference
    (normalize_title, e.g. 'Made In Dagenham' vs 'Made in Dagenham' - the
    review's own show_raw.title()-casing versus the awards CSV's original
    casing) - this only flags a *real* wording gap that normalize_title
    can't paper over ('Jekyll And Hyde' vs 'Jekyll & Hyde' isn't one;
    'Joseph And His...' vs 'Joseph and the...' is), which actually needs
    the title corrected before that award history will surface. A one-off
    retroactive audit (there was no such check when the first review-
    extraction batch was approved) - see apply_show_title_match for the
    fix, and categorize_pending_reviews' own history_match category for
    the same check applied going forward, before a review is ever
    approved."""
    skeletons = db.execute(
        "SELECT id, society_id, season, show FROM shows WHERE source = 'historical'"
    ).fetchall()
    mismatches = []
    for s in skeletons:
        candidates = find_historical_results_candidates(db, s["society_id"], s["season"], s["show"])
        strong = [
            (title, score) for title, score in candidates
            if score >= HISTORICAL_RESULTS_MATCH_THRESHOLD and normalize_title(title) != normalize_title(s["show"])
        ]
        if strong:
            entry = dict(s)
            entry["suggested_title"], entry["match_score"] = strong[0]
            mismatches.append(entry)
    return mismatches


@bp.route("/historical-shows/title-check")
@login_required
def historical_shows_title_check():
    db = get_db()
    mismatches = find_mismatched_skeleton_shows(db)
    society_names = {
        r["id"]: r["name"] for r in db.execute("SELECT id, name FROM societies")
    }
    for m in mismatches:
        m["society_name"] = society_names.get(m["society_id"])
    return render_template("admin/historical_shows_title_check.html", mismatches=mismatches)


@bp.route("/historical-shows/<int:show_id>/apply-title-match", methods=("POST",))
@login_required
def apply_show_title_match(show_id):
    """One-click accept for a find_mismatched_skeleton_shows suggestion -
    corrects an already-approved skeleton show's own title to the awards
    archive's title for the same production, so public.show_detail's
    (society, year, title) lookup finds it. Only ever touches
    source='historical' rows - a real imported show's title is
    authoritative on its own, never something to silently rewrite from a
    fuzzy suggestion."""
    db = get_db()
    show = db.execute("SELECT * FROM shows WHERE id = ? AND source = 'historical'", (show_id,)).fetchone()
    if show is None:
        abort(404)
    title = request.form.get("title", "").strip()
    if not title:
        abort(400)

    # The corrected title can collide with a real shows row that already
    # exists independently of the review pipeline (confirmed in production -
    # Thurles Musical Society's 17/18 'Ragtime The Musical' already existed
    # as a member submission; the review's own skeleton was a separate,
    # differently-titled row for the same actual production) - a plain
    # rename would 500 on ux_shows_natural_key. When that happens, the
    # skeleton was never the real show to begin with - re-point its
    # review(s) onto the one that already exists and remove the now-
    # redundant skeleton, rather than trying to rename into a collision.
    existing = db.execute(
        "SELECT id FROM shows WHERE society_id = ? AND season = ? AND show = ? AND id != ?",
        (show["society_id"], show["season"], title, show_id),
    ).fetchone()
    if existing is not None:
        db.execute("UPDATE historical_reviews SET show_id = ? WHERE show_id = ?", (existing["id"], show_id))
        db.execute("DELETE FROM shows WHERE id = ?", (show_id,))
        db.commit()
        flash(
            f'"{title}" already exists as a real show for this society/season - linked the '
            "review there instead and removed the duplicate skeleton.", "success",
        )
    else:
        # No updated_at bump here (deliberately - this is a data correction,
        # not an edit to the production), so the productions freshness check
        # is told directly instead.
        db.execute("UPDATE shows SET show = ? WHERE id = ?", (title, show_id))
        productions_build.mark_stale(db)
        db.commit()
        flash(f'Show title corrected to "{title}".', "success")
    return redirect(url_for("admin.historical_shows_title_check"))


def match_show_for_edit(db, society_id, season, show_raw):
    if society_id is None:
        return None
    row = db.execute(
        "SELECT id FROM shows WHERE society_id = ? AND season = ? AND show = ? AND moderation_status = 'approved'",
        (society_id, season, show_raw),
    ).fetchone()
    return row[0] if row else None
