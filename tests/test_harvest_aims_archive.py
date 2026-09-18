"""The Wayback harvester: what it fetches, what it skips, and that it resumes.

Nothing here touches the network. Every test drives `harvest()` with a fake
getter, because the two things that actually matter about this script are that it
does not lose work when the Internet Archive goes down mid-run (it did on
2026-09-17) and that what it stores carries the URL and capture date it came from.
"""
import json
import urllib.error

import pytest

from harvest_aims_archive import (
    ArchiveUnavailable,
    Manifest,
    capture_key,
    cdx_query_url,
    harvest,
    html_to_text,
    parse_cdx_page,
    path_extension,
    should_fetch,
    url_filter,
    wayback_url,
)


def cap(original="http://www.aims.ie/awards/2004/index.html",
        timestamp="20040623091916", mimetype="text/html", status="200",
        digest="AAAA"):
    return {"urlkey": "ie,aims)/", "timestamp": timestamp, "original": original,
            "mimetype": mimetype, "statuscode": status, "digest": digest,
            "length": "1234"}


# --------------------------------------------------------------------------
# The CDX index
# --------------------------------------------------------------------------

def test_cdx_query_asks_for_the_whole_domain_over_the_disputed_years():
    url = cdx_query_url("aims.ie", 2001, 2010, 2000)
    assert "matchType=domain" in url
    assert "from=2001" in url and "to=2010" in url
    assert "collapse=digest" in url


def test_parse_cdx_page_splits_off_the_resume_key():
    payload = json.dumps([
        ["urlkey", "timestamp", "original"],
        ["ie,aims)/", "20040101000000", "http://aims.ie/"],
        [],
        ["ie,aims)/awards 20050101"],
    ])
    captures, resume_key = parse_cdx_page(payload)

    assert len(captures) == 1
    assert captures[0]["original"] == "http://aims.ie/"
    assert resume_key == "ie,aims)/awards 20050101"


def test_parse_cdx_page_without_a_resume_key_is_the_last_page():
    payload = json.dumps([
        ["urlkey", "timestamp", "original"],
        ["ie,aims)/", "20040101000000", "http://aims.ie/"],
    ])
    captures, resume_key = parse_cdx_page(payload)

    assert len(captures) == 1
    assert resume_key is None


def test_parse_cdx_page_handles_an_empty_index():
    assert parse_cdx_page("[]") == ([], None)


# --------------------------------------------------------------------------
# What is worth fetching
# --------------------------------------------------------------------------

@pytest.mark.parametrize("original", [
    "http://www.aims.ie/awards/2004/noms2004.pdf",
    "http://www.aims.ie/awards/index.html",
    "http://www.aims.ie/societies",
])
def test_documents_are_fetched(original):
    mimetype = "application/pdf" if original.endswith(".pdf") else "text/html"
    wanted, _ = should_fetch(cap(original=original, mimetype=mimetype))
    assert wanted


@pytest.mark.parametrize("original,mimetype", [
    ("http://www.aims.ie/images/spacer.gif", "image/gif"),
    ("http://www.aims.ie/style.css", "text/css"),
    ("http://www.aims.ie/rollover.js", "application/x-javascript"),
])
def test_website_furniture_is_skipped_with_a_reason(original, mimetype):
    wanted, reason = should_fetch(cap(original=original, mimetype=mimetype))
    assert not wanted
    assert reason


def test_a_capture_that_was_not_a_200_is_skipped():
    wanted, reason = should_fetch(cap(status="404"))
    assert not wanted
    assert "404" in reason


def test_an_unknown_mimetype_on_an_extensionless_path_is_still_fetched():
    # A 2003 site is full of these, and they are usually HTML.
    wanted, _ = should_fetch(cap(original="http://www.aims.ie/awards", mimetype="unk"))
    assert wanted


def test_path_extension_ignores_a_dot_in_the_directory():
    assert path_extension("http://aims.ie/v2.0/awards") == ""
    assert path_extension("http://aims.ie/v2.0/noms.PDF") == ".pdf"


def test_capture_key_is_unique_per_url_and_per_capture_date():
    a = capture_key(cap(original="http://aims.ie/a", timestamp="20040101000000"))
    b = capture_key(cap(original="http://aims.ie/b", timestamp="20040101000000"))
    c = capture_key(cap(original="http://aims.ie/a", timestamp="20050101000000"))
    assert a != b and a != c


