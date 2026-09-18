# Collapsed societies in the awards archive

Some award records are filed under a society that did not stage the show. Two
different societies have been merged into one name in the source AIMS data, so
their nominations and wins appear as one society's record.

Reported 2026-09-17 by Jack Rawlings, who spotted that Athenry Musical Society
is missing from the site entirely and that its awards show under **Athlone**
Musical Society. He also noted it appears on aims.ie the same way, which is the
first clue that this is not our bug.

**It isn't.** Every affected row carries the *same society id* in
`AIMS_Awards - Results.csv`, so the two societies were already merged before the
data reached us. We imported it faithfully. The consequence is that the source
cannot be used to separate them again - that needs outside evidence.

## How to find them: two tiers in one season

A society competes in **one** section per season, Gilbert or Sullivan. So a
society with award rows in **both tiers in the same year** is structurally
impossible, and is the fingerprint of two societies collapsed into one.

Run against the source CSV, that test finds seven:

| Society | Affected years | Award rows |
|---|---|---|
| Clara Musical Society | 8 | 34 |
| Athlone Musical Society | 6 | 27 |
| Tralee Musical Society | 3 | 15 |
| Avonmore Musical Society | 3 | 11 |
| Kilcock Musical & Dramatic Society | 2 | 9 |
| UCC Musical Theatre Society | 1 | 2 |
| Twin Productions | 1 | 2 |

**100 award rows, about 2% of the archive.**

**The real total is larger.** The tier test only works from 2001, when AIMS
introduced the two sections - which is exactly why every conflict starts in
2001. Before that there is no tier to give it away, but the collapse is still
there: Athlone shows both *Fiddler on the Roof* and *Mack & Mabel* in 2000.

## A second test: the people don't overlap

Split a suspect society's conflicting years by tier and compare the nominees.
For Athlone across 2001-2007:

- **Gilbert side:** Dave Langan, Heather Shine, Linda Murray, Blaithin Walsh,
  Majella Flanagan, Petrova Mulvey, Colin Hughes and others
- **Sullivan side:** Brian Brady, Pat Naughton, Cathriona O'Connell, Paula
  Short, Peter Kennedy, Marilyn Bane
- **Overlap: none**

Two disjoint casts and crews under one name. This test says *there are two
societies*; it cannot say which is which. That takes a source.

## Do not use the `productions` table as evidence

`productions` is derived from `shows`/`historical_results`/`historical_reviews`,
so it inherits the same collapse rather than corroborating it. Athlone shows two
productions in 1999 and 2000 there for the same reason. Checking one against the
other proves nothing.

## The outside source: old aims.ie on the Wayback Machine

The ShowTimes review archive only runs from **09/10** onward, so it cannot reach
the disputed years. The official **AIMS nominations lists** can, and the pre-Wix
aims.ie published them. The Internet Archive holds aims.ie from **January 2001**,
with about 7,220 distinct URLs captured before 2010.

Four nomination PDFs survive:

| Year | URL (prefix with `http://web.archive.org/web/<timestamp>id_/`) | Capture | State |
|---|---|---|---|
| 2001/02 | `http://www.aims.ie/seminar/nominations.pdf` | `20030524153916` | Truncated - outer panels only |
| 2004 | `http://aims.ie/awards/2004/noms2004.pdf` | `20040623091916` | Text extracts cleanly |
| 2005 | `http://aims.ie/awards/2005/Nominations2005.pdf` | `20051217093710` | Text extracts cleanly |
| 2007 | `http://www.aims.ie/awards/2007/noms2007.pdf` | `20071120132435` | Text extracts cleanly |

**Correction on that first row, and it saves someone a wasted afternoon.** It
was previously listed as a 2003 list needing OCR. It is neither.

- It is the **2001/2002** leaflet - the banquet it names is 15 June 2002 - kept
  at a `/seminar/` path and merely *captured* in 2003.
- It is **not a scan**. The file holds 33 FlateDecode streams and no image
  filter of any kind, so there is nothing for OCR to read.
- The archived copy is **truncated**: 57,344 bytes with no xref table, no
  trailer and no page tree, which is why PyMuPDF opens it to zero pages. Only
  three content streams still decompress - the outer panels of a folded leaflet.
  The inner panels, which carried the nominations, are in the missing bytes, and
  there is only one capture, so there is no better copy to try.

