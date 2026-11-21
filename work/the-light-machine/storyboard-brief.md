You plan the 3D pictures of a narrated explainer video.

Return ONE JSON object: {"beats": {"<beat name>": {...}, ...}}, one entry for every beat below and no other.
Each beat entry:
  "scene":   a scene name from the catalog
  "params":  optional, only parameters that scene declares
  "shots":   optional [{"view": "<view of that scene>" or "at:<anchor>", "start": seconds}]; leave out for the default (a cut every 4-5 s)
  "labels":  up to 4 [{"text": "<=32 chars", "anchor": "<anchor of that scene>", "at": fraction of the beat (0-1), or "word:<a word the narrator says>"}]
  "actions": optional [{"name": "<action of that scene>", "at": fraction or "word:<w>"}]
  "hud":     optional [{"text", "screen": [u, v], "at"}] for text fixed to the screen
  "counter": optional {"template": "${:,} billion", "from", "to", "screen": [u, v], "curve": "exp", "color": "warm"}
Rules: pick the scene whose picture the sentence is about, not a decorative one; tag only things the narrator names;
tie a label to the word it explains with "word:"; vary scenes between neighbouring beats; never invent a number
the narration does not say. Use only names that appear in the catalog.

SCENE CATALOG
- bar-chart: Columns rising left to right; the last one is the point of the sentence.
    params: values: number[] (default []) column values; empty = a doubling curve
    views: wide, last
    anchors: first, last
    actions: grow
- campus: A low headquarters building among trees, seen from the air.
    params: (this scene takes none: leave out "params")
    views: wide, low
    anchors: building
    actions: (this scene has none: leave out "actions")
- chip-teardown: A chip package that opens: quad flat pack, ball grid array, or a stacked AI package.
    params: package: enum in ['qfp', 'bga', 'ai'] (default "qfp") qfp = pin-lined chip; bga = chip on balls; ai = logic die with stacked memory; text: string (default "") marking printed on the lid; seed: int (default 4) random seed of the wire bonding
    views: wide, die, pins, balls, memory, logic
    anchors: balls, die, interposer, lid, logic, memory, package, pins
    actions: open
- cores-compare: Two processors side by side: a few big cores taking turns, many small ones at once.
    params: (this scene takes none: leave out "params")
    views: wide, few, many
    anchors: few, many
    actions: (this scene has none: leave out "actions")
- document: One sheet of paper with a short title and a line that gets marked.
    params: lines: int (default 12) text lines; mark: int (default 6) line that gets marked; title: string (default "") title above the text
    views: wide, mark
    anchors: mark, title
    actions: mark
- flow-diagram: Boxes in a row joined by traces carrying light: how one stage feeds the next.
    params: nodes: string[] (default ["Input", "Process", "Output"]) box names left to right; anchors are node1..nodeN
    views: wide, first, last
    anchors: node1, node2, node3, node4, node5, node6
    actions: run
- graphics-card: A graphics card whose cooler lifts off to show the processor underneath.
    params: text: string (default "GPU") marking on the processor
    views: wide, gpu, connector
    anchors: connector, cooler, gpu
    actions: open
- layer-stack: Named slabs dropping onto each other, bottom first; one can be the highlighted layer.
    params: layers: string[] (default ["Hardware", "Platform", "Applications"]) slab names, bottom first; anchors are layer1..layerN; highlight: string (default "Hardware") the slab that glows; base: enum in ['chip', 'none'] (default "chip") what the stack sits on
    views: wide, top
    anchors: base, layer1, layer2, layer3, layer4, layer5
    actions: stack
- line-chart: A line drawn across a dark board, optionally over a row of bars.
    params: points: number[] (default [9, 8.4, 8.7, 7.2, 7.5, 6.0, 6.3, 4.8, 5.1, 3.6, 3.9, 2.6]) line values (max 24); bars: number[] (default []) optional bars under the line; adds the `bars` anchor
    views: wide, end
    anchors: bars, line_end, line_start
    actions: draw
