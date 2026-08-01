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

## The moderation queue

`/admin/queue` (also in the nav once logged in) lists every pending member
submission, oldest first, with everything the submitter entered - dates,
venue, production team, ticket link, poster if one was attached.

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
don't have a published review yet. Click **Edit** on any row to open the full
form - every field a submission has, plus:

- **Review status and Review URL.** Pick a status from the dropdown, or paste
  a review URL - **pasting a URL always sets the status to Published**,
  regardless of what the dropdown says. That's deliberate: attaching the link
  is what "publishing" means here.
- **Poster.** Upload one if there isn't one, replace it, or tick "Remove
  current poster" to take it down.
- **Cancelled.** Ticking this shows a "Cancelled" tag next to the show
  everywhere it appears, without removing it from the record.

This is also where you'd fix up a CSV-imported historical show (all 570
originally-imported shows are editable here too, not just new submissions).

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

The public browse page hides societies with tier "Inactive" by default.
Logged in, you'll see a "Show inactive societies" checkbox on that page -
tick it to include them. This is only ever visible to you; anonymous visitors
never see the checkbox or the inactive societies, no matter what's in the
URL.
