# Moderator guide

For whoever is logged in to approve submissions and keep the data current -
today that's just you, but this covers everything needed to hand it to a
second moderator later too.

## Logging in

Go to `/admin/login` (there's also a "Moderator login" link in the nav when
you're logged out). Your login is created with `seed_admin.py`, not through
the website - see [deployment.md](deployment.md#running-it-locally-windows)
for how to create or reset one.

There are two roles:
- **admin** - everything a moderator can do, plus creating/revoking invite
  codes.
- **moderator** - queue and show editing, but not invite codes.

## Dashboard

`/admin/` (the single "Admin" link in the nav once logged in) is the
landing page - a "Needs attention" summary (pending submissions, shows
missing a review link or a date, possible duplicate titles, award records
with no society match), each linking straight to the relevant filtered
view, plus a plain list of links to every other admin tool below.

## The moderation queue

`/admin/queue` (also in the nav once logged in) lists every pending member
submission, oldest first, with everything the submitter entered - dates,
venue, production team, ticket link, poster if one was attached.

A show submission or a feature suggestion also emails a fixed inbox in real
time (see "Email notifications" in the deployment guide) - no need to keep
checking these pages manually just in case.

For each one you can:
- **Approve** - it goes live immediately: appears in the society's show
  history, on "This season" if it's the current season, and gets its own
  page.
- **Reject** - it's kept in the database (marked `rejected`) but never shown
  publicly. There's no delete - rejecting is enough to keep it out of sight.
- **Edit details** - opens the full edit form (see below) before you decide,
  in case something needs fixing first (a typo in the show title, a date
  that looks wrong).

## Editing any show

`/admin/shows` lists every approved show, searchable by show or society name,
with a "needs a review link" filter to find shows that have happened but
don't have a published review yet. It defaults to the **current season and
earlier** - seasons announced far in advance are mostly blank "TBA" slots, so
they're hidden by default; pick "All seasons" or a specific one from the
season dropdown to see them. Click **Edit** on any row to open the full
form - every field a submission has, plus:

- **Review status and Review URL.** Pick a status from the dropdown, or paste
  a review URL - **pasting a URL always sets the status to Published**,
  regardless of what the dropdown says. That's deliberate: attaching the link
  is what "publishing" means here.
- **Poster.** Upload one if there isn't one, replace it, or tick "Remove
  current poster" to take it down.
- **Cancelled.** Ticking this shows a "Cancelled" tag next to the show
  everywhere it appears, without removing it from the record.

This is also where you'd fix up a CSV-imported historical show (all
originally-imported shows are editable here too, not just new submissions).
`/admin/shows/dates` (linked from the dashboard) is a quicker, row-by-row
workspace just for opening/closing dates, filterable by season and region.

## Adding a society or show directly

`/admin/societies` has a **+ Add society** link for registering a new
society that isn't in the imported data yet. Each row also has an **Add
show** link, and a society's own edit page has "+ Add a show for this
society" - both open the same full show-edit form (review status included,
since this is you entering it, not a member submission) pre-scoped to that
society. A manually-added society gets an id of 10000 or higher, well clear
of the range imported from the original CSV export, so a future CSV
re-import can never collide with it.

## Invite codes

`/admin/invite-codes` (admin role only). Create a code with an optional label
and expiry date, and share it with whoever needs to submit shows - a whole
society, a region, or just one trusted person, depending on how widely you
want to hand it out. There's no limit on how many people can use the same
code.

**Revoke, don't delete** - the "Revoke" button deactivates a code instantly
(anyone mid-session with it loses access on their next submission attempt)
while keeping it in the list, so any shows submitted with it keep their
history. Reactivate the same way if you revoked it by mistake.

## Seeing inactive societies

The public browse page hides societies with section "Inactive" by default.
Logged in, you'll see a "Show inactive societies" checkbox on that page -
tick it to include them. This is only ever visible to you; anonymous visitors
never see the checkbox or the inactive societies, no matter what's in the
URL.

## Traffic

