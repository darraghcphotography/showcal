"""Harvest the pre-Wix aims.ie out of the Internet Archive.

Why this exists: the ShowTimes review archive only runs from 09/10, so it cannot
reach the years where seven societies are collapsed into one another's award rows
(see `docs/collapsed-societies.md`). The old aims.ie published the official AIMS
nominations lists, and the Internet Archive holds the site from January 2001.

This is enumerate-fetch-store: it asks the CDX index what was captured, fetches
each distinct version of each page, and writes the raw bytes plus extracted text
beside a manifest line recording the URL and the capture date it came from. It
makes no claims and decides nothing - every output carries its own provenance, so
a later read of it is reading a primary source, not somebody's summary of one.

    py scripts/harvest_aims_archive.py                  # index, then fetch
    py scripts/harvest_aims_archive.py --index-only     # just build cdx.jsonl
    py scripts/harvest_aims_archive.py --limit 50       # a taste of it first

It is resumable on purpose. The Internet Archive went offline mid-session on
2026-09-17 and will again: every completed capture is appended to the manifest
immediately, a re-run skips what the manifest already has, and a run of
consecutive failures stops the whole thing rather than hammering a service that
is having a bad day. Re-running after an outage costs nothing but the index read.

Output goes to `archive_harvest/` at the repo root, which is gitignored the same
way `enrichment/` is - it is raw source material, not repo content.
"""
import argparse
import gzip
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CDX_ENDPOINT = "http://web.archive.org/cdx/search/cdx"
WAYBACK_ENDPOINT = "http://web.archive.org/web"
USER_AGENT = (
    "AIMS Show Tracker archive harvester - one request per second, resumable"
)

# CDX fields we ask for, in order. Keep the names as the API spells them.
CDX_FIELDS = ("urlkey", "timestamp", "original", "mimetype", "statuscode", "digest", "length")

# What we are here for: pages and documents. Everything else on a 2003 website is
# layout furniture - spacer gifs, a rollover script, a stylesheet - and none of it
# names a society.
TEXT_MIMETYPES = {
    "text/html",
    "text/plain",
    "application/xhtml+xml",
    "application/pdf",
    "text/xml",
    "application/xml",
}
SKIP_EXTENSIONS = {
    ".gif", ".jpg", ".jpeg", ".png", ".bmp", ".ico", ".svg", ".webp",
    ".css", ".js", ".swf", ".class", ".jar", ".cur",
    ".mov", ".mp3", ".mp4", ".wav", ".avi", ".wmv", ".ram", ".rm",
    ".zip", ".exe", ".ttf", ".eot", ".woff", ".woff2",
}
EXTENSION_FOR_MIMETYPE = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/xml": ".xml",
    "application/xml": ".xml",
}


class ArchiveUnavailable(Exception):
    """The Internet Archive is not answering. Stop; the manifest is safe."""


def log_line(text):
    """Print a line that may contain characters the console cannot encode.

    A Windows console is cp1252, and printing an accented URL to it raises
    UnicodeEncodeError - which killed a run of 1,885 fetched pages at the point
    where it was *reporting* a failure, turning a skippable URL into a crash.
    Progress output must never be able to end a long job.
    """
    text = str(text)
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        stream.write(text + "\n")
    except UnicodeEncodeError:
        stream.write(text.encode(encoding, "replace").decode(encoding) + "\n")
    stream.flush()


# --------------------------------------------------------------------------
# The CDX index
# --------------------------------------------------------------------------

def cdx_query_url(domain, from_year, to_year, page_limit, resume_key=None):
    """The CDX search URL for one page of results.

    `collapse=digest` drops runs of captures whose content never changed, which
    is most of them, while still keeping every version of a page that *did*
    change - which is the whole point, since an awards page is a different
    document each year.
    """
    params = [
        ("url", domain),
        ("matchType", "domain"),
        ("output", "json"),
        ("fl", ",".join(CDX_FIELDS)),
        ("from", str(from_year)),
        ("to", str(to_year)),
        ("collapse", "digest"),
        ("limit", str(page_limit)),
        ("showResumeKey", "true"),
    ]
    if resume_key:
        params.append(("resumeKey", resume_key))
    return f"{CDX_ENDPOINT}?{urllib.parse.urlencode(params)}"


