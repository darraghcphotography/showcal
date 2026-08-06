"""One-off/re-runnable seed of show_info for the top 30 most-performed titles
on the AIMS circuit (by combined shows + historical_results count at the time
this was written). Synopses and licensing info were gathered via web search,
not guessed - rights_url is only set where a specific working page turned up
directly in a search result, never constructed. Safe to re-run: it's an
upsert, and moderator edits made afterwards via /admin/titles/<title>/info
will simply be overwritten if you run this again - it's meant as a one-time
bootstrap for these 30 titles, not something to keep re-running.

Usage:
    py enrich_show_info.py [--db aims.db]
"""
import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent

DATA = [
    ("Jesus Christ Superstar",
     "The final days of Jesus of Nazareth, told through Judas's eyes as he wrestles with betraying his friend. "
     "A rock opera told entirely through song, exploring the relationships between Jesus, Judas, Mary Magdalene, "
     "the disciples and the Roman authorities in the last seven days before the crucifixion.",
     None, "Contact publisher", "Licensed by Andrew Lloyd Webber and Tim Rice's estate via Concord Theatricals."),
    ("Oklahoma!",
     "Rodgers and Hammerstein's first collaboration, based on the play Green Grow the Lilacs. Headstrong farm girl "
     "Laurey is caught in a love triangle between cowboy Curly and hired hand Jud, coming to a head at the box social.",
     None, "Contact publisher", "Licensed through Concord Theatricals (Rodgers & Hammerstein catalogue)."),
    ("Fiddler on the Roof",
     "Set in the village of Anatevka, dairyman Tevye tries to protect his five daughters and hold on to tradition "
     "as the world around them changes, against the rising anti-Semitism of Czarist Russia.",
     "https://www.mtishows.com/fiddler-on-the-roof", "Contact publisher",
     "Note: the licence includes a required Choreographic Guide preserving Jerome Robbins' original staging."),
    ("West Side Story",
     "A modern Romeo and Juliet set among rival New York gangs the Jets and the Sharks. Tony falls for Maria, "
     "sister of the Sharks' leader, and their love is caught in the escalating gang rivalry.",
     "https://www.mtishows.com/west-side-story", "Contact publisher",
     "A School Edition is also available for younger/amateur casts."),
    ("My Fair Lady",
     "Based on Shaw's Pygmalion. Cockney flower-girl Eliza Doolittle is taken on by Professor Henry Higgins, who "
     "bets he can pass her off as a duchess by teaching her to speak like the upper class.",
     "https://www.mtishows.com/my-fair-lady-0", "Contact publisher",
     "MTI represents the Lerner & Loewe catalogue for secondary/amateur performance rights."),
    ("Oliver!",
     "Lionel Bart's musical based on Dickens' Oliver Twist. Orphan Oliver escapes a workhouse for London, falls in "
     "with Fagin's gang of pickpockets, and is eventually taken in by the benevolent Mr Brownlow.",
     "https://www.mtishows.com/oliver", "Contact publisher", None),
    ("Guys and Dolls",
     "A romantic comedy set in Damon Runyon's New York. Gambler Nathan Detroit needs cash for the biggest craps "
     "game in town, while fellow gambler Sky Masterson chases missionary Sarah Brown on a bet.",
     "https://www.mtishows.com/guys-and-dolls", "Contact publisher", None),
    ("Sister Act",
     "Disco singer Deloris Van Cartier witnesses a murder and is hidden in a convent, where she clashes with the "
     "strict Mother Superior but transforms the choir - and the whole community - with her voice.",
     "https://www.mtishows.com/sister-act", "Contact publisher",
     "Music by Alan Menken; a family-friendly gospel-infused comedy popular with community theatres."),
    ("Sweeney Todd",
     "Sondheim's musical thriller: an unjustly exiled barber returns to London seeking revenge on the judge who "
     "wronged him, while his landlady Mrs Lovett disposes of his victims by baking them into her pies.",
     "https://www.mtishows.com/sweeney-todd", "Contact publisher",
     "Performance rights for the songs must be cleared separately via the relevant small-rights agency."),
    ("All Shook Up",
     "A guitar-playing roustabout rides into a straitlaced 1950s Midwestern town and shakes up its social order, "
     "loosely based on Twelfth Night, built entirely around the Elvis Presley songbook.",
     None, "Contact publisher",
     "Licensed through Theatrical Rights Worldwide; School Edition and Young@Part editions also exist."),
    ("The Pirates of Penzance",
     "A Gilbert & Sullivan comic opera. Apprentice pirate Frederic falls for Mabel, daughter of Major-General "
     "Stanley, but discovers a leap-year technicality means he's still years away from finishing his apprenticeship.",
     "https://www.mtishows.com/the-pirates-of-penzance", "Contact publisher",
     "The 1879 original is public domain; the specific edition/arrangement a society uses may still need clearing."),
    ("The Addams Family",
     "Wednesday Addams has fallen for a 'normal' young man and begs her father Gomez to keep it secret from "
     "Morticia - unravelling over one chaotic family dinner with her boyfriend's parents.",
     None, "Contact publisher",
     "Licensed through Theatrical Rights Worldwide; Young@Part/School Edition versions available."),
    ("Hot Mikado",
     "A jazz/swing reimagining of Gilbert & Sullivan's The Mikado - Nanki-Poo and Yum-Yum's forbidden romance "
     "navigates the absurd laws of Titipu, set to a hot jazz and blues score.",
     "https://www.mtishows.com/hot-mikado", "Contact publisher", None),
    ("Chess",
     "Music by ABBA's Benny Andersson and Björn Ulvaeus, lyrics by Tim Rice. At the height of the Cold War, two "
     "chess grandmasters compete for the World Championship - and for the love of the same woman.",
     None, "Contact publisher",
     "Amateur rights historically controlled by Samuel French/Concord Theatricals; also released via MTI Europe."),
    ("Me and My Girl",
     "Set in 1930s London, cockney Bill Snibson discovers he's heir to a fortune and title, but must decide whether "
     "to adopt an aristocratic lifestyle or stay true to himself and his girlfriend Sally.",
     "https://www.concordtheatricals.co.uk/p/12161/me-and-my-girl", "Contact publisher",
     "Also licensed via Samuel French and Origin Theatrical in some territories."),
    ("Carousel",
     "Rodgers and Hammerstein's second collaboration, adapted from Molnár's play Liliom. Carnival barker Billy "
     "Bigelow and millworker Julie Jordan fall in love; after Billy dies attempting a robbery, he's offered a "
     "chance at redemption.",
     None, "Contact publisher", "Licensed through Concord Theatricals (Rodgers & Hammerstein catalogue)."),
    ("The Mikado",
     "A Gilbert & Sullivan comic operetta set in the fictional Japanese town of Titipu. Nanki-Poo flees an "
     "unwanted marriage and falls for Yum-Yum, who is betrothed to the Lord High Executioner Ko-Ko.",
     None, "Contact publisher",
     "The 1885 original is public domain; the specific edition/arrangement a society uses may still need clearing."),
    ("Evita",
     "Charts Eva Perón's rise from illegitimate child to the most powerful woman in Argentina, narrated by Che, "
     "with songs including \"Don't Cry for Me, Argentina\".",
     "https://alwshowlicensing.com/show/evita/", "Contact publisher",
     "UK & Ireland rights via ALW Show Licensing; also available through Concord Theatricals."),
    ("The King & I",
     "Welsh widow Anna Leonowens arrives in 1860s Siam to teach the King's children, and she and the King form an "
     "unlikely, transformative friendship across a vast cultural divide.",
     None, "Contact publisher", "Licensed through Concord Theatricals (Rodgers & Hammerstein catalogue)."),
    ("South Pacific",
     "Set on a WWII South Pacific island, nurse Nellie falls for French planter Emile but struggles with prejudice "
     "on learning his children's mother was a native islander - a theme mirrored in a second couple's story.",
     None, "Contact publisher", "Licensed through Concord Theatricals (Rodgers & Hammerstein catalogue)."),
    ("Jekyll & Hyde",
     "Frank Wildhorn's musical adaptation of Robert Louis Stevenson's novella - a doctor's experiment to separate "
     "good and evil in human nature unleashes a murderous alter ego.",
     "https://www.mtishows.com/jekyll-hyde", "Contact publisher",
     "Song performance rights must be cleared separately via the relevant small-rights agency."),
    ("Calamity Jane",
     "In 1876 Deadwood City, sharpshooter Calamity Jane's mission to bring a glamorous actress back from Chicago "
     "goes wrong, setting off a chain of romantic mix-ups ending in a double wedding.",
     "https://www.mtishows.com/calamity-jane", "Contact publisher",
     "Amateur rights for the UK and Ireland are handled by Music Theatre International."),
    ("Legally Blonde",
     "Sorority star Elle Woods follows her ex-boyfriend to Harvard Law School to win him back, and ends up proving "
     "herself - and everyone else - wrong about what she's capable of.",
     "https://www.mtishows.com/legally-blonde-the-musical", "Contact publisher",
     "A 60-minute JR. edition is also available for younger casts."),
    ("Man of La Mancha",
     "Imprisoned author Miguel de Cervantes stages a play-within-a-play as his defence: the story of Alonso "
     "Quijana, an old man who believes himself the chivalrous knight Don Quixote.",
     None, "Contact publisher", "Licensed through Concord Theatricals."),
    ("The Hired Man",
     "Based on Melvyn Bragg's novel, tracing one Cumbrian family's journey between farm labour and coal mining in "
     "the early twentieth century, through hiring fairs, union meetings and the changing rural way of life.",
     "https://alwshowlicensing.com/show/the-hired-man/", "Contact publisher",
     "Rights for the UK and Ireland are typically via the Really Useful Group/ALW Show Licensing."),
    ("Hello, Dolly!",
     "Matchmaker Dolly Levi travels to Yonkers to find a match for miserly merchant Horace Vandergelder - and "
     "engineers events so that she ends up matching herself to him instead.",
     None, "Contact publisher", "Licensed through Concord Theatricals."),
    ("Anything Goes",
     "Cole Porter's shipboard comedy aboard the S.S. American, as stowaway Billy pursues the woman he loves while "
     "nightclub singer Reno Sweeney causes chaos of her own among the passengers.",
     "https://www.concordtheatricals.co.uk/p/44584/anything-goes-2022-revision", "Contact publisher",
     "Two licensable versions exist (1962 and a 2022 revision) - check which your society intends to use."),
    ("Titanic The Musical",
     "Tells the story of the RMS Titanic's maiden voyage and sinking through the eyes of passengers and crew "
     "across the ship's different classes, as they confront the disaster together.",
     None, "Contact publisher", "Licensed through Concord Theatricals."),
    ("Godspell",
     "A musical retelling of the Gospel of Matthew through parables, songs and comic sketches, centred on themes "
     "of kindness, forgiveness and community.",
     "https://www.mtishows.com/godspell", "Contact publisher",
     "Three editions exist (1971 original, 2012 revision, and Godspell JR.) - each licensed separately."),
    ("The Merry Widow",
     "Franz Lehár's operetta: a wealthy young widow, Hanna, is courted by her countrymen hoping to keep her "
     "fortune at home, while her on-off romance with the roguish Count Danilo takes centre stage.",
     None, "Contact publisher",
     "The 1905 original is public domain in most territories; specific translations/arrangements may still require clearing."),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)

    # Two titles were seeded with the wrong case the first time this ran,
    # silently orphaning those rows - real shows/historical_results titles
    # are "Fiddler on the Roof" and "Man of La Mancha", not "... On The
    # Roof"/"Man Of La Mancha". Fixed here (rather than relying on the
    # upsert below, which would just insert a second correctly-cased row
    # and leave the old one behind) so this stays a single re-runnable step.
    # If the correctly-cased row already exists (e.g. another script already
    # upserted premiere data onto it), drop the old duplicate instead of
    # renaming into a collision - the DATA loop below will fill in synopsis/
    # rights on the surviving row either way.
    CASING_FIXES = {
        "Fiddler On The Roof": "Fiddler on the Roof",
        "Man Of La Mancha": "Man of La Mancha",
    }
    for old, new in CASING_FIXES.items():
        if conn.execute("SELECT 1 FROM show_info WHERE show = ?", (new,)).fetchone():
            conn.execute("DELETE FROM show_info WHERE show = ?", (old,))
        else:
            conn.execute("UPDATE show_info SET show = ? WHERE show = ?", (new, old))

    for show, synopsis, rights_url, rights_status, note in DATA:
        full_synopsis = synopsis + (f" {note}" if note else "")
        conn.execute(
            """
            INSERT INTO show_info (show, synopsis, rights_url, rights_status, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(show) DO UPDATE SET
                synopsis = excluded.synopsis, rights_url = excluded.rights_url,
                rights_status = excluded.rights_status, updated_at = excluded.updated_at
            """,
            (show, full_synopsis, rights_url, rights_status),
        )
    conn.commit()
    print(f"Upserted show_info for {len(DATA)} titles")

    missing = []
    for show, *_ in DATA:
        exists = conn.execute(
            "SELECT 1 FROM shows WHERE show = ? UNION SELECT 1 FROM historical_results WHERE show = ? LIMIT 1",
            (show, show),
        ).fetchone()
        if not exists:
            missing.append(show)
    print("Titles with no matching show/historical_results row (check spelling):", missing or "none")
    conn.close()


if __name__ == "__main__":
    main()