`/admin/traffic` shows a simple pageview count per page - no cookies, no
visitor tracking, just "how many times has each page loaded" and when it was
last viewed. Useful for a rough sense of whether anyone's actually using the
site before investing more time in it. Admin pages, the CSV export, and
`robots.txt`/`sitemap.xml` aren't counted.

## Society logins

`/admin/invite-codes` doubles as where you create these: pick a society when
creating a code (instead of leaving it blank) and it becomes a **society
login** rather than a one-off submission code. Share it with that society's
secretary and they can log in at `/society/login` to manage their own show
history directly at `/society/` - add or edit past seasons, dates, section,
production team, poster, ticket link. Changes go **live immediately**, no
moderation queue, but they can never set or see the review status/URL fields
- those stay yours to attach, same as for a CSV-imported or publicly
submitted show. They also can't touch any other society's shows (enforced
server-side, not just hidden in the UI).

A society's **default venue** (set on their edit page under `/admin/societies`)
prefills automatically whenever venue is left blank on a new show - by them,
or by a public member submission for that society.

## Awards

`/admin/awards` is where you maintain the AIMS adjudication archive yourself
now - there's no longer an external database to re-import from. It has the
same filters as the public Awards page, plus:

- **+ Add award result** - one record at a time: year, section, category (pick
  an existing one, or "Other" to type a new category name), result, show,
  society, nominee/role, and an optional adjudicator's note. Edit or delete
  any existing record from here too.
- **+ Add a whole category's results at once** - the way you'll use this
  most: set the year/section/category once, then fill in up to 5 nominee rows
  (society, show, nominee, role) and tick a single "Winner" radio button -
  every other filled-in row saves as a Nominee. Blank rows are skipped.
- **"No society match only"** filter - a record whose society name never
  matched a row in `societies` (common for older/defunct/renamed societies).

Editing or adding a record through this page marks it `manual` - it's
permanently safe from ever being overwritten, even if `import_awards.py`
(the old CSV importer, kept only as a historical bootstrap script) is ever
run again.

## Duplicate titles

`/admin/duplicate-titles` suggests pairs of show titles that look like
spelling variants of the same show (e.g. "Beauty & The Beast" vs "Beauty
and the Beast"), alongside genuinely different shows with similar names
(e.g. "Frozen" vs "Frozen Jr.") that you'd dismiss instead. Picking a side
to merge **permanently renames every occurrence** of the other spelling,
across both current shows and the awards archive, with a confirmation
prompt first since there's no undo.

## Venue directory

`/admin/venue-directory` is where a venue stops being a piece of text somebody
typed and becomes a record. Two jobs live there.

**Merging spellings.** The queue up front suggests pairs that might be the same
building. They are only suggestions, and the rule behind them is deliberately
loose - it will happily propose the Galway, Ballinasloe and Claremorris Town
Hall Theatres as one venue, and they are three different buildings. Check who
actually played there before merging; the society is usually the giveaway. A
merge moves every show and every spelling to the venue you keep, and carries
across anything filled in on the one you're folding away.

The queue also flags entries that name no building at all - "TBA", "Various",
or a bare county like "Tipperary". Those aren't merges. If you can work out
which venue was meant, fix the venue on the show itself and the directory
catches up on its own.

**Filling in the detail.** Each venue can carry a town, county, seating
capacity, auditorium type, website, technical spec link and map coordinates.
Every one of them is optional and appears on the public page only once it's
set, so a half-filled venue never looks broken - it just shows less. Leave a
field blank rather than guessing: a wrong capacity is worse than a missing one,
because nobody can see that it's wrong.

The venues with 5 or more productions were researched and filled in during
August 2026 by `enrich_venues.py` (its docstring records where each figure came
from and what was deliberately left blank). Anything you add by hand survives
the nightly rebuild and is never overwritten by it.

## Show info

Each title's own page can show a synopsis and amateur rights/licensing
info (a link to the actual MTI/Concord Theatricals catalog page, and a
rough availability status) - genuinely useful for a society browsing Shows
A-Z for their next production. Nothing here is fetched automatically; look
the title up yourself and add it via the "Add show info" link on that
title's page. Titles with info filled in get a small "info" tag on Shows
A-Z.