def parse_cdx_page(payload):
    """Split a CDX JSON page into (captures, resume_key).

    The API returns a header row, then rows, then - when there is more to come -
    a blank row followed by a one-cell resume key. Both of those trailers have to
    be recognised rather than parsed as captures.
    """
    rows = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
    if not rows:
        return [], None
    header, body = rows[0], rows[1:]

    resume_key = None
    while body and (not body[-1] or len(body[-1]) == 1 or not any(body[-1])):
        tail = body.pop()
        if tail and tail[0]:
            resume_key = tail[0]

    captures = [dict(zip(header, row)) for row in body if len(row) == len(header)]
    return captures, resume_key


def fetch_index(domain, from_year, to_year, page_limit, opener, delay):
    """Every capture the CDX index knows about, following resume keys."""
    resume_key = None
    while True:
        url = cdx_query_url(domain, from_year, to_year, page_limit, resume_key)
        payload = opener(url)
        captures, resume_key = parse_cdx_page(payload.decode("utf-8", "replace"))
        for capture in captures:
            yield capture
        if not resume_key:
            return
        time.sleep(delay)


# --------------------------------------------------------------------------
# Deciding what to fetch
# --------------------------------------------------------------------------

def path_extension(original_url):
    path = urllib.parse.urlparse(original_url).path
    _, _, tail = path.rpartition("/")
    if "." not in tail:
        return ""
    return tail[tail.rfind("."):].lower()


def should_fetch(capture):
    """Is this capture a document worth storing?

    Returns (True, "") or (False, <reason>). The reason is recorded in the
    manifest rather than thrown away, so "why did we not pull that page?" has an
    answer later without re-running anything.
    """
    status = str(capture.get("statuscode") or "")
    if status and status != "200":
        return False, "status " + status

    mimetype = (capture.get("mimetype") or "").split(";")[0].strip().lower()
    extension = path_extension(capture.get("original", ""))

    if extension in SKIP_EXTENSIONS:
        return False, "extension " + extension
    if mimetype in TEXT_MIMETYPES:
        return True, ""
    if mimetype in ("warc/revisit", "unk", ""):
        # The index does not know; the extension usually does. A 2003 site is
        # full of extensionless paths that are plain HTML, so allow those.
        return True, ""
    return False, "mimetype " + mimetype


def url_filter(match=None, exclude=None):
    """A predicate over the original URL, for running the useful part first.

    21,000 captures is about four hours at one request a second, and most of it
    is a discussion forum. `--match awards` pulls the nominations and results
    pages in ten minutes; the rest can run overnight. The filter is applied to
    the original URL, not the Wayback one, so a pattern reads the way the old
    site's paths read.
    """
    match_re = re.compile(match, re.I) if match else None
    exclude_re = re.compile(exclude, re.I) if exclude else None

    def keep(original):
        if exclude_re and exclude_re.search(original):
            return False, "excluded by pattern"
        if match_re and not match_re.search(original):
            return False, "not matched by pattern"
        return True, ""

    return keep


def capture_key(capture):
    """A stable, filesystem-safe id for one captured version of one URL."""
    digest = hashlib.sha1(capture["original"].encode("utf-8")).hexdigest()[:12]
    return capture["timestamp"] + "-" + digest


def wayback_url(capture):
    """The `id_` form: the original bytes, without the Archive's own banner."""
    return "{}/{}id_/{}".format(WAYBACK_ENDPOINT, capture["timestamp"], capture["original"])


# --------------------------------------------------------------------------
# Fetching, politely
# --------------------------------------------------------------------------

def encode_url(url):
    """Percent-encode the non-ASCII characters in a URL.

    `urllib` will not send a URL containing them and fails with an ascii codec
    error, which looks exactly like a network fault and burns all four retries
    before being reported as an outage. The old site has plenty: the awards
    pages carry one URL per person, and Irish names are full of accents -
    `societiesdirector.asp?director=Aine+Gilmore` with a fada on the A is what
    found this.

    Only the non-ASCII characters are touched. Anything already percent-encoded
    is left exactly as it is, since re-encoding the % would change the URL.
    """
    return "".join(c if ord(c) < 128 else urllib.parse.quote(c, safe="") for c in url)


def http_get(url, timeout=60, retries=4, backoff=2.0, sleeper=time.sleep):
    """GET with backoff. Raises ArchiveUnavailable once the retries are spent."""
    url = encode_url(url)
    last_error = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept-Encoding": "gzip",
            })
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return body
        except urllib.error.HTTPError as error:
            if error.code in (403, 404):
                raise  # A real answer about this one URL, not an outage.
            last_error = error
        except Exception as error:  # timeouts, resets, DNS, half-read bodies
            last_error = error
        if attempt < retries - 1:
            sleeper(backoff * (2 ** attempt))
    raise ArchiveUnavailable("{}: {}".format(url, last_error))