def test_wayback_url_asks_for_the_original_bytes():
    # The id_ suffix is what keeps the Archive's own banner out of the capture.
    assert wayback_url(cap()).startswith("http://web.archive.org/web/20040623091916id_/")


# --------------------------------------------------------------------------
# Text extraction
# --------------------------------------------------------------------------

def test_table_rows_become_lines_so_a_name_stays_with_its_society():
    html = ("<table><tr><td>Best Male Singer</td><td>Pat Naughton</td>"
            "<td>Athenry Musical Society</td></tr>"
            "<tr><td>Best Comedienne</td><td>Marilyn Bane</td>"
            "<td>Athlone Musical Society</td></tr></table>")
    lines = [line for line in html_to_text(html).splitlines() if line.strip()]

    athenry = next(i for i, line in enumerate(lines) if "Athenry" in line)
    assert "Pat Naughton" in "\n".join(lines[max(0, athenry - 2):athenry + 1])
    assert not any("Athenry" in line and "Athlone" in line for line in lines)


def test_scripts_and_styles_do_not_reach_the_text():
    html = "<style>td{color:red}</style><script>var x=1;</script><p>Nominations 2004</p>"
    assert html_to_text(html) == "Nominations 2004"


def test_unclosed_tags_from_a_2003_page_still_yield_their_text():
    assert "Athenry" in html_to_text("<p>Athenry<td><b>Musical")


# --------------------------------------------------------------------------
# Harvesting
# --------------------------------------------------------------------------

class FakeArchive:
    """Answers with canned bodies, and can be told to fall over."""

    def __init__(self, body=b"<p>Nominations</p>", failures=0, http_error=None):
        self.body = body
        self.failures = failures
        self.http_error = http_error
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append(url)
        if self.http_error:
            raise urllib.error.HTTPError(url, self.http_error, "no", None, None)
        if self.failures:
            self.failures -= 1
            raise ArchiveUnavailable(url + ": timed out")
        return self.body


def run(captures, tmp_path, getter, **kwargs):
    manifest = Manifest(tmp_path / "manifest.jsonl")
    counts = harvest(captures, tmp_path, manifest, delay=0, getter=getter,
                     sleeper=lambda _s: None, log=lambda *_a: None, **kwargs)
    return counts, manifest


def test_a_fetched_page_is_stored_with_its_provenance(tmp_path):
    counts, _ = run([cap()], tmp_path, FakeArchive())

    assert counts["fetched"] == 1
    text = (tmp_path / "text").glob("*.txt")
    stored = next(text).read_text(encoding="utf-8")
    assert "# source: http://www.aims.ie/awards/2004/index.html" in stored
    assert "# captured: 20040623091916" in stored
    assert "Nominations" in stored


def test_raw_bytes_are_kept_beside_the_text(tmp_path):
    run([cap()], tmp_path, FakeArchive(b"<p>Raw</p>"))
    raw = list((tmp_path / "raw").iterdir())
    assert len(raw) == 1
    assert raw[0].read_bytes() == b"<p>Raw</p>"


def test_the_same_content_captured_twice_is_only_stored_once(tmp_path):
    archive = FakeArchive()
    counts, _ = run([cap(timestamp="20040101000000"),
                     cap(timestamp="20050101000000")], tmp_path, archive)

    assert counts["fetched"] == 1
    assert counts["duplicate"] == 1
    assert len(archive.calls) == 1


def test_a_changed_page_is_kept_as_a_second_version(tmp_path):
    counts, _ = run([cap(timestamp="20040101000000", digest="AAAA"),
                     cap(timestamp="20050101000000", digest="BBBB")],
                    tmp_path, FakeArchive())
    assert counts["fetched"] == 2


def test_a_second_run_resumes_instead_of_refetching(tmp_path):
    run([cap()], tmp_path, FakeArchive())

    archive = FakeArchive()
    counts, _ = run([cap()], tmp_path, archive)

    assert counts["already"] == 1
    assert archive.calls == []


