# How the scripts of fern and Veritasium are built (beat maps, craft, rules)

Research date 2026-11-21. Builds on `story-not-slides.md` (cut rhythm, numeric-sentence share, turns a minute) and does
not repeat it. This file is about the script itself: openings, interleaving of person and science, voices, re-hooks,
mechanism explanation, endings.

## 0 Method, sources, honesty about limits

- Source of every transcript: the Rosetta transcript pages (rosetta.to/u/veritasium/..., rosetta.to/u/fern-tv/...),
  which republish the YouTube captions. Nothing was downloaded except those pages' text. No video frames were seen.
- Limits that matter when reading the numbers:
  - Captions are machine-made. Veritasium's Midgley and Mullis films come without punctuation, so sentence-length
    statistics exist only for the punctuated films (Citicorp, Dirac, all fern films). Names are garbled
    ("Durac", "Lameasure", "Ethel"); I use the correct spelling.
  - There are no per-line timestamps. Veritasium films carry an official chapter list (times below marked "ch."). All
    other times are word position x runtime and are good to about +/- 15 s (a sponsor read shifts them). Runtimes of
    Flight 103 (about 28 min), the console film (about 18 min) and the KKK film (about 47 min) are estimates.
  - "Picture" columns are inferred from the words (place cards, interviews, demos), not seen. Marked "(inf.)".
  - Reading depth: openings, every chapter turn and every ending were read in full; middles were read by one-minute
    skeletons plus targeted searches for quotes, problems and turns. Statistics are computed over the full text.
- Substitutions: no Semmelweis film exists on either channel. "How One Line in the Oldest Math Text..." and "Why No One
  Has Measured The Speed Of Light" were not on the Rosetta list and are skipped. "Rotating bodies" skipped. The
  Veritasium titles used are the nearest human-plus-mechanism films that were readable.

| code | channel | film | runtime | role in this study |
| --- | --- | --- | --- | --- |
| Mi | Veritasium | The Man Who Accidentally Killed The Most People In History (Midgley/Patterson), 2022 | 24:57 | parallel lives, one mystery |
| Ci | Veritasium | How a Student's Question Saved This NYC Skyscraper (LeMessurier), 2025 | about 33 min | single protagonist, secret, clock |
| Mu | Veritasium | The Man Who Took LSD and Changed The World (Kary Mullis, PCR), 2024 | about 33 min | genius-misfit biography around one mechanism |
| Di | Veritasium | The Man Who Accidentally Discovered Antimatter (Dirac), 2025 | 35:23 | heavy-theory film with a thin human thread (counter-example) |
| F103 | fern | The Strange Attack on Flight 103, 2026 | about 28 min | investigation, witnesses, present-tense scenes |
| Co | fern | The $1 Billion Coca-Cola Machine, 2026 | 16:45 | "you" as protagonist, no historical person |
| SS | fern | Why the U.S. President Is Almost Impossible to Kill, 2026 | 27:12 | frame story plus history plus mechanism |
| Cn | fern | The Hunt for the Lost Communist Console, 2025 | about 18 min | object quest, crew on screen |
| KK | fern | How an FBI Agent Infiltrated the KKK (Scott Payne), 2025 | about 47 min | interview-led; used only for the voice question |

## 1 Script statistics (computed over the full transcripts)

| film | words/min | median sentence (words) | p90 sentence | sentences <= 6 words | >= 25 words | questions/min | "but"/min | you/min | I/min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mi | 152 | n/a | n/a | n/a | n/a | n/a | 1.2 | 1.1 | 0.5 |
| Ci | 170 | 12 | 23 | 19% | 8% | 0.83 | 1.7 | 1.7 | 1.8 (interviewee) |
| Mu | 157 | n/a | n/a | n/a | n/a | n/a | 1.2 | 2.6 | 1.5 |
| Di | 173 | 14 | 27 | 17% | 14% | 0.76 | 1.4 | 1.9 | 0.7 |
| F103 | about 157 | 12 | 21 | 18% | 5% | 0.38 | 0.8 | 0.1 | 0.6 |
| Co | 177 | 11 | 23 | 19% | 8% | 0.42 | 1.4 | 5.1 | 0.0 |
| SS | 154 | 12 | 22 | 15% | 6% | 0.48 | 0.9 | 0.6 | 0.2 |
| Cn | about 154 | 11 | 19 | 21% | 5% | 0.56 | 0.8 | 1.4 | 0.3 |
| KK | about 160 | 10 | 24 | 27% | 10% | 0.36 | 1.2 | 1.5 | 4.7 |

Readings:
- Spoken pace is 150-177 words/min in every film. Median sentence 10-14 words; a short sentence (<= 6 words) every
  5th-6th sentence (15-21%, 27% in the interview-heavy KK); a 25+ word sentence only 5-14% of the time (Veritasium 8-14%,
  fern 5-10%). Mean sentence length is 12-15 words. Both channels write for the ear in the same register.
- The words "but / however / yet / until / suddenly" appear 0.8-1.7 times a minute, i.e. a turn word every 35-75 s. In
  the broader turn count of the earlier study the range was 1.5-3 a minute; the two agree that a turn arrives well
  inside every minute-and-a-half.