# --------------------------------------------------------------------------
# Turning what came back into text
# --------------------------------------------------------------------------

_BLOCK_TAGS = ("p", "tr", "div", "li", "h1", "h2", "h3", "h4", "table", "blockquote")


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks = []
        self._muted = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._muted += 1
        elif tag == "br" or tag in _BLOCK_TAGS or tag == "td":
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._muted:
            self._muted -= 1
        elif tag in _BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data):
        if not self._muted:
            self.chunks.append(data)


def html_to_text(html):
    """Readable text from a page, with its line structure roughly intact.

    A nominations list is a table, and the row boundaries are what tie a name to
    a society - so block tags become newlines rather than spaces.
    """
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass  # 2003 HTML. Take whatever parsed before it gave up.
    text = "".join(parser.chunks)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def decode_body(body):
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", "replace")


def pdf_to_text(path):
    """PyMuPDF if it is installed, else None.

    Same split as the ShowTimes work: extraction needs PyMuPDF, which is not in
    the container, so PDFs harvested there are stored and extracted later. A
    stored PDF with no text is not a failure - the bytes are the artefact.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None
    try:
        with fitz.open(path) as document:
            return "\n\n".join(page.get_text() for page in document).strip()
    except Exception:
        return None


def extract_text(body, mimetype, raw_path):
    mimetype = (mimetype or "").split(";")[0].strip().lower()
    if mimetype == "application/pdf" or Path(raw_path).suffix == ".pdf":
        return pdf_to_text(raw_path), "pdf"
    return html_to_text(decode_body(body)), "html"


# --------------------------------------------------------------------------
# The manifest
# --------------------------------------------------------------------------

class Manifest:
    """Append-only JSONL: one line per capture we have finished with.

    Append-only because the alternative - rewriting a state file - is the thing
    that loses a run's work when the process is killed mid-write.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.done = {}
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # a torn final line from a killed run
                    if "key" in record:
                        self.done[record["key"]] = record

    def has(self, key):
        return key in self.done

    def digests(self):
        return {r["digest"] for r in self.done.values()
                if r.get("digest") and r.get("state") == "fetched"}

    def record(self, **fields):
        self.done[fields["key"]] = fields
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(fields, ensure_ascii=False) + "\n")
            handle.flush()


def load_index(path):
    captures = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                captures.append(json.loads(line))
    return captures


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------

