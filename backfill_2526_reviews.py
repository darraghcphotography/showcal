"""Backfill review_url/review_status for 25/26-season shows now that Darragh
has published the missing reviews to aims.ie/reviews. Matched by hand against
the site's full blog-posts-sitemap.xml (91 review URLs) - each candidate was
required to share a genuinely distinctive word with the show's real society
name (a place name or a specific proper noun), not just a generic word like
"musical"/"society"/"choral" that half the archive shares, to avoid
attaching the wrong production's review to a show.

Two matches needed a manual override rather than pure token overlap:
- 327 "Stage One New-Musical Group (S.O.N.G.)" -> we-will-rock-you-song-dundalk:
  this is literally the SONG Dundalk society (see today's earlier
  fix_society_misattributions_2.py) - the token match failed only because
  "S.O.N.G." tokenizes into single letters against the slug's solid "song".
- 329 "St. Marys Musical Society, Navan" -> sister-act-st-mary-s-musical-society:
  apostrophe/pluralisation mismatch ("Marys" vs "Mary's") broke the token
  match, but the name is otherwise an exact match.

18 of the 46 originally-missing 25/26 shows are NOT matched here - either
genuinely not yet on aims.ie's published list, or a same-title collision
across several societies (e.g. two different "Carrie" reviews, neither
naming the actual society) that couldn't be resolved safely. Left alone
rather than guessed.

Safe to re-run: guarded by an assertion of the expected current state.
Defaults to a dry run - pass --apply to actually commit.

Usage:
    py backfill_2526_reviews.py [--db aims.db]
    py backfill_2526_reviews.py --db aims.db --apply
"""
import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent

# (show_id, expected_show_title, expected_society_name, review_url)
MATCHES = [
    (311, "Rock of Ages", "Pop-Up Theatre, Sligo", "https://www.aims.ie/post/review-rock-of-ages-pop-up-theatre"),
    (312, "Disney’s Frozen: The Broadway Musical", "Ballinrobe Musical Society", "https://www.aims.ie/post/review-frozen-ballinrobe-musical-society"),
    (313, "The Wizard of Oz", "St. Mel's Musical Society, Longford", "https://www.aims.ie/post/review-the-wizard-of-oz-st-mel-s-ms"),
    (315, "West Side Story", "Newbridge Musical Society", "https://www.aims.ie/post/review-west-side-story-newbridge-musical-theatre"),
    (316, "Disney’s Frozen: The Broadway Musical", "Clara Musical Society", "https://www.aims.ie/post/review-frozen-clara-musical-society"),
    (317, "Into The Woods", "Kilcock Musical & Dramatic Society", "https://www.aims.ie/post/review-into-the-woods-kilcock-musical-dramatic-society"),
    (318, "We Will Rock You", "Bray Musical Society", "https://www.aims.ie/post/review-we-will-rock-you-bray-musical-society"),
    (319, "Rock of Ages", "Dunboyne Musical Society", "https://www.aims.ie/post/review-rock-of-ages-dunboyne-musical-society"),
    (320, "Chess", "Enniscorthy Musical Society", "https://www.aims.ie/post/review-chess-enniscorthy-musical-society"),
    (321, "The Clockmaker's Daughter", "Avonmore Musical Society", "https://www.aims.ie/post/review-the-clockmaker-s-daughter-avonmore-musical-society"),
    (322, "Anything Goes", "St. Agnes Choral Society", "https://www.aims.ie/post/review-anything-goes-st-agnes-choral-society"),
    (323, "Pippin", "Galway Musical Society", "https://www.aims.ie/post/review-pippin-galway-musical-society"),
    (324, "SpongeBob SquarePants: The Broadway Musical", "Kilmacud Musical Society", "https://www.aims.ie/post/review-the-spongebob-musical-kilmacud-musical-society"),
    (325, "Spring Awakening", "Maynooth University Musical and Dramatics Society", "https://www.aims.ie/post/review-spring-awakening-maynooth-university-musical-society"),
    (326, "The Prince of Egypt", "Tralee Musical Society", "https://www.aims.ie/post/review-the-prince-of-egypt-tralee-musical-society"),
    (327, "We Will Rock You", "Stage One New-Musical Group (S.O.N.G.)", "https://www.aims.ie/post/review-we-will-rock-you-song-dundalk"),
    (328, "Dear Evan Hansen", "North East Musical and Dramatic Society", "https://www.aims.ie/post/review-dear-evan-hansen-north-east-musical-dramatic-society"),
    (329, "Sister Act", "St. Marys Musical Society, Navan", "https://www.aims.ie/post/review-sister-act-st-mary-s-musical-society"),
    (330, "The Clockmaker's Daughter", "St. Mary's Choral Society, Clonmel", "https://www.aims.ie/post/review-the-clockmaker-s-daughter-st-mary-s-choral-society"),
    (331, "Sister Act", "Baldoyle Musical Society", "https://www.aims.ie/post/review-sister-act-baldoyle-musical-society"),
    (332, "Fame", "Leixlip Musical & Variety Group", "https://www.aims.ie/post/review-fame-the-musical-leixlip-musical-variety-group"),
    (333, "Jesus Christ Superstar", "Lisnagarvey Operatic and Dramatic Society", "https://www.aims.ie/post/review-jesus-christ-superstar-lisnagarvey-operatic-and-dramatic-society"),
    (334, "We Will Rock You", "Fortwilliam Musical Society", "https://www.aims.ie/post/review-we-will-rock-you-fortwilliam-musical-society"),
    (335, "West Side Story", "Roscrea Musical Society", "https://www.aims.ie/post/review-west-side-story-roscrea-musical-society"),
    (340, "Little Shop of Horrors", "St. Brendan's Choral and Dramatic Society", "https://www.aims.ie/post/review-little-shop-of-horrors-st-brendan-s-choral-and-dramatic-society"),
    (341, "Annie", "Ratoath Musical Society", "https://www.aims.ie/post/review-annie-ratoath-musical-society"),
    (342, "Calamity Jane", "Waterford Musical Society", "https://www.aims.ie/post/review-calamity-jane-waterford-musical-society"),
    (343, "Jesus Christ Superstar", "Wexford Light Opera Society", "https://www.aims.ie/post/review-jesus-christ-superstar-wexford-light-opera-society"),
]

