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

That settles 2001, 2004, 2005 and 2007. **2003 and 2006 are not yet sourced**,
though they follow the same pattern.

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

**Clara - open.** The worst affected and the least evidenced.

## Two related findings

- **Athenry Musical Society does not exist in `societies`.** Only "Athenry Youth
  Musical Theatre" (id 130, Western, Out of scope), which is a different
  organisation. Fixing this means creating Athenry as a defunct society.
- **Trophies are named after the societies that donated them** - "BEST PROGRAMME
  (Pioneer Musical Society Trophy)". A society name appearing in a category
  heading is evidence the society existed, not evidence it staged the show.

## Next step

Harvest the captured aims.ie pages systematically rather than one PDF at a time:
every nominations page, results page, society list and show calendar from
2001-2010. That is likely to settle the remaining years for all seven, and would
also backfill pre-2009 production history more generally.

**Nothing here has been written to the live database.** Reassigning award rows
on anything less than a source would be exactly the kind of confident wrong
answer this archive exists not to produce.