- meeting-table: A diner booth with people around a table and an idea sketched on a napkin.
    params: count: int (default 3) people at the table
    views: wide, table
    anchors: table
    actions: idea
- neural-network: A feed-forward network; signals sweep through it layer by layer.
    params: layers: int[] (default [4, 6, 6, 6, 3]) neurons per layer
    views: wide, input, output
    anchors: hidden, input, output
    actions: (this scene has none: leave out "actions")
- org-radial: One figure at the centre, everyone else in rings around it, each linked straight in.
    params: rings: int[] (default [16, 26, 18]) people per ring
    views: wide, centre
    anchors: centre, links, ring
    actions: spread
- pages: Front pages drifting past in the dark: attention, with nothing legible to quote.
    params: count: int (default 7) front pages drifting past
    views: wide, close
    anchors: front
    actions: (this scene has none: leave out "actions")
- people-row: One to six figures standing on a plinth: founders, a team, rivals.
    params: count: int (default 3) figures, 1-6; anchors are person1..personN; lead: int (default 2) index of the highlighted figure
    views: wide, lead
    anchors: person1, person2, person3, person4, person5, person6
    actions: (this scene has none: leave out "actions")
- presenter-screen: A figure on a stage in front of a screen with a rising chart behind them.
    params: values: number[] (default [1, 1.3, 1.1, 2, 3.4, 6.2, 13, 27.5]) chart behind the presenter
    views: wide, presenter, screen
    anchors: peak, presenter
    actions: grow
- scale-compare: One block beside many: how much more, counted out in cubes.
    params: many: int (default 100) cubes in the large group
    views: wide, many
    anchors: many, one
    actions: fill
- server-racks: A row of server racks; one drawer slides out to show what is inside.
    params: count: int (default 3) racks in the row; pull: int (default 1) index of the rack whose drawer slides out
    views: wide, drawer
    anchors: drawer, racks
    actions: open
- statement: A field of posts moving like a slow wave: the backdrop for a line that carries no object.
    params: mood: enum in ['cool', 'warm'] (default "cool") colour of the field
    views: wide, low
    anchors: centre
    actions: (this scene has none: leave out "actions")
- timeline: Years along a rail; each marker lights as the story reaches it.
    params: events: string[] (default ["1993", "1999", "2006", "2012", "2024"]) marker names; anchors are event1..eventN
    views: wide, start, end
    anchors: event1, event2, event3, event4, event5, event6, event7, event8
    actions: run
- wafer: A silicon wafer on its chuck; one die lifts out of the grid.
    params: (this scene takes none: leave out "params")
    views: wide, die
    anchors: die, wafer
    actions: lift

