"""apply_review_links.py - the write-back half of the aims.ie review publisher
sync. Its one hard rule: nothing is written for a review that isn't live on
aims.ie (Darragh, 2026-11-19)."""
import json

import apply_review_links as arl
from conftest import seed_society

LIVE = "https://www.aims.ie/post/review-gypsy-fusion-theatre-group"


def _show(db, society_id, review_url=None, review_author=None):
    cur = db.execute(
        "INSERT INTO shows (society_id, season, region, section, show, review_url, review_author, moderation_status) "
        "VALUES (?, '26/27', 'Northern', 'Sullivan', 'Gypsy', ?, ?, 'approved')",
        (society_id, review_url, review_author),
    )
    db.commit()
    return cur.lastrowid


def _society_name(db, society_id):
    return db.execute("SELECT name FROM societies WHERE id = ?", (society_id,)).fetchone()[0]


def _run(app, db, tmp_path, links, fetch, dry_run=False):
    path = tmp_path / "review_links.json"
    path.write_text(json.dumps({"links": links}), encoding="utf-8")
    argv = ["--db", app.config["DATABASE"], "--json", str(path)] + (["--dry-run"] if dry_run else [])
    return arl.main(argv, fetch=fetch)


def _link(db, show_id, society_id, url=LIVE):
    return {"show_id": show_id, "expect_society": _society_name(db, society_id), "expect_season": "26/27",
            "review_url": url, "adjudicator": "Justin Parkes"}


def live(url):
    return 200, url


def _row(db, show_id):
    return db.execute("SELECT review_url, review_status, review_author FROM shows WHERE id = ?", (show_id,)).fetchone()


def test_live_review_is_applied_with_author(app, db, tmp_path):
    sid = seed_society(db)
    show_id = _show(db, sid)
    report = _run(app, db, tmp_path, [_link(db, show_id, sid)], live)
    assert len(report["applied"]) == 1
    assert tuple(_row(db, show_id)) == (LIVE, "Published", "Justin Parkes")


def test_not_live_is_never_written(app, db, tmp_path):
    sid = seed_society(db)
    show_id = _show(db, sid)
    for fetch in (lambda u: (404, u), lambda u: (200, "https://www.aims.ie/"), lambda u: (500, u)):
        report = _run(app, db, tmp_path, [_link(db, show_id, sid)], fetch)
        assert report["applied"] == [] and len(report["skipped_not_live"]) == 1
    assert _row(db, show_id)["review_url"] is None


def test_network_error_counts_as_not_live(app, db, tmp_path):
    sid = seed_society(db)
    show_id = _show(db, sid)

    def boom(url):
        raise OSError("no route")

    report = _run(app, db, tmp_path, [_link(db, show_id, sid)], boom)
    assert len(report["skipped_not_live"]) == 1
    assert _row(db, show_id)["review_url"] is None


def test_non_aims_url_rejected_without_fetching(app, db, tmp_path):
    sid = seed_society(db)
    show_id = _show(db, sid)
    calls = []
    report = _run(app, db, tmp_path, [_link(db, show_id, sid, url="https://example.com/post/x")],
                  lambda u: calls.append(u) or (200, u))
    assert calls == [] and len(report["skipped_not_live"]) == 1


def test_existing_different_link_is_reported_not_overwritten(app, db, tmp_path):
    sid = seed_society(db)
    old = "https://www.aims.ie/post/review-sister-act-newry"
    show_id = _show(db, sid, review_url=old)
    report = _run(app, db, tmp_path, [_link(db, show_id, sid)], live)
    assert len(report["conflicts"]) == 1
    assert _row(db, show_id)["review_url"] == old


def test_rerun_is_a_no_op_and_keeps_existing_author(app, db, tmp_path):
    sid = seed_society(db)
    show_id = _show(db, sid, review_author="Peter Kennedy")
    _run(app, db, tmp_path, [_link(db, show_id, sid)], live)
    report = _run(app, db, tmp_path, [_link(db, show_id, sid)], live)
    assert report["already_applied"] == 1 and report["applied"] == []
    assert _row(db, show_id)["review_author"] == "Peter Kennedy"


def test_mismatched_show_skipped(app, db, tmp_path):
    sid = seed_society(db)
    show_id = _show(db, sid)
    link = _link(db, show_id, sid)
    link["expect_season"] = "25/26"
    report = _run(app, db, tmp_path, [link], live)
    assert len(report["skipped_no_match"]) == 1
    assert _row(db, show_id)["review_url"] is None


def test_dry_run_writes_nothing(app, db, tmp_path):
    sid = seed_society(db)
    show_id = _show(db, sid)
    report = _run(app, db, tmp_path, [_link(db, show_id, sid)], live, dry_run=True)
    assert len(report["applied"]) == 1
    assert _row(db, show_id)["review_url"] is None
