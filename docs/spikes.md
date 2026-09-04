# Spikes — assumptions we have not actually verified

Things the site currently depends on that were assumed rather than checked. They are not bugs: a
bug is something we know is wrong. These are things we believe are right and have not proved.

**Why this file exists.** Unverified assumptions were previously recorded in whatever `HANDBACK.md`
entry happened to be open when they surfaced. That works for a week and then the entry scrolls out
of reach — the reader who needs it most is the one picking up cold six sessions later, and they
have no reason to read a handback from September. One visible list is the fix.

**Each spike resolves one of three ways:**

| Resolution | Where it goes |
|---|---|
| Confirmed fine | Delete it here, record the finding in the relevant doc so nobody re-derives it |
| Confirmed a problem | It becomes real work — `ROADMAP.md`'s open list |
| Still unknown, accepted for now | Stays here, with a note on what would make it urgent |

Do not resolve a spike by reasoning about it. Resolve it by checking.

---

## Open

### Esri tile terms of service permit our use
**Status:** unverified · **Raised:** 2026-09-04 · **Affects:** `/venues`, `/venues/map`

The venue maps render Esri Canvas basemaps
(`server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_{Light,Dark}_Gray_Base`). The tiles
**do** serve keyless — that is confirmed in a real browser across both themes. What is not
confirmed is whether Esri's terms permit keyless production use, as opposed to merely not
technically blocking it. Some providers allow anonymous access while contractually expecting an
account.

This is exactly how the previous provider failed, which is the argument for checking rather than
waiting.

**How to resolve:** read Esri's current basemap terms for non-authenticated use.
**If it is a problem:** OSM standard tiles are the documented fallback — genuinely public-policy
keyless, just a lighter and more colourful style than the dark-grey match Esri gives us.
**What would make it urgent:** a watermark, a rate limit, or any tile 4xx appearing on `/venues`.

### CartoDB actually discontinued keyless tiles
**Status:** unverified · **Raised:** 2026-09-04 · **Affects:** the fallback decision above

The maps were moved off Carto because every tile rendered "API KEY REQUIRED" watermarked across
it. Confirmed live on production, and confirmed as pre-existing rather than introduced by any
agent's change. What was *not* established is whether Carto has genuinely ended anonymous tiles or
has added a soft nag that a free account would clear.

It only matters if the Esri spike above resolves badly — then "Carto with a free key" may be a
better answer than switching style entirely.

**How to resolve:** check Carto's current basemap pricing page for a free/anonymous tier.

### Magic-link and notification emails actually reach an inbox
**Status:** never measured · **Affects:** society access, the whole outreach workflow

`notify.send()` returns `True` when SMTP accepted the message, and the moderator screen now
surfaces a `False`. **SMTP acceptance is not delivery.** Nothing has ever confirmed that a magic
link sent to a society committee member's address arrives, rather than landing in spam — no SPF,
DKIM or DMARC posture has been checked for the sending domain, and no test send to an external
provider (Gmail, Outlook) has been recorded.

This matters more than it looks: the failure is silent on both ends. The moderator sees a
delivered message; the society sees nothing and concludes the site is broken.

**How to resolve:** send a real magic link to a Gmail and an Outlook address and see where it
lands. If it lands in spam, that is a DNS job, not a code job.
**What would make it urgent:** a society reporting they never received an approved request.

### The 54 orphaned `historical_reviews` rows are genuinely orphaned
**Status:** believed true, no verification method · **Affects:** review data quality

54 rows do not match any production. They are believed stale rather than meaningful, but nothing
has been deleted because "it looks unmatched" is not a test — the same reasoning would have thrown
away real data at several earlier points in this archive's history.

Worth knowing the figure moves: this was recorded as "~112" in `ROADMAP.md` for a while before
being recounted live at 54 on 2026-09-02. **Recount before acting on it.**

**How to resolve:** find a check that distinguishes "no matching production exists" from "the
matching production is recorded under a name we have not linked yet".

### `/stats/trends` most-staged shows will stay correct
**Status:** latent, deliberately not changed · **Affects:** `/stats/trends` Decades

That view groups most-staged shows on the raw `historical_results.show` string rather than a
normalized `title_key`. Exactly one title in the entire archive is recorded under two spellings
(*Honk* / *Honk!*), and the 2010s top five is identical either way — so this is fragility, not a
defect, and was left alone on purpose.

**What would make it real:** any bulk import that introduces spelling variants. If you are about to
run one, fix this first rather than afterwards.

### The site is usable with a screen reader
**Status:** never tested · **Affects:** all public pages

Accessibility here is markup-deep: `aria-label` on pagination, `role="status"` on flashes,
`aria-pressed` on the theme toggle. It has never been driven with an actual screen reader, nor with
images disabled — and the site leans far harder on imagery (posters, logos, playbills) than it did
when that markup was added.

Mobile *layout* is genuinely measured (`document.scrollWidth` against the viewport at 320/390px
across every route, most recently 2026-09-04) — do not let that create the impression accessibility
is measured too. They are different claims.

**How to resolve:** one pass with NVDA or VoiceOver over the homepage, a show page and the society
login flow.

### `season_start_year()`'s pivot holds
**Status:** true until 2050 · **Affects:** anything decoding a `'yy/yy'` string

The function resolves two-digit years with a pivot at 50, which fits `shows.season`'s real range
(05/06 to 27/28) and is correct until 2050. It is **already** wrong for the awards archive, which
reaches back to 1912 — `'11/12'` resolves to 2011. That is documented in the function's own
docstring and in `glossary.md`, and is handled by carrying the four-digit year instead.

Recorded here not because 2050 is a live risk but because the *class* of assumption is easy to
re-introduce: any new code decoding a season string inherits it.

---

## Accepted risks — known, not being fixed yet

These are settled decisions rather than open questions. They live here so they stay visible.

**Backups sit on the same volume as the database.** `backup_db.py` and `verify_backup.py` both
work; the destination is the problem. This is the only open item whose downside is losing
everything. A genuinely off-box destination is a decision about Darragh's hardware and accounts —
propose options with trade-offs, do not pick one.

**A push to `main` reaches production in ~5 minutes with no human checkpoint.** GitOps polling was
enabled 2026-08-25. This is deliberate and it is also the single largest blast-radius fact about
this repo. The mitigation is the standing rule that anything a visitor can *see* gets described to
Darragh before the push — not a technical control.

**297 `historical_results` rows have `category_name IS NULL`**, 274 of them pre-2001. This needs
real archival research, not a scrape, and no amount of querying will resolve it.