- Explicit question marks are rare (0.4-0.8 a minute). The questions that matter are few and placed: one at the top,
  one at each big pivot. The rest of the tension is built from statements ("this was about to send the greatest
  physicists spiraling").
- Explicit analogy markers ("like a", "imagine", "think of") run only 0.1-0.4 a minute in every film. Analogy is carried by
  the picture/demo (section 6), not by the words.
- Person of the narrator: fern is third person, present tense, nearly no "I" (F103, SS, Co); "you" is a character only in
  Co (5.1 a minute) and in the SS hypothetical. Veritasium is "I/we" with an on-camera host and uses "you" 1-3 a minute
  as the thinker ("you might expect...").
- Direct quotation density (spans in quotation marks in the caption text): Ci 12 spans = 173 words (about 5% of the
  film), Di 9 spans = 76 words, SS 3 spans = 27 words, Cn 1, F103 0, Co 0. Median quoted span 8-13 words. In KK 51 spans
  = 678 words, plus 37% of the film is first-person interview audio.

## 2 Beat maps

Functions: HOOK, STAKES, QUESTION, GUESS (viewer or character expectation), COMPLICATION, HUMAN (a person's moment),
EXPL (explanation), REVERSAL, REHOOK (new open loop), PAYOFF, CALLBACK, SPONSOR. Speaker: N narrator, H on-camera
host, I interviewee/witness, A archive audio, Q a quoted historical voice read by someone else.

### Mi, Midgley/Patterson (24:57)

| time | function | speaker | content | picture (inf.) |
| --- | --- | --- | --- | --- |
| 0:00 | HOOK + STAKES | N/H | One scientist, three inventions, millions dead "including himself", lowered intelligence, two environmental disasters. 20 s, no name. | titles over archive cars/lead imagery |
| 0:25 | HUMAN + EXPL | H | Patterson, 1944, Manhattan Project, mass spectrometers; PhD plan to date the Earth; zircon calibration | portrait, lab, diagram |
| 1:40 | COMPLICATION | H | Tilton's uranium fine, Patterson's lead "all over the place", far too high | lab animation |
| 2:20 | QUESTION + REHOOK | N + Q | A lab-notebook-style line from Patterson; "where was all this extra lead coming from"; the mystery "would take over the rest of his life and bring him to the ends of the Earth" | hard cut |
| 2:35 | HUMAN | N | 1908 Detroit: Byron Carter killed by a hand-crank kickback; friend Leland swears off hand cranks; Kettering builds the self-starter | period illustration/archive (inf.) |
| 3:55 | COMPLICATION + EXPL | N/H | The new engine "knocks"; octane scale, heptane vs isooctane; on-camera piston demo at about 5:40 (98 octane does nothing when compressed) | host at bench |
| 7:00 | HUMAN | N + Q | Midgley (27) hired; tries butter, camphor, ethanol ("spitting in the Great Lakes" - his own words); ethanol works but cannot be patented | portrait, lab |
| 7:45 | COMPLICATION/PAYOFF | N/Q | Tetraethyl lead works, smells foul; 5 years in; "$200 million" line (over $3 billion today) | numbers over archive |
| 9:10 | REVERSAL | A + N | Marketing film audio; 1923 Indy 500; plant workers sicken, five die; press conference where Midgley pours TEL on his hands and inhales | archive |
| 10:30 | EXPL | H | Why lead is poison (mimics calcium, myelin, children) | animation |
| 11:35 | COMPLICATION | N | Public-health experts warn; dismissed | letters/headlines |
| 12:15 | CALLBACK | N | Back to Patterson: Caltech clean lab, tears out lead-soldered cables; meteorites dated at 4.55 billion years (0.15% from today's value) | lab shots |
| 13:30 | QUESTION | N | "How natural is the lead in our environment?" | ocean sampling animation |
| 14:20-19:30 | EXPL + PAYOFF | N/H | Ocean depth profiles, Greenland/Antarctic ice cores, bones; industry pushback; blood-lead guideline falls 60 to 3.5; crime graph offset by 20 years; IQ claim | graphs placed over archive |
| 19:30 | REHOOK | N | Second invention: the refrigerant problem, Freon; demonstration by inhaling and blowing out a candle (echo of the lead stunt); ozone hole | archive, animation |
| 21:30 | REVERSAL | N | Polio, rope-and-pulley bed, strangled in it in 1944: killed by his own invention. Closes "including himself" from the opening | still image |
| 22:00 | PAYOFF | N | Bans country by country (1986 to 2021), 1 million lives a year, $2.45 trillion; leaded aviation fuel remains | map/graphic |
| 22:50 | CALLBACK + REFLECTION | Q + H | An 18th-century line about how long a useful truth can wait; "how much harm or good a single person could do" (the opening's "one single scientist") | quiet card |
| 23:00 | SPONSOR | H | handed over by "which brings me to" | |

### Ci, Citicorp/LeMessurier (about 33 min)

| time | function | speaker | content | picture (inf.) |
| --- | --- | --- | --- | --- |
| 0:00-0:12 | HOOK | N | Name the building, "summer of 1978", the engineer's name, "terrifying discovery", fatal flaw: collapse in winds of 110 km/h | skyline, building |
| 0:15 | STAKES | N | 200,000 people nearby, hurricane season weeks away | |
| 0:40 | HUMAN | A | The engineer's own recorded voice: he was the only man who knew | archive interview |
| 0:45 | QUESTION x2 | N | Stay silent or fix and risk ruin? "How was this allowed in the first place?" Host introduced | |
| 1:00 | HUMAN | I (host/historian) | 1960s: the bank wants the block; a church on the corner will not leave; the pastor's "we are not leaving" | street, church |
| 2:20 | EXPL | H + I | Column-on-stilts idea, "let's make our job harder"; napkin sketch; chevron load paths on a physical model | model on table |
| 4:44 | EXPL | H | Wind load (push phones against each other, force build-up per chevron) | host demo |
| 7:49 | EXPL | H | Tuned mass damper: pendulum model, tighten the bolt to feel more damping | hand-built rig |
| 10:45 | REHOOK | N | "Going swimmingly for about a year, but the first hint of trouble came in May 1978" | |
| 11:30 | COMPLICATION | I | Fabricator asks how the welded braces worked out; the office replies "we bolted those" (cost saving: a quarter-million dollars) | phone, plans |
| 12:15 | HUMAN | N | Student's phone call; the teacher claimed the columns should be at the corners | |
| 14:00-18:00 | EXPL + REVERSAL | H | Quartering winds: split wind into components; numbers 454 t vs 635 t; brace tension 295 t, more than double; "this is serious" | blackboard/chevron animation |
| 18:10 | HUMAN | N/I | He flies to Canada to confirm; wind-tunnel data joint by joint; weakest joint on floor 30 | |
| 18:38 | STAKES | N | Odds: one-in-six chance of collapse that very fall | |
| 19:49 | HUMAN | I | The host asks an engineer what the moment must have felt like (empathy by proxy) | |
| 20:15 | HUMAN | A | His admitted thought of driving into a bridge abutment; then "there was a 1 in 6 chance... never any other choice" | |
| 20:50 | PAYOFF-of-decision | N | Tells architect and chairman; emergency generators for the damper; "Project Pandora" renamed "Serene" | |
| 21:28 | EXPL | N | Night welding of steel plates "like band-aids" on 200 joints | night shots |
| 22:30-23:00 | RE-STAKE + SPONSOR | N + H | Phone lines installed overnight; sponsor read about staying connected | |
| 24:45 | CALLBACK | N | "And now back to Project Serene" | |
| 25:15 | HUMAN (gag) | A | Plan to alert the press by phone; the paper is on strike (martini line) | |
| 25:40 | SUSPENSE | N | Hurricane Ella; generators on; "the most beautiful day the world has ever seen" | |
| 27:00 | PAYOFF | N | Repairs done in October; building now rated to a 1-in-1000 storm; TMDs spread to every tall building | skyline |
| 28:00 | REHOOK (after payoff) | N | "First, who was the mysterious student that started it all?" -> Diane Hartley, the BBC documentary, a NIST study, the lingering controversy | interviews |
| 32:00 | REFLECTION | I | Interviewee's closing "truly remarkable story" | |

### Mu, Kary Mullis (about 33 min)

| time | function | speaker | content |
| --- | --- | --- | --- |
| 0:00 | HOOK (demonstration) | H | Extract your own DNA with salt water, soap and alcohol; "how do you read DNA?" |
| 0:55 | STAKES + TEASE | H | "One man who took a lot of drugs and stumbled on a discovery that unlocked DNA forever. Also he was kind of a jerk." (character in one line) |
| 1:17 (ch.) | HUMAN | I | Berkeley: LSD, skipped classes, a published paper at 22 |
| 2:50 (ch.) | CONTEXT | H | Cetus, early biotech |
| 4:16 (ch.) | EXPL | H | Sickle-cell detection by gel, unzipping DNA, radioactive probes (five minutes of mechanism before Mullis acts) |
| 8:29 | COMPLICATION | H | "It worked, but it took days or weeks" |
| 9:12 (ch.) | HUMAN | I | Mullis's boring job (making probes); a new synthesiser machine gives him free time; his disliked behaviour at work |
| 10:20 | HUMAN moment | I | Friday drive, spring 1983: "read one license plate from the Moon vs make more copies of it"; stops the car; scribbles on a receipt |
| 11:30-15:00 | EXPL | H | Primer, polymerase, 3'/5' direction, doubling 2-4-8-16 |
| 15:15 | HUMAN | Q (his own memoir line) | "DNA bombs exploding in my brain"; would he have invented it without LSD? He doubts it |
| 15:30 (ch.) | COMPLICATION | I | Company seminar: colleagues walk out; "too simple to work" |
| 18:10 (ch.) | COMPLICATION | H | Polymerase dies at 95 C each cycle |
| 18:50-23:50 | REVERSAL + EXPL | Q + I | Thomas Brock's hot-spring bacteria; Taq survives; "the Holy Grail"; billion copies in hours |
| 23:53 (ch.) | PAYOFF + HUMAN | N | Cetus's Golden Goose; Mullis is fourth author, furious; Nobel |
| 27:00 (ch.) | REFLECTION | I | Quirky genius; AIDS denial years; credit disputes |
| 30:20 | REFLECTION/ THESIS | H | He was playing, not forced; opportunity plus a trained mind; then the sponsor |

### Di, Dirac (35:23) (the least human film; useful as a limit)

| time | function | speaker | content |
| --- | --- | --- | --- |
| 0:00 | HOOK | N | 1928, "a young man shuffled onto a stage", detached recitation (Wigner's description), the lecture sends famous physicists "spiraling"; Heisenberg: "saddest chapter in modern physics" |
| 0:55 | QUESTION | N | What had the young man said to disrupt quantum mechanics? A negative-energy particle |
| 1:09-8:33 | EXPL | H | Special relativity, Schrodinger, Klein-Gordon. The protagonist is unnamed for about 9 minutes |
| 8:33 (ch.) | HUMAN | I | "The strangest man in physics": three-hour dinner in which he said almost nothing; the love of mathematical beauty |
| 11:00-24:00 | EXPL | H | Linear equation, matrices, four-component wave function; two short human beats (his answer to Heisenberg on dancing; "beauty over fit") |
| 26:35 (ch.) | COMPLICATION | I | Negative energies; Heisenberg gives up |
| 27:50 | REVERSAL | N | Anderson's cloud-chamber positron, 1932 |
| 31:20 | PAYOFF | N | Antiparticles; the matter/antimatter question left open |
| 33:38 | CALLBACK | N | The 1928 listener, Wigner, becomes his friend and introduces his sister Margit; "they were antiparticles" (a personality metaphor borrowed from the physics) |

### F103, Flight 103 (about 28 min)

| time | function | speaker | content |
| --- | --- | --- | --- |
| 0:00 | HOOK (future tense) | N | "In a few seconds a bomb will explode here" ... everyone aboard will die, thousands will comb the area, "one of the largest crime scenes in history", unresolved 40 years later |
| 0:35 | STAKES + TITLE | N | The story of one of the deadliest crashes; archive voices say it never went away; channel sting "Fern." |
| 0:45-2:15 | SPONSOR | founder | founder voice, brand story, SIM-card plan |
| 2:15 | HUMAN | I + N | Witness Shona rings a friend's doorbell with Christmas presents; house shakes; she steps outside and sees a passport and a woman's body |
| 3:50 | CONTEXT | N + A | TV news of the crash, 259 aboard + 11 residents dead |
| 5:15 | EXPL | N | Search, a metal baggage-container rail, residue; "someone brought down Flight 103" |
| 6:50-8:15 | EXPL | N | Forensics: blast in forward hold, one container, a Toshiba radio bomb found in Germany two months earlier |
| 8:15-11:00 | RECONSTRUCTION | N (present tense) | Heathrow, Frankfurt, baggage transfer, take-off, cruise; "exactly 50 seconds after 7:02 the timer hits zero" |
| 11:00-14:30 | EXPL | N + expert channel | Shock waves, fuselage breaking, nose detaching, fall to the ground (the "how"), then "270 people die that day" |
| 14:30 | COMPLICATION | A + N | Public was not warned beforehand (Vice-President's reasoning); four groups claim responsibility |
| 15:50 | HUMAN | N | Malta shopkeeper Tony Gauci sells clothes to "a very strange customer": scene, no invented dialogue |
| 17:10 | PAYOFF-step | N | Circuit-board fragment, timer maker, Libya |
| 19:15-22:00 | PROGRESS | N | Switzerland timer firm, identification, charges |
| 22:44-24:00 | REVERSAL | N | Trial in the Netherlands under Scottish law; a victim's father (Jim Swire) does not accept the verdict |
| 24:07-26:00 | COMPLICATION | N | Witness less certain than the court was told; reward claim; retraction |
| 26:00-28:00 | EPILOGUE | N + A | Release, return as a hero, new charges in 2020 and 2026; the case is still open. The opening's "unresolved" is the last word |

### Co, Coca-Cola Freestyle (16:45)

| time | function | speaker | content |
| --- | --- | --- | --- |
| 0:00 | HOOK | N ("you") | You in a cinema holding a cup; the red-chrome machine; "it's not just serving you a drink, it tracks everything" |
| 0:30 | STAKES + QUESTION | N | Coke "invested more than $1 billion"; "how a drink dispenser became a global lab and what role you play" |
| 0:45 | CONTEXT | N | The soda-fountain history in two sentences each; 2006 sales fall |
| 2:30 | HUMAN (the "you") | N | You at the touchscreen: bubbles, Sprite Cherry; the product walked as a user |
| 5:15 | EXPL | N | Every machine reports to Coca-Cola's backend; user mixes become products |
| 7:00 | EXPL | N | Cartridge supply chain predicted from data |
| 8:20 | DIGRESSION | N | Data-theft warning with sponsor (identity protection), "back to Coke's genius machine" |
| 9:30 | REHOOK | N | Marketing "nudging"; facial-recognition capability in the spec sheet; company does not reply |
| 12:50 | EXPL | N | "We could not find real numbers; so our analyst estimated" (2% margin assumption) |
| 15:30 | REVERSAL | N | Two of four Freestyle-born flavours failed |
| 16:15 | PAYOFF | N | The billion has "long been made back" - answers the opening number |

### SS, Secret Service (27:12)

| time | function | speaker | content |
| --- | --- | --- | --- |
| 0:00 | HOOK (frame) | N | "A shooter is taking aim at the president"; five Secret Service branches spring into action; stakes both ways; three questions |
| 0:55 | CONTEXT | N | "Zero Fail"-style book sources; JFK in Fort Worth, 1963, hated by his protectors |
| 3:58 | HUMAN | N | Dallas; Clint Hill (assigned to Jackie) is the first to recognise the sound; he runs for the limousine |
| 5:25 | EXPL | N | Threats multiply, agency rebuilds; sponsor at about 6:00 |
| 7:15 | EXPL | N | Advance work, "jackal" assassins, counter-assault team, the Beast |
| 11:40 | CUT-BACK | N | "A split second from now it'll be time to show their stuff. Just like in 1981" |
| 12:45-15:15 | HUMAN | N + A | Hinckley's obsession; agent McCarthy throws himself in the line; Devastator bullets; 4.5 m |
| 15:20 | EXPL | N | Threat-assessment classes, the ink library, profilers |
| 17:10 | FRAME RETURNS | N | "The first bullet narrowly misses the president." Frame beats arrive about every 4-6 min |
| 18:50 | EXPL | N | 9/11 and the shift to aerial threats |
| 21:45 | FRAME | N | Drone, Beast, "Hammer" medical team |
| 23:35 | PAYOFF | N | The hypothetical is declared "an unlikely scenario, one of many they prepare for" |
| 24:30 | COMPLICATION | N | Agency scandals; the rooftop failure at the Trump rally |
| 26:30 | REFLECTION | N | "All the times history almost changed, then didn't" |

### Cn, lost communist console (about 18 min)

| time | function | speaker | content |
| --- | --- | --- | --- |
| 0:00 | HOOK | N | Rarest console on the planet, about 1000 made, in a country that no longer exists; four questions in a row; "This is the hunt for the lost communist console." |
| 0:50 | BRAND | founder | "Fern." plus narrator hand-over |
| 1:40 | QUEST | N + crew | We search online, buy one for about 900 euros |
| 2:35 | HUMAN/OBJECT | I | Collector inspects it: weight, controller stamp "710", colours |
| 3:30-8:20 | CONTEXT | N + A | West's console boom (Odyssey, Atari, Pac-Man ad audio), East German isolation, sponsor at about 7:00 |
| 9:00 | OBJECT/EXPL | N + crew | Play-test; a copy of Western Pong, play until 15 points "or you get bored" |
| 10:00 | HUMAN | N | Party official Nelle, strict electrical engineer who fires the underperformers (first person with a will, at 55% in) |
| 11:00 | COMPLICATION | N | Export controls (COCOM) block the main chip |
| 13:30 | REVERSAL | N | Cancelled; the factory goes on to radio alarm clocks |
| 14:20 | CALLBACK | N | Party doc says games help raise children in socialist values; "one year later, the Wall came down" |
| 15:20 | RE-FRAME | N | Today China uses games as soft power - the film's argument is that the unwanted console is a "power tool" that failed |

### KK, Scott Payne (about 47 min; interview format)

First 3 min: one second of the criminals' threat (audio, fragment), a dated scene card ("April 21, 2017, a field in Alabama") told in present tense, the narrator lists his cover roles, then the subject's own account takes over. About a third of the film is the subject speaking in the first person (segments median about 95 words, max about 500). The narrator takes over only to set context, dates and names.

## 3 Craft findings

### 3.1 Openings (first 30-60 s)

Line by line, five patterns:

1. **Stakes before names (fern):** F103 (cold open, 0:00-0:35): future-tense promise of a bomb ("in a few seconds, a bomb will
   explode here"), the death toll in two sentences, "this is no accident", "nearly 40 years later it remains unresolved",
   then the title sentence. SS: "a shooter is taking aim", success versus failure in two parallel sentences, then
   three "who / how / how" questions. Cn: object-rarity facts, four questions, title as a sentence. Co: "you" in a
   cinema holding a cup, a glowing machine, "it tracks everything you do", the $1 billion number, then the thesis.
   Every fern opening ends with the title spoken as a sentence and the brand sting.
2. **Protagonist with a problem in 12 seconds (Veritasium Ci):** building named, "summer of 1978", engineer named,
   "terrifying discovery", flaw, threshold ("winds of just 110 km/h"), 200,000 people, hurricane season weeks away,
   his own recorded voice at 0:40, the binary choice at 0:45, the host's task at 0:50. About 15 factual claims in 50 s,
   none of them mechanism.
3. **Thesis summary without a name (Mi):** 20 seconds claiming three inventions, millions of deaths "including
   himself" and two environmental disasters; then straight to a different man (Patterson) with a puzzle. The title
   character (Midgley) is named only at about 7:00 (28% in); the hook is carried by a mystery, not by him.
4. **Demonstration then person-tease (Mu):** 55 s of "do this at home" extraction of DNA, a how-do-you-read-it
   question, then "one man who took a lot of drugs... also he was kind of a jerk". Character and joke in one line; the
   name comes at 1:18.
5. **Scene in a lecture hall, name withheld (Di):** a young man on a stage in 1928; the audience reaction is the hook.
   He remains "the young man" for about nine minutes. Stakes are given by other people's reactions (Heisenberg
   "saddest chapter", Pauli giving up physics), not by an assertion of importance.

Numbers: a named person or a first-person "you" is present by 0:12 (Ci), 0:25 (Mi: Patterson at 0:30), 0:55 (Mu), 1:10
(Di: Wigner at 0:10), 0:00 ("you", Co), 0:55 (SS: JFK). The first human *scene* with a person acting arrives at
0:25-2:30 in Veritasium, 2:15 (after the sponsor read) in F103, 3:58 in SS, about 10:00 in Cn. All hooks promise a
question; none states the answer in the first minute. Sponsor reads sit after the hook in the fern films (0:45-2:15 in
F103, about 1:00 in Cn, about 6:00 in SS) and at the end or at a lull in Veritasium (Mi/Mu at the end; Ci at the
cliffhanger around 23:00; Di in the dull theory stretch about 7:00).

### 3.2 How human story and science interleave

- **Proportion (from chapter titles and my beat maps):** Ci about 45% science/55% person-and-decision; Mu about
  45% person / 55% mechanism if the five-minute sickle-cell detour and the primer/polymerase explanation count as
  science; Mi about 40% person / 60% science; Di about 10% person / 90% mathematics. Fern: SS about 35% person-based scenes
  (Dallas, Reagan, the hypothetical frame) and 65% mechanism of the service; F103 about 40% person (witness, shopkeeper,
  family, trial) and 60% investigation process.
- **How often the camera returns to the person:** Ci: person beat roughly every 3-5 minutes with a person-driven
  turn every time the science would otherwise run past 5-7 minutes (1:00 church, 11:17 student, 18:38 odds, 20:15 dark
  thought, 25:15 press gag). Mi: ping-pong between Patterson and Midgley with a hand-off on every chapter boundary
  (2:35, 12:15) so the science always has someone's question behind it. SS: frame returns every 4-6 minutes at
  explicit cut-back lines. Di (exception): the longest unbroken theory run is about 13 minutes (11:00-24:00) with
  only two one-sentence people beats; its retention depends on a bigger stage (a live physicist interviewee in
  the room) and the mystery of the negative energy.
- **Each science step is motivated by a person's problem.** Mi: Patterson's wrong lead readings make zircon dating
  necessary (1:40); the loud Cadillac Model 30 makes octane necessary (3:55); the smell makes Midgley try the next
  additive; workers' deaths make the toxicology section necessary (10:30); Patterson's clean-lab obsession makes the
  ocean and ice-core studies necessary (13:30). Mu: boring probe-making and free time lead to the PCR idea; the
  polymerase dying at 95 C leads to the hot-spring bacteria. Ci: the church creates the stilts, the stilts the load path,
  the swaying the damper, the bolted joints the quartering-wind check. The mechanism is never delivered before the
  person's need for it has been shown.
- **A person who is wrong or hurt does the pivot.** Midgley's lead and Freon both turn on stunts of denial (hands in lead,
  inhaled gas); LeMessurier's flaw and secret repair; Mullis's rejection by colleagues; Dirac's equation that "wrongly"
  predicts negative energy. The reversal is a human act, then the science is called in to explain what the act
  revealed.
- **Re-framing of the same person:** Patterson appears at 0:25, disappears for 10 minutes, returns at 12:15
  and 14:20, and his result closes the film. Midgley's death by his own bed (21:30) is staged as irony 21 minutes after
  the hook promised "including himself".

### 3.3 Dialogue and voices (how historical people speak)

None of the six non-interview films puts invented dialogue in a real mouth. The methods, in order of frequency:

1. **Narrator paraphrase of a documented event, present or past tense, no quotation marks** (F103 shopkeeper scene, SS Dallas,
   SS Hinckley, Cn Nelle). Intent and thought are stated as fact only when documented ("Hill was the first to recognise the
   sound"). Where unknown, the film asks ("could there have been a lapse?") or says "it's likely".
2. **First-person archive or interview audio of the real person or a witness** (Ci: LeMessurier's own recorded voice and
   his bridge-abutment thought; F103: witness Shona and a victim's relative; KK: the subject for a third of the film).
   Segment length in KK median about 95 words (about 35 s); in F103 median about 29 words (about 11 s), max about 205.
3. **Written quote read by narrator with attribution** ("he later wrote", "Heisenberg wrote to Bohr", "Midgley wrote",
   a letter, a notebook, a memoir) (Mi about 5 in 25 min, Di about 6 in 35 min, Mu memoir line). Length 8-25 words.
4. **Reported speech told by a named expert or participant** (Ci: pastor and the office-phone exchange are told by the
   host's interviewee; Mu: colleagues' reactions are told in the interviewees' own casual voice: "he's like...").
   The dialogue is sourced because the person telling it is the source and is identified.
5. **Archive speech of the period** (Reagan, Bush, promotional films): used for credibility, 5-15 s.

Frequency and length: Ci 12 quoted spans in 33 min (about one per 3 min), median 13 words; Di 9 spans in 35 min,
median 9 words; Mi about one every 4-5 min; SS 3 in 27 min; F103 0 in 28 min (witness audio instead). So "a character
speaks" is rare: about 0.2-0.4 times a minute, short, and always source-labelled in the script or on screen.

Inner thought is used only when the person recorded it: LeMessurier's bridge thought is a verbatim interview line;
Mullis's "DNA bombs exploding in my brain" is memoir; Hill's reaction is described through action. There is no
imagined internal monologue in any film. Our own dramatised lines are therefore a departure from both channels.
Where fern needs emotion without a recording it uses a witness or a camera-style detail ("her hair was not out of
place", "all she sees is devastation").

### 3.4 The narrator's voice

- **fern:** third person, present tense for every scene ("A man walks into the shop. He buys everything Gauci shows him."),
  past tense for background; second person only for the "you" device in Co and in framing questions. Short, flat, concrete
  verbs; the dry jokes are single lines ("blessed with a much smoother voice than mine", "to drown out your Jared Leto
  induced sorrow", "Is that gun made of white plastic?"). Running device: "we asked, they did not respond" in Co (three
  times, giving honesty and a dry laugh), SS's "Zero fail". The channel uses its own brand sting after the hook.
- **Veritasium:** "I" in first-person singular for the host's reactions, "we" for the team, "you" for the viewer's likely
  guess. Longer sentences than fern (14-15 words mean, 8-14% over 25 words) but each held to one clause chain; the
  numbers come with comparisons. The host sets small tests ("I'm going to take a little 98-octane fuel and put it in this
  piston"); the guest or co-host supplies colour and gossip in casual speech.
- **Rhetorical devices counted:** turn words 0.8-1.7/min; "so" as a consequence opener 0.3-1.9/min; the "why" question
  once per 3-5 minutes; "which means" about 0.0-0.14/min (consequence is stated by juxtaposition rather than by the
  phrase); "turns out/surprisingly/strange/mystery/problem" 0.12-0.5/min. Callbacks to the hook: Mi (single scientist /
  "including himself"), Di (the 1928 audience), Co (the $1 billion), F103 (unresolved).
- **Addressing the viewer:** fern asks "who are the people... how do they..." as a list of three; Veritasium asks the
  viewer to predict ("what do you think this moment was like for him?" asked of a guest). Direct instructions to the
  viewer are rare except for the sponsor.

### 3.5 Re-hooks and chapter transitions

- **Rate:** Ci has seven big re-hooks in 33 min (0:45, 10:45, 14:00, 18:38, 20:15, 25:40, 28:00), about one per 4.7
  minutes, plus 1.8 turn words a minute. Mi: 2:20, 3:55, 7:45, 9:10, 12:15, 19:30, 21:30 (7 in 25 min). Mu: 0:55, 8:29,
  15:30, 18:10, 23:53 (5 in 33 min). SS: the frame cut-back lines at 11:40, 17:10, 21:45 (every 4-6 min).
- **Lines that close a section:** a promise ("the mystery would take over the rest of his life"); a negative turn ("it worked,
  but there was a problem"); a consequence ("and then workers started dying"); a split-second countdown ("a split second
  from now it will be time to show their stuff"); a hand-back from a sponsor ("and now back to Project Serene").
- **A re-hook after the payoff:** Ci opens a whole new investigation (who was the student?) after the repair is
  done, and Mi launches the second invention (Freon) after "lead" is resolved. This keeps the film alive past the
  natural end; the new question is shorter than the first.
- **Chapter titles are questions or events**, not topics: "Why is the Citicorp building on stilts?", "What were the odds of
  collapse?", "Hurricane Ella", "The Anonymous Student". This is a useful template for our section headers.

### 3.6 Explaining a mechanism

- **Order:** (1) the person fails or wants something, (2) the quantity that matters is named once with a number, (3) a
  physical analogue the viewer can hold (pushing two phones against each other for wind; license plate from the Moon
  for PCR; "like a clock" for decay; stilts at the midpoint of a chair's sides), (4) the rule, (5) the consequence for
  the story ("so the 30th floor joints were the weak ones").
- **Concept density:** Ci introduces about 12 distinct engineering ideas in 33 min (about 0.4 a minute: stilts, chevron,
  wind load, damper, quartering winds, bolt vs weld, wind-tunnel dynamic, tension, odds, retrofit, TMD spread, NIST
  reanalysis) with 4-7 minutes of explanation per idea. Mi explains 6 in 25 min (decay chain, octane, lead
  toxicity, ice cores, blood lead, CFC). Mu about 8 in 33 min. Di piles up about 10 in 35 min and is the slowest to
  re-engage. fern explains one mechanism at the surface level (how Freestyle bubbles map to cartridges; the forensic
  chain) and keeps the quantity of new terms low.
- **Numbers made concrete:** comparisons to a known year or money value ("$200 million... over $3 billion in today's
  dollars"), a probability stated as an odds-with-a-date ("1 in 6 chance that very fall"), a clear delta ("brace
  tension more than double"), a threshold the viewer knows ("110 km/h"), a ratio that surprises ("0.15% from today's
  accepted value"), a time ("exactly 50 seconds after 7:02"). A statistic is never alone for more than one sentence
  before it is tied to a person or a place.
- **Demonstrations stand where analogies are expected:** Veritasium's octane piston, pendulum rig, and phone-pushing
  demo; fern replaces demos with reconstruction (present-tense flight-path account of the bomb) and the crew's own
  hands-on test (play-testing the console).

### 3.7 Endings

- **Payoff then reflection, then a tie back to the hook:** Mi ends the death of the man with the bed, bans
  and savings, a period quote, then "a single person" (the opening's "one single scientist"). Di ends on the 1928
  audience member and the marriage, using the physics metaphor (antiparticles) to describe the couple. Co closes the money
  question from the top ("billion made back"). SS ends with "the times history almost changed and then did not" - a
  reflection of the opening stakes. F103 ends with "still unresolved" (opening line) plus current news. Ci ends on a
  guest's amazed summary after a re-hook.
- **What does not happen:** none of the ending sections introduces a new mechanism; they are 60-120 s long; the last
  1-2 sentences are short.
- **Two flavours:** a closure ending (Mi, Ci, Co) and an open-case ending (F103, SS). For the open-case ones, the last
  beat is a statement about what remains unknown.

### 3.8 What a scene contains visually (inferred from the words)

- **Place and time cards:** "April 21, 2017, a field in Alabama", "Fort Worth, Texas, 1963", "summer of 1978", "late
  afternoon, an aircraft is parked on a stand southeast of Terminal 3", "December 3rd, 1921". Almost every human scene
  starts with a place or a date and then a *physical* detail (the stamp number 710 on the controller, the weight 1.5 kg,
  the colour of the buttons, the napkin sketch, the receipt the idea was written on, the welders ripping off sheetrock at
  night). These are the "objects with history" that make the world lived-in; they also double as proof.
- **People in a place doing a task:** welders, baggage handlers, shopkeeper with the clothes, host with a pendulum model,
  collector unboxing the console. Not portrait-and-label: the person is in the act.
- **The explainer is staged in the real space:** Henry stands in the Citicorp lobby and at a physical model; the
  console film unboxes and plays. The mechanism animations (wind load arrows, crank-and-piston, polymerase cycle) appear
  after the physical object has been seen.
- **Archive as evidence of the named thing:** promotional film audio for Ethyl, Odyssey/Atari advert audio, the TV news of
  the crash, the Vice-President on air, the BBC documentary on Citicorp. Always named in the line next to it.
- **Quote cards (inf.):** period lines (Franklin, Heisenberg letter) are read over a calm card or portrait; one per ~5 min.

## 4 What this means for a Semmelweis film (carry-over, not a research finding)

- The nearest reference is Ci: a single person with a documented problem and a clock, a decision with a cost, and a
  later "who really did this" re-hook. Mi shows how to run a second thread (the person who later proves it) alongside
  the first. Neither uses invented lines.
- Documented words we may dramatise: his letters and open letters, clinic registers, a recorded diary-style reaction
  of colleagues (if sourced). Everything else, the film should narrate in paraphrase or in the host's voice.
- Where the protagonist must "think", write it as the narrator naming a documented concern, or as a quote with a source.

## 5 Rules for our script skill (testable; tag = films that support the rule)

Hook and opening
1. A question or stake sentence appears in the first 30 s; the answer is not given in the first 60 s. [Mi, Ci, Mu, Di, F103, Co, SS, Cn]
2. A named person (or a "you" protagonist) appears in the first 12-30 s, or the opening is a scene of a person with the name withheld for no more than the length of the hook and a cut. [Ci, Mi, Di, Mu, Co]
3. The title is said as a sentence by minute 1 (fern: "This is the hunt for..." / "This is the story of..."). [F103, Cn]
4. Stakes use two numbers or dates max in the hook, one human-sized (people, hours, years) and one threshold. [Ci, F103, Co]
5. The hook uses 3-5 short declarative sentences; the first sentence is concrete and sensory, not an abstraction. [F103, SS, Co, Mu, Di]
6. The first scene in which the protagonist acts (not only named) is within the first 3 min of the main body (after the sponsor/brand spot). Exception allowed only with a mystery protagonist and a stated reason. [Mi (0:25), Ci (1:00), Mu (1:17), F103 (2:15), SS (3:58)]
7. Delaying the title character beyond 25% of the film requires a parallel person with a puzzle on screen the whole time. [Mi, Di]

Story and science interleaving
8. No stretch of pure explanation longer than 5 min without a person beat (action, reaction, decision, or quoted line). Hard fail at 7 min. [Ci, Mi, Mu; Di is the counter-example]
9. Every explanation block opens with the person's problem, in one sentence, before the first technical term. [Mi, Ci, Mu]
10. A person's decision or failure triggers each major science step; list the "because of X he needed Y" link per step in the planner and fail if it is missing. [Mi, Ci, Mu]
11. Person beats return at least every 3-5 minutes; target ratio 40-55% person/story, 45-60% mechanism. Under 25% person is a fail. [Ci, Mi, Mu, SS, F103]
12. A second thread (a rival, a later checker, a victim, a witness) cuts in at least twice and returns at the end. [Mi, Ci, F103]
13. One decision per film is shown with its cost (what the person risks: money, name, safety). [Ci, Mu, Mi]
14. A re-hook after the main payoff opens a smaller second question and answers it in 3-6 min or hands it to the closing reflection. [Ci, Mi, Di]

Rhythm and language
15. Spoken pace 150-175 words/min; median sentence 10-14 words; <= 6-word sentences 15-25% of all; 25+ word sentences <= 10%. [all]
16. A turn word (but, however, until, suddenly, yet) at least every 60-75 s; at least one explicit problem sentence every 2-3 min. [Mi, Ci, Mu, Di, Co]
17. Explicit questions 0.35-0.85 a minute, none in two consecutive sentences, and one at every chapter pivot. [Ci, Di, SS, Cn]
18. No more than 4 explicit analogy markers a minute; every analogy is a physical thing in the viewer's hand (phones, chair, license plate, band-aid), appears once, and is paid back by the rule within 20 s. [Ci, Mu]
19. Narrator tense: present for scenes, past for background; third person for the story, first person plural for the team's own checks, "you" only to put the viewer in the person's shoes or to ask for a guess. [F103, SS, Co, Ci]
20. Comedy: 1 dry one-line joke per 3-5 min, aimed at an institution or a habit, never at a victim. [Co, Cn, SS, Mu]
21. A running device (the "no reply" line, "Zero fail", "antiparticles" metaphor) appears 2-4 times with a changing meaning. [Co, SS, Di]

Voices and quotations
22. No invented speech for a real person. Every quoted line carries a source tag in the script data (letter, memoir, testimony, court record, interview) and the narration names the source in the same or the next sentence. [Ci, Mi, Di, F103, SS]
23. Quoted lines are 8-25 words; at most one per 3 minutes on average (0.2-0.4 a minute); a quote is never followed immediately by another. [Ci, Di, Mi]
24. Dialogue exchanges are told as reported speech by a named teller (the narrator citing a memoir, a host citing an interview), not as a performed scene. [Ci, Mu]
25. An inner thought is allowed only if documented; otherwise rewrite as the narrator's inference with a hedge ("he must have known..."), or as an action. [Ci, Mu, Mi]
26. Emotion without a recording comes from a concrete detail of the body or the scene, not from a feeling word. [F103, SS]
27. Witness or archive voice, when we have it, is 10-35 s long, first person, and is cut in at a moment of consequence, then the narrator resumes within a sentence. [F103, Ci, KK]
28. Ask a character-aware proxy (a guest, an on-screen colleague) what the moment must have felt like, rather than narrating the feeling. [Ci]

Re-hooks, transitions
29. A section ends on a line that is one of: a promise, a negative turn, a consequence, a countdown, or a return handle (frame story). Never on a summary. [Mi, Ci, SS, Mu]
30. Big re-hooks about every 4-5 min, small turns every minute; the last 3 minutes before the ending contain at least one more. [Ci, Mi, Mu]
31. Chapter titles are a question or an event, not a subject. [Ci, Mu, Mi]
32. If a frame story is used, it cuts in every 4-6 min with a one-line handle ("a split second from now...") and is explicitly closed. [SS]

Mechanism
33. Introduce at most one new technical concept per 2.5 minutes of film; a defined term is used again within 60 s. [Ci, Mi, Mu]
34. Every number is paired with a comparison, a date, or an odds statement within the same sentence; no more than two numbers in a row (cross-check with `qc_script.py`). [Ci, Mi, F103]
35. A physical demonstration or reconstruction stands where an analogy would otherwise be spoken. [Ci, Mi, Mu, F103]
36. Mechanism is first shown on the real object or place, then animated. [Ci, Cn]

Endings
37. The ending has four moves in this order: payoff (answer to the hook), consequence (what changed or did not), reflection (one sentence), callback (an object, phrase or place from the opening). 60-120 s in total. [Mi, Di, Co, SS, F103]
38. No new mechanism after the payoff; the last two sentences are 12 words or fewer. [Mi, Co, SS]
39. Open-case ending names the unknown in one sentence instead of closing it. [F103, SS]

Visual specificity for each scene
40. Every human scene starts with a place and time card and one physical detail with a number or a name on it (stamp, weight, receipt, napkin, brace tension). [F103, SS, Ci, Cn, KK]
41. A person is always doing something in a place (task, tool), not standing beside a label. [Ci, F103, Cn]
42. Archive is named in the line next to it; a period or promotional voice is used for 5-15 s once or twice a film. [Mi, Ci, Cn, SS]

## 6 Known weak points of this study

- The pictures were not viewed; section 3.8 is inferred from captions. A visual follow-up (frame sampling of the same six films) would
  confirm what the narrator-on-camera is doing during mechanism passages.
- Several times for the fern films and the sponsor reads are estimates.
- The rules are derived from nine films, of which two (Di, Co) deliberately depart from the human-first model; they are tagged
  accordingly so the planner can treat them as counter-examples rather than targets.
