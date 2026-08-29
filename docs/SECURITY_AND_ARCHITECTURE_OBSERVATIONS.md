# Security & Architecture Observations

> **Context**: These notes were compiled during a code and security review pass across the repository. The application is well-structured, performant, and secure in all core areas (parameterized SQL, nonce-gated CSP, strict upload decoding, derived table fingerprinting). 
> 
> Below are a few minor operational findings and optional architectural thoughts for whenever it is convenient.

---

## 1. Operational Security Finding: Rate-Limiting IP Resolution

### Summary
In `app/__init__.py`, `ProxyFix` is configured as:
```python
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)
```
In `app/rate_limit.py`, the limiter uses Flask-Limiter's standard `get_remote_address`:
```python
limiter = Limiter(key_func=get_remote_address)
```

### Observation
When deployed in Docker behind Cloudflare Tunnel / a reverse proxy, `x_for` is not enabled in `ProxyFix` (Werkzeug default is `x_for=0`). As a result, `request.remote_addr` resolves to the internal proxy / container bridge IP for incoming requests.

Because `@limiter.limit` is applied to `/admin/login` (10/min), `/submit` (5/min), `/society/login` (10/min), and `/correction` (5/min), all public visitors share that single rate-limit bucket. If an automated bot or misconfigured client triggers 10 failed logins, legitimate users could temporarily receive `HTTP 429 Too Many Requests`.

### Suggested Fix Options (Whenever Convenient)
1. **Option A (ProxyFix `x_for=1`)**:
   ```python
   app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_for=1)
   ```
2. **Option B (Cloudflare Header in `app/rate_limit.py`)**:
   ```python
   def get_real_client_ip():
       from flask import request
       return (
           request.headers.get("CF-Connecting-IP")
           or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
           or request.remote_addr
       )

   limiter = Limiter(key_func=get_real_client_ip)
   ```

---

## 2. Minor Edge Case: 413 Error Handler Referrer

### Observation
In `app/__init__.py:206`:
```python
@app.errorhandler(413)
def too_large(e):
    flash("That file is too large - images must be under 8 MB.", "error")
    return redirect(request.referrer or url_for("public.index")), 302
```
If a client posts an oversized payload with an external `Referer: https://external-domain.com`, the 413 handler redirects to that external URL.

### Suggested Adjustment
Ensure `request.referrer` is same-origin before redirecting:
```python
target = request.referrer if (request.referrer and request.referrer.startswith(request.host_url)) else url_for("public.index")
return redirect(target), 302
```

---

## 3. Architecture & Code Housekeeping Thoughts (Non-Urgent)

### A. Grouping One-Off Historical Migration Scripts
* **Current State**: The repository root currently contains ~25 historical data-loading and backfill scripts (`scripts/backfills/naas_history_backfill.py`, `scripts/backfills/tullamore_castlerea_history_backfill.py`, `scripts/enrichment/classify_venue_types.py`, `scripts/backfills/backfill_default_venues_round2.py`, `scripts/backfills/import_founding_years.py`, `load_historical_reviews.py`, etc.).
* **Idea**: Moving completed, one-off historical migration scripts into a dedicated folder like `scripts/migrations/` (while keeping live operational tools like `wsgi.py`, `build_productions.py`, `add_changelog.py`, `backup_db.py`, `verify_backup.py` at the root) would make it immediately clear to anyone browsing the repo which scripts are operational vs archived migrations.

### B. Modularizing `app/blueprints/public.py`
* **Current State**: `app/blueprints/admin/` is cleanly divided into 15 focused domain modules (`shows.py`, `venues.py`, `awards.py`, `adjudicators.py`, `faq.py`, etc.). Meanwhile, `app/blueprints/public.py` has grown to ~1,700 lines containing all public features (calendar, shows, venues, societies, titles, awards, search).
* **Idea**: If `public.py` is ever touched for major feature work in the future, splitting it into domain sub-modules under `app/blueprints/public/` (`shows.py`, `societies.py`, `venues.py`, `awards.py`, `search.py`) following the same pattern as `admin/` could be a clean, long-term maintainability win.

---

## 4. Strengths & Highlights from the Review

* **Derived Table Fingerprinting (`productions` & `venues`)**: The multi-subquery fingerprint (`COUNT(*)`, `MAX(id)`, `MAX(updated_at)`) running in $\approx 0.26\,\text{ms}$ before requests makes derived tables consistently fresh without query overhead.
* **Content Security Policy (CSP)**: Nonce-gating inline scripts with per-request cryptographic tokens (`g.csp_nonce`) and `frame-ancestors 'none'` provides robust XSS and clickjacking protection.
* **Image Processing & Sanitization**: Decoding uploads through Pillow (`img.load()`), enforcing WebP/JPEG re-encoding with max dimensions, and generating random UUID filenames thoroughly neutralizes image bomb / file upload risks.
* **Response Compression**: Enabling `flask-compress` gzip/brotli solved the payload size challenge on `/titles` and list views cleanly without needing complex client-side pagination.