BEATS (name, seconds on screen, narration)
- beat-01 (15 s): Fifty thousand times a second, a machine fires a laser at a falling drop of molten tin, and your phone depends on it. It sounds like a stunt, or a bad joke told by a physicist, but it is hard to find a manufacturing process that matters more.
- beat-02 (19 s): Inside every modern chip are enormous numbers of tiny switches, and each one has to be drawn with extraordinary precision. The drawing is done with light, and light has a problem: it is a blunt pencil. For decades the whole industry has been fighting that single fact, by making the pencil sharper again and again.
- beat-03 (21 s): This is the story of the latest, strangest sharpening, and of the one machine that makes it possible. Here is the strange thing about it: you will almost certainly never see this machine, and most people could not name the company that builds it. It is called extreme ultraviolet lithography, usually shortened to EUV, and it took decades to get working.
- beat-04 (19 s): To see why anyone would go to such lengths, we first need to see how a chip is actually drawn. A chip starts as a polished disc of silicon, coated with a thin layer of a material that reacts to light. A pattern is then shone onto that coating through a stencil called a mask, and the pattern is shrunk by optics on its way down.
- beat-05 (22 s): Where the light lands, the coating changes, and the chip maker can etch the shape into the silicon beneath. Then the disc is coated again, and the whole process repeats, layer after layer, until the wiring of a processor is built up like a city. The size of the smallest line you can draw depends on the wavelength of the light, the distance between one wave crest and the next.
- beat-06 (17 s): Long waves smear detail the way a thick marker smears a signature, so to draw finer lines, engineers kept moving to shorter waves. The answer this machine uses is a very short wavelength, thirteen and a half nanometres, which is the extreme ultraviolet of the name.
- beat-07 (16 s): That one decision, to move to such a short wavelength, turned a hard problem into one that looked almost impossible. A shorter wavelength means a finer pencil, which is the entire promise of this technology, and the rest of this film is the price of keeping it.
- beat-08 (18 s): The idea is older than most people expect. The EUV story begins in the middle of the nineteen-eighties in Japan, in a small research effort that most of the industry did not take seriously. Nobody could be sure the physics would ever become a factory tool, and for years it stayed a laboratory curiosity.
- beat-09 (17 s): American chipmakers pooled their effort in a group called the EUV LLC, while in Europe the Dutch company ASML joined with the German optics maker Zeiss in a consortium called EUCLIDES. It is worth pausing on how unusual this was, because it was not one company's invention.
- beat-10 (16 s): Researchers in Japan began it, American chipmakers pooled their effort, and a European consortium linked ASML with Zeiss. Then, in two thousand and one, ASML assigned a small group of people and modest resources to build a prototype EUV system.
- beat-11 (17 s): The first prototypes shipped in two thousand and six, and they were still a long way from making real chips. So in two thousand and twelve, Intel, Samsung and TSMC agreed to contribute to ASML's research and development, because they needed the machine to exist.
- beat-12 (21 s): Rivals sharing the cost of one machine tells you how badly they needed it, and how little any of them could do alone. In two thousand and thirteen, ASML shipped its first EUV production system, nearly three decades after the first idea. Now we can open the machine, and the first thing to understand is that nature offers no easy source of this light.
- beat-13 (17 s): It is not made by any ordinary lamp, so the machine has to create it from scratch, with a controlled explosion. The fuel is tin. The machine ejects molten tin droplets, each about twenty-five micrometres wide, at about seventy metres per second through a vacuum chamber.
- beat-14 (18 s): Each droplet is a target narrower than a human hair, and it has to be hit exactly right. The machine drops fifty thousand of these droplets every second. A carbon dioxide laser hits each one, and the laser fires a dual pulse, a weaker pre-pulse first and a stronger main pulse after it.
- beat-15 (15 s): The result is a hot plasma, and as it blazes, it gives off the extreme ultraviolet light the whole machine exists to collect. The timing has to be perfect, fifty thousand times a second, with the laser aimed at a target that is barely there.
- beat-16 (24 s): Let us slow the whole thing down, to see what one second looks like inside the chamber. A droplet is ejected, travelling through the vacuum at about seventy metres per second, and meets a laser pulse timed to arrive at the very same instant. Then another droplet follows, and another, fifty thousand in that single second, each one a separate explosion that must happen in the same place as the last.
- beat-17 (18 s): And the laser is a machine in its own right, with four amplifying lasers feeding one beam. The driver laser, built by the German company Trumpf, has more than four hundred and fifty thousand individual parts. All of that, to make a flash of light that lasts a tiny fraction of a second and then vanishes.
- beat-18 (19 s): None of this is meant as a laboratory trick; the machine is built to run inside a chip factory, where it has to work again and again. Collecting that flash brings the next problem, because the light is easy to lose. At this wavelength, all matter absorbs the light, including air, so the machine has to run in a vacuum.
- beat-19 (18 s): That is also why the optical path is built from mirrors rather than lenses. But a mirror is not simple here either, because each one still absorbs around thirty percent of the light that reaches it. To reflect anything at all, the mirrors are built from many alternating thin layers of silicon and molybdenum.
- beat-20 (17 s): The layers act together like a hall of mirrors at a microscopic scale, adding up many weak reflections into one useful one. Even so, after a chain of mirrors, much of the original light is gone. That is why the source has to be so violent, and why every watt of light matters so much.
- beat-21 (19 s): Even the stencil has to change, and this is one of the cleverest parts of the design. An ordinary mask lets light pass through its clear parts and blocks it elsewhere, but at this wavelength, all matter absorbs the light. So the mask is a mirror too, built from forty to fifty alternating layers of silicon and molybdenum.
- beat-22 (18 s): The light bounces off it, carries the pattern toward the silicon, and every extra reflection along the way costs more of the precious light. Think about what that means: the machine is a chain of mirrors, from the flash of tin to the disc of silicon. The mirrors have a second, quieter demand, which is smoothness.
- beat-23 (20 s): Zeiss polishes the mirror blanks to a surface roughness of about fifty picometres, a fraction of the width of a single atom. Stretch one of these mirrors to the area of Germany, and its tallest bump would stand one millimetre high. The source that reports this calls Zeiss the only company on Earth that knows how to grind an EUV mirror.
- beat-24 (15 s): Any larger flaw would bend the light by a tiny angle, and a tiny angle at this scale becomes an error on the finished chip. So the machine that prints the future depends on mirrors made by a single company, polished to a degree that is hard to imagine.
- beat-25 (20 s): Put it together, and you can see how strange the whole device is. There is a droplet generator, a laser with hundreds of thousands of parts, a vacuum chamber, and mirrors of astonishing smoothness. The laser comes from Trumpf, the mirrors from Zeiss, and the machine itself from ASML, and the system works only when every one of them does.
- beat-26 (16 s): Today ASML is the only company that produces and sells EUV systems for chip production. Anyone who wants chips drawn with this light has exactly one supplier to turn to. It is a rare thing in industry, a single point that so much can depend on.
- beat-27 (20 s): Yet the story does not end there, because the lines on a chip keep shrinking, and even this light is getting too blunt. The next step is a machine with a bigger opening for the light, measured by a number called the numerical aperture. The first commercial high-NA tool, with a numerical aperture of zero point five five, was assembled at Intel.
- beat-28 (16 s): Machines of this kind cost around three hundred and sixty million dollars each. A larger numerical aperture lets the machine draw finer lines, but it makes everything else harder to get right. And there is a deeper limit waiting, one that no amount of money can polish away.
- beat-29 (17 s): EUV lithography is particularly sensitive to stochastic effects, which is a careful way of saying that chance gets involved. At these scales, each tiny patch of the pattern receives a limited number of particles of light, and a limited number fluctuates from one patch to the next.
- beat-30 (22 s): Some patches get a little too much, some a little too little, and a line that should be straight comes out slightly torn. Picture a light shower falling on a grid of tiles: no two tiles ever collect exactly the same number of raindrops. The more the lines shrink, the more that randomness matters, and no engineer can switch it off, because it is built into the nature of light itself.
- beat-31 (18 s): Engineers fight this with brighter sources and more sensitive coatings, but every fix has a price, in speed, in cost or in some other kind of error. That is the real frontier, no longer a question of better lenses or better lasers, but of how to draw cleanly with so few particles.
- beat-32 (16 s): Everything we have seen so far, the tin, the laser, the vacuum and the mirrors, is a way of buying one thing: a shorter wavelength. What makes the story gripping is the contrast: a tool so delicate that picometres matter, built to run on a factory floor.
- beat-33 (19 s): Chips made with this light trace back to a droplet of tin meeting a pulse of light. That is the quiet miracle of modern manufacturing: it hides its strangest ideas inside things small enough to forget. And it asks a good question about progress: when the physics pushes back, how far will people go to keep the pencil sharp?
- beat-34 (16 s): So the next time you hold a phone, think about what is inside it. A pattern drawn by light, shaped by mirrors polished past what seems possible, powered by tin drops exploding fifty thousand times a second. It took decades and a company most people have never heard of.
- beat-35 (5 s): And the strangest part is that it works, quietly, in a factory somewhere near you.

Write the answer to F:\AI-PROJECTS\longform-explainer\.claude\worktrees\continue-implementation-plan-9d914b\work\the-light-machine\storyboard.json, then run: python tools/plan_storyboard.py --episode work\the-light-machine --check