def harvest(captures, out_dir, manifest, delay=1.0, limit=None,
            getter=http_get, sleeper=time.sleep, max_consecutive_failures=8,
            keep=None, log=log_line):
    """Fetch and store each capture. Returns a counts dict.

    Digest dedupe happens here rather than in the CDX query because `collapse`
    only drops *adjacent* duplicates: the same unchanged page reappears whenever
    something else on the site changed between two crawls of it.
    """
    out_dir = Path(out_dir)
    raw_dir = out_dir / "raw"
    text_dir = out_dir / "text"
    raw_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    seen_digests = manifest.digests()
    counts = {"fetched": 0, "skipped": 0, "duplicate": 0, "already": 0, "failed": 0}
    consecutive_failures = 0

    for capture in captures:
        if limit is not None and counts["fetched"] >= limit:
            log("Stopping at --limit {}.".format(limit))
            break

        key = capture_key(capture)
        if manifest.has(key):
            counts["already"] += 1
            continue

        wanted, reason = should_fetch(capture)
        if wanted and keep is not None:
            wanted, reason = keep(capture["original"])
            if not wanted:
                # A pattern miss is not a verdict on the page - a later run with
                # a different pattern should still see it, so it is passed over
                # rather than written to the manifest as done with.
                counts["skipped"] += 1
                continue
        if not wanted:
            counts["skipped"] += 1
            manifest.record(key=key, url=capture["original"],
                            timestamp=capture["timestamp"],
                            digest=capture.get("digest"),
                            state="skipped", reason=reason)
            continue

        digest = capture.get("digest")
        if digest and digest in seen_digests:
            counts["duplicate"] += 1
            manifest.record(key=key, url=capture["original"],
                            timestamp=capture["timestamp"], digest=digest,
                            state="duplicate",
                            reason="identical content already stored")
            continue

        url = wayback_url(capture)
        try:
            body = getter(url)
        except urllib.error.HTTPError as error:
            # The Archive answered about this one URL. Not an outage.
            counts["failed"] += 1
            consecutive_failures = 0
            manifest.record(key=key, url=capture["original"],
                            timestamp=capture["timestamp"], digest=digest,
                            state="failed", reason="HTTP {}".format(error.code))
            sleeper(delay)
            continue
        except ArchiveUnavailable as error:
            consecutive_failures += 1
            counts["failed"] += 1
            log("  unavailable: {}".format(error))
            if consecutive_failures >= max_consecutive_failures:
                log("\n{} failures in a row - the Archive looks down. Stopping here; "
                    "re-run the same command to resume.".format(consecutive_failures))
                break
            sleeper(delay * consecutive_failures)
            continue

        consecutive_failures = 0
        extension = (EXTENSION_FOR_MIMETYPE.get((capture.get("mimetype") or "").split(";")[0])
                     or path_extension(capture["original"]) or ".html")
        if extension in SKIP_EXTENSIONS:
            extension = ".html"
        raw_path = raw_dir / (key + extension)
        raw_path.write_bytes(body)

        text, kind = extract_text(body, capture.get("mimetype"), raw_path)
        text_path = None
        if text:
            text_path = text_dir / (key + ".txt")
            # The provenance travels with the text, not in a sidecar that can
            # get separated from it.
            header = ("# source: {}\n# captured: {}\n# via: {}\n\n".format(
                capture["original"], capture["timestamp"], url))
            text_path.write_text(header + text, encoding="utf-8")

        if digest:
            seen_digests.add(digest)
        counts["fetched"] += 1
        manifest.record(key=key, url=capture["original"],
                        timestamp=capture["timestamp"], digest=digest,
                        state="fetched", kind=kind, bytes=len(body),
                        raw=raw_path.name,
                        text=text_path.name if text_path else None,
                        reason="" if text else "no text extracted (PDF needs PyMuPDF?)")
        log("  [{}] {} {}".format(counts["fetched"], capture["timestamp"],
                                  capture["original"]))
        sleeper(delay)

    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "archive_harvest"),
                        help="output directory (default: archive_harvest/ at the repo root)")
    parser.add_argument("--domain", default="aims.ie",
                        help="domain to harvest, subdomains included (default: aims.ie)")
    parser.add_argument("--from-year", type=int, default=2001)
    parser.add_argument("--to-year", type=int, default=2010)
    parser.add_argument("--delay", type=float, default=1.0,
                        help="seconds between requests (default: 1.0 - be polite)")
    parser.add_argument("--limit", type=int, default=None,
                        help="stop after this many newly fetched captures")
    parser.add_argument("--index-only", action="store_true",
                        help="build cdx.jsonl and stop")
    parser.add_argument("--refresh-index", action="store_true",
                        help="re-query CDX even if cdx.jsonl already exists")
    parser.add_argument("--match", default=None,
                        help="only fetch captures whose original URL matches this regex "
                             "(e.g. --match \"awards|nomination\")")
    parser.add_argument("--exclude", default=None,
                        help="skip captures whose original URL matches this regex")
    parser.add_argument("--page-limit", type=int, default=2000,
                        help="CDX rows per request")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "cdx.jsonl"

    if args.refresh_index or not index_path.exists():
        print("Indexing {} {}-{} ...".format(args.domain, args.from_year, args.to_year))
        count = 0
        try:
            with index_path.open("w", encoding="utf-8") as handle:
                for capture in fetch_index(args.domain, args.from_year, args.to_year,
                                           args.page_limit, http_get, args.delay):
                    handle.write(json.dumps(capture, ensure_ascii=False) + "\n")
                    count += 1
        except ArchiveUnavailable as error:
            print("CDX index unavailable: {}".format(error))
            print("Nothing fetched. Re-run when the Archive is back.")
            return 2
        print("{} captures indexed -> {}".format(count, index_path))
    else:
        print("Using the existing index at {} (--refresh-index to rebuild).".format(index_path))

    captures = load_index(index_path)
    print("{} captures in the index.".format(len(captures)))
    if args.index_only:
        return 0

    manifest = Manifest(out_dir / "manifest.jsonl")
    if manifest.done:
        print("Resuming: {} captures already accounted for.".format(len(manifest.done)))

    keep = url_filter(args.match, args.exclude) if (args.match or args.exclude) else None
    counts = harvest(captures, out_dir, manifest, delay=args.delay, limit=args.limit,
                     keep=keep)
    print("\n" + ", ".join("{} {}".format(value, name) for name, value in counts.items()))
    print("Raw captures in {}, extracted text in {}.".format(out_dir / "raw", out_dir / "text"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