What survives is in `archive_harvest/noms2003/noms2003.salvaged.txt`: the
Programme category (Athlone - *42nd Street*, Galway - *The Scarlet Pimpernel*,
St Mel's Longford - *Fiddler on the Roof*) and the two section adjudicators.
That corroborates our own 2002 Best Programme row for Athlone and nothing more.

## The harvest

`scripts/harvest_aims_archive.py` pulls the captured pages wholesale. The CDX
index returns **21,427 captures** for the domain across 2001-2010, of which
**13,724** are documents rather than images, stylesheets or redirects - far more
than the 1,500-2,500 first estimated, because the old site carried a show
database, a review section and a busy discussion forum on top of the awards
pages. Use `--match` to take the useful part first.

Two HTML pages found this way are worth more than any of the PDFs, because they
are the **official lists, in full, for the earliest disputed year**:

| Page | Capture | What it gives |
|---|---|---|
| `/.%5cseminarnominations.htm` | `20010720034012` | Every AIMS 2000/2001 nomination, by category and section |
| `/.%5cseminarsocieties.htm` | `20010720034927` | The member societies of 2001, split Gilbert / Sullivan |

## What is proven, and what is not

**Athenry Musical Society - confirmed** from the official lists, matching rows
we currently hold under Athlone, all on the Sullivan side:

- 2007, Best Comedienne, Marilyn Bane as Adelaide, *Guys and Dolls*
- 2005, Best Male Singer, Pat Naughton as Emile de Becque, *South Pacific*
- 2005, Best House Management, *South Pacific*
- 2004, Best Stage Manager, Brian Brady, *My Fair Lady*
- **2001, Best Director (Sullivan, Tommy Ebbs Trophy), Paula Short, *Anything
  Goes*** - the official 2000/2001 list prints it against *Athenry Musical
  Society*; we hold it as row `10950` under Athlone. Same person, same show,
  same section, different society.

**Athenry was a member society in its own right**, and on the side the
structural test predicted: the 2001 society list opens its **Sullivan** column
with "Athenry Musical Society", immediately above "Avonmore Musical Society".
That is worth stating plainly, because until now Athenry existed in this
investigation only as an absence.

**2003 and 2006 are now sourced too**, from the official section pages:

- 2003, Sullivan results: *Best Stage Manager - Athenry Musical Society, Brian
  Brady, Sugar* and *Best Comedian - Athenry Musical Society, Peter Kennedy,
  Jerry, Sugar*. We hold both under Athlone against *Some Like It Hot*, which is
  the same musical under its other title - the people, roles, section and year
  all match.
- 2006, Sullivan nominations: *Cathriona O'Connell as Lady Jaqueline, Me & My
  Girl, Athenry Musical Society*. We hold it as row `11463`, under Athlone.

**And a year the structural test never flagged: 2008.** The official 2008
Sullivan page lists exactly two Athenry entries - Best Chorus and Best Visual,
both *Pirates of Penzance* - and we hold exactly those two rows under Athlone.
The word "Athlone" does not appear on that page at all.

That matters beyond this one society. **The two-tier test under-counts**, and
not only before 2001 as already noted: it cannot see a year in which just one of
the two collapsed societies was nominated, because there is no conflict to spot.
2008 is such a year. Any count of affected rows taken from that test alone - the
100 above included - is a floor, not a total.

**Avonmore / Pioneer - a strong lead.** One 2015 row is labelled *"Pioneer
Musical Society"* while carrying **Avonmore's** society id: Best Comedian,
*Kiss Me Kate*. Avonmore's 2015 conflict is Gilbert *The Witches of Eastwick*
against Sullivan *Kiss Me Kate* - so the Sullivan side is likely Pioneer's.
Here the source data leaked the correct name on a single row. Note that
`societies` already holds **Pioneer Musical & Dramatic Society** (id 160);
whether that is the same body as "Pioneer Musical Society" is a question for
AIMS, not an assumption to make here.

**Tralee 2004 - suggestive only.** The official 2004 list ties Tralee to
*Children of Eden* in four places; our Sullivan-side *The King & I* is
uncorroborated. Not enough to act on.

**Clara / Clane - confirmed, and it is the whole of the Clara problem.** The
worst-affected society turns out to be collapsed with **Clane Musical &
Dramatic Society**, which is one letter away and already exists in `societies`
(id 25) - so this is a reassignment, not a society that has to be created.

The split is clean and it runs one way in every sourced year: the **Gilbert**
side is Clane's, the **Sullivan** side is Clara's. Read directly off the
official pages:

- 2003 Gilbert: *Shane McGrath as Jesus* and *Willie Bermingham as Pontius
  Pilate*, *Jesus Christ Superstar* - both printed against **Clane**. We hold
  both under Clara.
- 2004 Gilbert: *Marie Cusack, Best Stage Manager* and *Brendan Farrell as
  Ko-Ko, Best Comedian*, *Hot Mikado* - both **Clane**. We hold both under Clara.
- 2004 roster: the season's own society list gives *Clane - Hot Mikado - g* and
  *Clara - Guys & Dolls - s*, on separate lines of the same table.

`scripts/match_awards_to_archive.py --society "Clara Musical Society"
--summary` returns Clane for the Gilbert side of 2001, 2002, 2004, 2005, 2006,
2007 and 2008, and Clara's own name for the Sullivan side. Nothing points the
other way in any year.

## Two related findings

- **Athenry Musical Society does not exist in `societies`.** Only "Athenry Youth
  Musical Theatre" (id 130, Western, Out of scope), which is a different
  organisation. Fixing this means creating Athenry as a defunct society.
- **Trophies are named after the societies that donated them** - "BEST PROGRAMME
  (Pioneer Musical Society Trophy)". A society name appearing in a category
  heading is evidence the society existed, not evidence it staged the show.

## Reading the harvest back

`scripts/match_awards_to_archive.py` takes a society's award rows, looks each
nominee up in the harvested text, and reports the society the official page
prints beside them. `--summary` gives one line per season and section, which is
the shape the question is actually asked in - it is the section, not the
individual row, that belongs to one body or the other.

**It offers both neighbours rather than choosing.** The pages are table rows
flattened to text and they disagree on column order: the 2001 nominations read
nominee, show, society, while the 2003 results print the society first. So the
nearest name in one direction is the row's own and in the other it is the
neighbouring row's, and nothing local says which. Picking by distance produced
confident wrong answers in testing - the 2001 Athenry row came back as Galway.
What settles it is repetition across rows, seasons and pages, so the tool tallies
and shows its working, with the capture date and URL on every line.

A vote only counts when the row's **show title** also appears beside the
nominee. A bare name match is a common name somewhere else on the site.

## The queue: /admin/collapsed-societies

Deciding what to do about all this happens in the app, not in a script.

The unit is a **season and a section** - `(society, year, tier)` - because that
is what the underlying fact is shaped like. A society competes in one section
per season, so when its rows show up in both, it is the whole of one side that
belongs to somebody else, not one stray row.

Three things about it are deliberate:

- **Nothing is applied by import.** `scripts/import_collapsed_suggestions.py`
  writes *proposals* into `collapsed_society_suggestions`, each carrying the
  capture date and URL it was read off, and the page links back to that page.
  Moving an award record is a human decision made on the evidence, never a
  consequence of loading it.
- **Every move is reversible from the page.** The decision row keeps the name
  the records carried before, so Undo needs no database shell. A group that has
  already been moved stays on the page for exactly this reason.
- **A suggestion can be right and still not applicable.** Athenry has no
  `societies` row, so the queue shows it as *"not on our list"* rather than
  offering a button that cannot work. Creating Athenry as a defunct society is
  the prerequisite for applying its side, and that is a separate decision.

The dashboard counter is deliberately counted from *suggestions*, not from
conflicts: a conflicted season with no evidence behind it is not work anybody
can do, and a counter that can never reach zero is worse than no counter.

By default the page lists the seasons in conflict, the seasons with evidence,
and the seasons already decided. `?all=1` adds the quiet ones - **a season with
neither flag can still be misfiled, which is exactly where 2008 was hiding.**

### Getting the evidence into a database

The harvest is gitignored and lives only on the machine that ran it, so the
findings travel as a file:

```
py scripts/import_collapsed_suggestions.py --export docs/collapsed_suggestions.json
docker compose exec aims-web python scripts/import_collapsed_suggestions.py     --db /data/aims.db --suggestions /data/collapsed_suggestions.json
```

`docs/collapsed_suggestions.json` is committed for that reason, and
because without it nobody could reproduce or check the findings without
re-running a multi-hour harvest. The loader re-resolves societies **by name**,
not by id, because a suggestions file is built against one database and loaded
into another.

## Next step

Two of the seven are now answered. For the rest:

- **Tralee, Avonmore, Kilcock** come back as themselves on the section that is
  theirs, with nothing consistent on the other side. Their partner societies are
  not in the harvest yet, or are not named on the pages held so far.
- **UCC and Twin Productions** have no nominee-bearing rows in range at all.
- The harvest so far is the awards and roster pages. **Around 13,000 documents
  remain**, including the old show database and the review section, which is the
  obvious next place to look for the missing partners.

**Nothing here has been written to the live database.** Reassigning award rows
on anything less than a source would be exactly the kind of confident wrong
answer this archive exists not to produce.