def test_work_done_before_an_outage_survives_it(tmp_path):
    # Two good captures, then an Archive that stops answering entirely.
    captures = [cap(original="http://aims.ie/a", digest="A"),
                cap(original="http://aims.ie/b", digest="B")]
    run(captures, tmp_path, FakeArchive())

    dead = FakeArchive(failures=99)
    counts, manifest = run(captures + [cap(original="http://aims.ie/c", digest="C")],
                           tmp_path, dead, max_consecutive_failures=3)

    assert counts["already"] == 2
    assert counts["fetched"] == 0
    assert len([line for line in (tmp_path / "manifest.jsonl").read_text().splitlines()
                if line.strip()]) == 2


def test_a_run_of_failures_stops_the_harvest_rather_than_hammering(tmp_path):
    dead = FakeArchive(failures=99)
    captures = [cap(original="http://aims.ie/{}".format(i), digest=str(i))
                for i in range(20)]
    counts, _ = run(captures, tmp_path, dead, max_consecutive_failures=3)

    assert counts["failed"] == 3
    assert len(dead.calls) == 3


def test_one_missing_page_does_not_stop_the_run(tmp_path):
    # A 404 is the Archive answering about that URL, not an outage.
    captures = [cap(original="http://aims.ie/{}".format(i), digest=str(i))
                for i in range(5)]
    gone = FakeArchive(http_error=404)
    counts, manifest = run(captures, tmp_path, gone, max_consecutive_failures=3)

    assert counts["failed"] == 5
    assert len(gone.calls) == 5
    assert all(r["state"] == "failed" for r in manifest.done.values())


def test_a_failed_capture_is_not_silently_refetched(tmp_path):
    captures = [cap()]
    run(captures, tmp_path, FakeArchive(http_error=404))

    counts, _ = run(captures, tmp_path, FakeArchive())
    # The manifest is the record of what was tried, not only of what worked, so
    # a page the Archive does not have is not asked for again every run.
    assert counts["already"] == 1


def test_retry_failed_attempts_them_again(tmp_path):
    # Because the failure is not always the Archive's. Encoding accented URLs
    # the wrong way wrote 152 real pages into the manifest as 404s, and without
    # this they would have been skipped forever.
    captures = [cap()]
    run(captures, tmp_path, FakeArchive(http_error=404))

    archive = FakeArchive()
    counts, _ = run(captures, tmp_path, archive, retry_failed=True)

    assert counts["fetched"] == 1
    assert len(archive.calls) == 1


def test_retry_failed_still_leaves_finished_work_alone(tmp_path):
    captures = [cap()]
    run(captures, tmp_path, FakeArchive())

    archive = FakeArchive()
    counts, _ = run(captures, tmp_path, archive, retry_failed=True)

    assert counts["already"] == 1
    assert archive.calls == []


def test_skipped_captures_record_why(tmp_path):
    _, manifest = run([cap(original="http://aims.ie/logo.gif", mimetype="image/gif")],
                      tmp_path, FakeArchive())
    record = next(iter(manifest.done.values()))
    assert record["state"] == "skipped"
    assert "gif" in record["reason"]


def test_limit_stops_after_that_many_new_captures(tmp_path):
    captures = [cap(original="http://aims.ie/{}".format(i), digest=str(i))
                for i in range(10)]
    counts, _ = run(captures, tmp_path, FakeArchive(), limit=3)
    assert counts["fetched"] == 3


def test_a_torn_manifest_line_does_not_break_the_resume(tmp_path):
    path = tmp_path / "manifest.jsonl"
    path.write_text(json.dumps({"key": "k", "state": "fetched", "digest": "A"})
                    + "\n{\"key\": \"partial\"", encoding="utf-8")
    manifest = Manifest(path)

    assert manifest.has("k")
    assert manifest.digests() == {"A"}


def test_a_pdf_is_stored_even_when_its_text_cannot_be_extracted(tmp_path, monkeypatch):
    import harvest_aims_archive

    monkeypatch.setattr(harvest_aims_archive, "pdf_to_text", lambda _p: None)
    counts, manifest = run([cap(original="http://aims.ie/awards/2004/noms2004.pdf",
                                mimetype="application/pdf")],
                           tmp_path, FakeArchive(b"%PDF-1.4 ..."))

    assert counts["fetched"] == 1
    assert list((tmp_path / "raw").iterdir())[0].suffix == ".pdf"
    assert next(iter(manifest.done.values()))["text"] is None


