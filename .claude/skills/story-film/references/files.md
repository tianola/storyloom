# What to write, where, in which format

An episode lives in `work/<name>/` (create it with `workflow.init_episode`). The one command is
`tools/make_episode.py --episode work/<name>` (stages: script, narration, shots, captions, lengths, plan, ingest,
render, assemble, qc). `docs/PRODUCTION-GUIDE.md` section 0 has the run notes.

## Story planning (read by people, not by the pipeline)

- `story/beat-sheet.md`: one line per beat with its seam (**but** / **therefore**), A or B track, the line ids it
  covers, the place, and the purpose (hook, question, guess, complication, person beat, explanation, reversal,
  re-hook, payoff, callback).
- `story/world.md`: one section per place and per character (staging.md §5-7). For a place: who is there at this
  hour and doing what, dominant use, personal objects, wear, practical lights, period markers, colour, sounds. For a
  character: look and sprite key, voice, what they want, how they move, signature gesture.

## Script and its data (read by the gates)

- `research/sources.md`: the claim table; only `verified` claims count.
- `script/narration.md`: one sentence or short passage per line; each line becomes an utterance `u001`, `u002`...
  - untagged line: the narrator;
  - `[name] text`: a character speaking on screen (mouth moves);
  - `[name:thought] text`: inner voice, mouth closed;
  - `{direction}` anywhere: a delivery note for ElevenLabs v3 (`{quietly}`, `{pause}`); removed from captions.
  - Write numbers as words; no digits or symbols in spoken text.
- `script/claims.json`: `{"u001": ["c1", "c3"], ...}`; every line that states a fact lists verified claims; a line with
  no fact may be declared framing.
- `script/cast.json`: `{"narrator": {"voice": "eleven:<id>", "sprite": "explorer", "speed": 1.15}, "<name>": {...}}`.
  The explorer is always the owner's own cloned voice.
- `script/dramatisation.json`: for every character line, `{"basis": ["c7"], "rung": 1-5, "note": "what is documented,
  what is adapted or imagined"}` (rung = the voice ladder in script.md §4).
- `script/story.json`: `question`, `guess`, `reversal`, `payoff` (line ids), `follow` (the thing or person followed),
  `hook {kind: shock|mystery|contradiction|stakes, image}`, `people [{name, line}]`.
- `script/chapters.json`: `{"chapters": [{"title": "a question or event", "from": "u004"}]}`.
- `script/pronounce.json`: respellings for the local Kokoro voice only.

## Picture

- `shots.json`: which beat each line belongs to (`{"u001": {"kind": "3d", "name": "beat-01"}}`); one beat = one place
  and one continuous stretch of time.
- `storyboard.json`, per beat:
  - `scene` (from `workflow/scenes.json`), `params` (time of day, walkers, groups...), `note` (the beat's purpose);
  - `shots`: `[{"view": name | "at:<pin>", "start": seconds, "to": view (a motivated move), "glide": "log"}]`;
  - `cast`: `[{"who": sprite, "speaker": cast name, "bust": bool, "screen": [x, y], "height": share of frame,
    "pose", "face", "acts": [{"at": "word:So" | seconds, "pose", "face"}], "shot": index | "span": [i, j]}]`;
  - `actions`: scene actions at a time; `hud`: at most a place/date card; `cut`: travel | montage | steady.
- New views, places, props or behaviours are code in `tools/blender/models/` (world.py, characters.py) plus an entry in
  `workflow/scenes.json`; the world bible says what they must contain.

## Gates to run

- `tools/qc_script.py --episode work/<name>`: length, hook, chapters, sources, cast and dramatisation, numbers, turns,
  questions, story.json.
- `tools/plan_storyboard.py --episode work/<name> --check`: names, text per minute, chart beats, montage and travel
  shares.
- After rendering: stills (`storyboard_beats.py --still`) and `qc/qc-report.json` (cut rhythm, empty shots, sync,
  loudness). Never loosen a gate; a pilot documents its expected failures in `qc/pilot-gate-status.md`.