# Still missing after matching against all 91 aims.ie review URLs - either
# genuinely not published there yet, or a same-title collision across
# several societies that couldn't be told apart safely (printed, not
# guessed):
STILL_MISSING = [
    (293, "The Sound of Music", "Ballyshannon Musical Society"),
    (296, "The Sound of Music", "Belfast Operatic Company"),
    (297, "Bonnie & Clyde", "Creative Minds Productions"),
    (298, "Grease", "SGPA"),
    (299, "Carrie", "Fermanagh Musical Theatre"),         # 2 other Carrie reviews exist (UCD, UCC) - neither is this one
    (300, "Young Frankenstein", "Nenagh Choral Society Youth Academy"),
    (301, "The Clockmaker's Daughter", "Marian Choral Society, Tuam"),  # 2 other Clockmaker's Daughter reviews exist - neither is this one
    (302, "Encore (Cabaret night)", "Fermoy Musical Society"),
    (303, "My Fair Lady", "Rathmines & Rathgar Musical Society"),  # 2 other My Fair Lady reviews exist - neither is this one
    (304, "The Clockmaker's Daughter", "Tralee Musical Society"),
    (305, "Come From Away", "Portlaoise Musical Society"),  # 4 other Come From Away reviews exist - none is this one
    (306, "The Addams Family", "East Clare Musical Society"),
    (307, "Carrie", "Queen's Musical Theatre Society"),
    (314, "All Shook Up", "University of Limerick Musical Theatre Society"),
    (336, "The Band", "Letterkenny Music & Drama Group"),
    (337, "A Christmas Carol", "Fortwilliam Musical Society"),
    (338, "Shrek the Musical", "Sligo Musical Society"),   # a different society's Shrek is on the list (Ballinasloe), not this one
    (339, "Curtains", "Glencullen Dundrum MDS"),           # 2 other Curtains reviews exist - neither is this one
]


def run(db_path, apply_changes):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    log = []

    def note(msg):
        log.append(msg)
        print(msg)

    for show_id, title, society_name, url in MATCHES:
        show = conn.execute(
            "SELECT shows.show, societies.name AS society_name, shows.review_status, shows.review_url "
            "FROM shows JOIN societies ON societies.id = shows.society_id WHERE shows.id = ?",
            (show_id,),
        ).fetchone()
        assert show is not None, f"show {show_id} missing"
        assert (show["show"], show["society_name"]) == (title, society_name), (
            f"show {show_id}: expected {(title, society_name)}, found "
            f"{(show['show'], show['society_name'])} - skipping, state has changed"
        )
        note(f"UPDATE show {show_id} '{title}' ({society_name}): review -> {url}")
        if apply_changes:
            conn.execute(
                "UPDATE shows SET review_status = 'Published', review_url = ? WHERE id = ?",
                (url, show_id),
            )

    print()
    print(f"Still missing (not applied, review ids): {[m[0] for m in STILL_MISSING]}")
    for show_id, title, society_name in STILL_MISSING:
        print(f"  {show_id}: {society_name} - {title}")

    if apply_changes:
        conn.commit()
        print(f"\nApplied. {len(MATCHES)} shows updated with a review link.")
    else:
        print(f"\nDry run only - {len(log)} planned updates above, nothing written. Pass --apply to commit.")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "aims.db"))
    parser.add_argument("--apply", action="store_true", help="Actually commit the changes (default: dry run)")
    args = parser.parse_args()
    run(args.db, args.apply)