# --------------------------------------------------------------------------
# Running the useful part first
# --------------------------------------------------------------------------

def test_match_pulls_the_awards_pages_and_leaves_the_forum(tmp_path):
    captures = [cap(original="http://www.aims.ie/awards/2004/noms2004.html", digest="A"),
                cap(original="http://www.aims.ie/discuss/thread.asp?id=9", digest="B")]
    archive = FakeArchive()
    counts, _ = run(captures, tmp_path, archive, keep=url_filter(match="awards"))

    assert counts["fetched"] == 1
    assert "noms2004" in archive.calls[0]


def test_exclude_drops_a_matching_url(tmp_path):
    captures = [cap(original="http://matrixstats.aims.ie/dyn/x.asp", digest="A"),
                cap(original="http://www.aims.ie/awards/2004/", digest="B")]
    counts, _ = run(captures, tmp_path, FakeArchive(),
                    keep=url_filter(exclude="matrixstats"))
    assert counts["fetched"] == 1


def test_a_pattern_miss_is_not_recorded_as_done(tmp_path):
    # Otherwise a narrow first run would permanently hide those pages from a
    # later, wider one - the manifest is a record of work, not of intent.
    forum = cap(original="http://www.aims.ie/discuss/thread.asp?id=9", digest="B")
    run([forum], tmp_path, FakeArchive(), keep=url_filter(match="awards"))

    archive = FakeArchive()
    counts, _ = run([forum], tmp_path, archive)
    assert counts["fetched"] == 1


def test_the_filter_is_case_insensitive():
    keep = url_filter(match="awards")
    assert keep("http://aims.ie/AWARDS/2004/")[0]


# --------------------------------------------------------------------------
# Characters the console and urllib cannot take
# --------------------------------------------------------------------------

def test_an_accented_url_is_percent_encoded_before_it_is_sent():
    # urllib refuses a URL with non-ASCII in it, and the ascii codec error
    # looks exactly like a network fault - so it burned all four retries and
    # was reported as an outage. The awards pages carry one URL per person and
    # Irish names are full of fadas, so this is common, not exotic.
    from harvest_aims_archive import encode_url

    encoded = encode_url("http://aims.ie/awards/societiesdirector.asp?director=Áine+Gilmore")
    # cp1252, not UTF-8: the Wayback index keys on the bytes the original site
    # served, and a 2004 ASP site served cp1252. Checked against the live
    # Archive - %C1 returns the page, %C3%81 returns 404.
    assert encoded == "http://aims.ie/awards/societiesdirector.asp?director=%C1ine+Gilmore"
    assert encoded.isascii()


def test_a_character_cp1252_cannot_hold_falls_back_to_utf8():
    from harvest_aims_archive import encode_url

    assert encode_url("http://aims.ie/Ł") == "http://aims.ie/%C5%81"


def test_an_already_encoded_url_is_left_alone():
    # Re-encoding the % would change the URL into a different one.
    from harvest_aims_archive import encode_url

    url = "http://www.aims.ie/awards/societieschoreographer.asp?choreographer=Yvonne%20Prendergast"
    assert encode_url(url) == url


def test_progress_output_cannot_kill_a_long_run(tmp_path, monkeypatch, capsys):
    # A cp1252 console raised UnicodeEncodeError while *reporting* a failed
    # URL, and ended a run that had already fetched 1,885 pages. Reporting a
    # problem must never be a worse problem.
    import io as _io
    import harvest_aims_archive

    cp1252 = _io.TextIOWrapper(_io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(harvest_aims_archive.sys, "stdout", cp1252)
    harvest_aims_archive.log_line("unavailable: Łá 中文")

    cp1252.seek(0)
    assert "unavailable" in cp1252.buffer.getvalue().decode("cp1252")


def test_a_capture_with_an_accented_url_does_not_stop_the_harvest(tmp_path):
    accented = cap(original="http://aims.ie/awards/societiesdirector.asp?director=Áine",
                   digest="A")
    after = cap(original="http://aims.ie/awards/2004/", digest="B")

    archive = FakeArchive()
    counts, _ = run([accented, after], tmp_path, archive)

    assert counts["fetched"] == 2
