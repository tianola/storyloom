"""Where an episode lives, what is on screen, and what it is called — read, not remembered.

Three tools used to answer these questions by typing the same answers into their own source:
`tools/assemble_episode.py` pinned `work/episode-artemis-ii` plus a 32-entry visual map,
`tools/rollout_render.py` pinned seven more paths at that directory, and
`tools/qc_shot_continuity.py` imported the assembler's copies. The result was a pipeline that
could re-build one film and no other, which is the opposite of a house style: a style that only
reaches a master when somebody edits `tools/` is a suggestion, and the episode that skips the edit
ships without the layer.

So the questions move here, and each has one answer:

  `resolve()`     the caller says which film; nothing in `tools/` gets to assume one
  `document()`    the film's own `episode.json`
  `shots()`       `shots.json`, the same file `qc_episode.py` already judges from
  `render_dir()`  a visual layer's output directory, from the contract for the archival layer
  `archive_sources()`  what an archival shot is cut from, and where its clip will land
  `rollout_plan()`     the builder, the baseline and the hero beats the episode was authored with
  `master()`      the deliverable, named for the directory holding it

`shots.json` was already published by the assembler from its own literal, which made the code the
source and the file a copy of it. Reading the file back removes the copy: a future episode,
including one with archival shots, states its own shots and needs no change to any tool.
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from workflow.archive import (ledger as archive_ledger, paths as archive_paths,
                              records as archive_records)

SHOTS_FILENAME = "shots.json"
EPISODE_DOCUMENT = "episode.json"
ROLLOUT_KEY = "rollout"
ROLLOUT_FILES = ("builder", "baseline")
ROLLOUT_BEATS = "finish_beats"


def _work_dir(root) -> Path:
    return Path(root) / "work"


def resolve(root, spec) -> Path:
    """The episode directory this run is about, from whatever the caller wrote.

    An argument is required rather than defaulted: a tool that can guess the current episode is a
    tool that will guess it while nobody is looking, and an unattended build that assembles last
    week's film produces a master that passes every gate.
    """
    value = str(spec).strip() if spec is not None else ""
    if not value:
        raise ValueError("an episode must be named: pass --episode <dir or slug>")
    candidate = Path(value)
    if not candidate.is_absolute():
        # A bare name is a slug under `work/`; anything with a separator is a path from the repo.
        candidate = (_work_dir(root) / candidate if len(candidate.parts) == 1
                     else Path(root) / candidate)
    if not candidate.is_dir():
        raise ValueError(f"episode {value!r} is not a directory; looked at {candidate} "
                         f"(episodes live under {_work_dir(root)})")
    if not (candidate / EPISODE_DOCUMENT).is_file():
        raise ValueError(f"{candidate} has no {EPISODE_DOCUMENT}, so it is not an episode; "
                         "create one with python -m workflow.init_episode")
    return candidate


def document(episode) -> dict:
    path = Path(episode) / EPISODE_DOCUMENT
    if not path.is_file():
        raise ValueError(f"{path} is missing, so nothing states what this episode is")
    body = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(body, dict):
        raise ValueError(f"{path} must hold a JSON object, got {type(body).__name__}")
    return body


def vo_dir(episode) -> Path:
    return Path(episode) / "vo"


def segments_dir(episode) -> Path:
    return Path(episode) / "segments"


def shots_path(episode) -> Path:
    return Path(episode) / SHOTS_FILENAME


def shot_lengths_path(episode) -> Path:
    return Path(episode) / "shot_lengths.json"


def graded_path(episode) -> Path:
    return Path(episode) / "video-graded.mp4"


def qc_dir(episode) -> Path:
    """Where a run's evidence lands: luma tables, cost timings, contact sheets, gate findings."""
    return Path(episode) / "qc"


def music_bed_path(episode) -> Path:
    return Path(episode) / "music" / "bed.wav"


def master(episode) -> Path:
    """The finished film, named for the directory that holds it.

    Deriving the name is what keeps `dist` honest: the publish step already copies
    `<episode dir>-broadcast.mp4`, so a master named anything else is a deliverable describing a
    different film.
    """
    episode = Path(episode)
    return episode / f"{episode.name}.mp4"


def dist_path(episode) -> Path:
    """The upload artifact — the gated master copied byte for byte, never re-encoded."""
    episode = Path(episode)
    return episode / "dist" / f"{episode.name}-broadcast.mp4"


def _relative_posix(value: str, name: str, base: str = "episode") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: must be a non-empty relative path")
    if "\\" in value or PurePosixPath(value).is_absolute() or ".." in PurePosixPath(value).parts:
        raise ValueError(f"{name}: must be a {base}-relative POSIX path, got {value!r}")
    return value


def layers(contract: dict) -> list:
    """The visual layers a film may be cut from, in the order the contract budgets them."""
    return list(contract["archive"]["episode_profile"]["mix"]["layers"])


def render_dir(episode, kind: str, contract: dict) -> Path:
    """Where one layer's rendered clips live inside an episode.

    The archival layer is the exception the contract already declares: its directory is style data
    carrying a `why`, so a rename moves the render, the ingest and this reader together. The
    layers the contract does not name a directory for follow the `renders/<layer>` convention.
    """
    declared = layers(contract)
    if kind not in declared:
        raise ValueError(f"visual layer {kind!r} is not one of the declared layers {declared}; "
                         "a kind outside the taxonomy is judged by nothing")
    if kind == "archive":
        relative = _relative_posix(contract["archive"]["paths"]["render_dir"],
                                   "archive.paths.render_dir")
        return Path(episode) / PurePosixPath(relative)
    return Path(episode) / "renders" / kind


def shots(episode, contract: dict) -> dict:
    """`{(utterance id, kind, name, title, subtitle)}` for every shot in the film.

    Tuples rather than the JSON's dicts because the drawing code already consumes that shape
    (`card_frame` reads `entry[1]` for the card style and `entry[2]`/`entry[3]` for its text, both
    optional), and a reader that flattened everything into a record would rewrite the look code
    for no gain. A card with no subtitle is a shorter tuple, not a missing key.

    An absent or empty table is refused rather than read as "no visuals". The assembler used to
    print `WARNING: no visual for u0NN, using black` and carry on, which is how a hole in the film
    reaches a master with a correct total duration.
    """
    path = shots_path(episode)
    if not path.is_file():
        raise ValueError(f"{path} is missing, so nothing says what is on screen in this episode")
    table = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(table, dict):
        raise ValueError(f"{path} must hold a JSON object keyed by utterance id, got "
                         f"{type(table).__name__}")
    if not table:
        raise ValueError(f"{path} is empty: the shots of this film have not been chosen yet, "
                         "and building it now would ship a black screen over every word")

    declared = set(layers(contract))
    shot_map = {}
    for uid, record in table.items():
        if not isinstance(record, dict):
            raise ValueError(f"{path}: {uid} must be an object with `kind` and `name`, got "
                             f"{type(record).__name__}")
        kind = record.get("kind")
        if kind not in declared:
            raise ValueError(f"{path}: {uid} declares kind {kind!r}, outside the layers "
                             f"{sorted(declared)}")
        name = record.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{path}: {uid} has no `name`, so there is no clip to slice")
        entry = [kind, name]
        for field in ("title", "subtitle"):
            if field in record:
                entry.append(record[field])
        shot_map[uid] = tuple(entry)
    return shot_map


def archive_sources(episode, contract: dict) -> dict:
    """What each declared archival shot is cut from, and where its finished clip lands.

    `{shot name: {"record", "licence", "source", "clip"}}`, `source` and `clip` as `Path`s. The
    shot table drives the answer, not `archive.json`, because the two files disagree in exactly one
    direction that matters: a shot that fell out of the cut leaves its record behind, and a queue
    that walks the records would spend an encode on footage no utterance speaks over.

    The assembler's ingest step and the rollout's `ingest` stage both ask this question, and while
    each answered it for itself they could disagree about the output directory — the ingest writing
    to the contract's `render_dir` while the cutter read a path it had typed — and the film that
    ships then has a black frame where the archive should have been. One lookup makes that
    disagreement unrepresentable, which is the whole point of this module.

    Absence of the layer is not a failure here: `records(required=False)` means a 3D-only film still
    resolves, and whether that absence is a finding is the mix rule's judgement (#148). Presence
    without proof is a failure, so a shot with no record, and a record whose media never arrived,
    raise together, naming the utterance, before any ffmpeg process exists.
    """
    declared = archive_records(episode, contract, required=False)
    rows = archive_ledger(episode, contract)
    clip_dir = render_dir(episode, "archive", contract)
    records_name = archive_paths(contract)["records_filename"]

    wanted: dict[str, list] = {}
    for uid, entry in shots(episode, contract).items():
        if entry[0] == "archive":
            wanted.setdefault(entry[1], []).append(uid)

    problems, found = [], {}
    for name, uids in wanted.items():
        record = declared.get(name)
        if record is None:
            problems.append(
                f"shot {name} ({', '.join(uids)}) is declared `archive` in {shots_path(episode).name} "
                f"but has no record in {records_name}")
            continue
        source = Path(episode) / PurePosixPath(record["asset"])
        if not source.is_file():
            problems.append(
                f"shot {name} ({', '.join(uids)}) reads {source.name} from {records_name}, which is "
                f"not on disk at {source}")
            continue
        found[name] = {"record": record, "licence": rows[str(record["licence"])],
                       "source": source, "clip": clip_dir / f"{name}.mp4"}
    if problems:
        raise ValueError(f"{Path(episode).name} has archival shots it cannot cut: "
                         + "; ".join(problems))
    return found


def rollout_seed() -> dict:
    """The `rollout` block a new episode starts with: every key `rollout_plan()` reads, empty.

    The seed lives beside the reader rather than in `init_episode.py` so the two can never disagree
    about which keys exist — a seeder that added a fourth key the reader never asked for would leave
    every new episode refusing, and a reader that grew a key nobody seeds is the same refusal with
    the message pointing at the author instead of at the tool.
    """
    return {key: "" for key in ROLLOUT_FILES} | {ROLLOUT_BEATS: []}


def rollout_plan(episode, root) -> dict:
    """The builder script, the luma baseline and the hero beats this film was authored to render.

    Which script draws a layer is episode authoring, not driver code: `tools/rollout_render.py`
    carried its builder path, its baseline and one hero beat name as three literals of its own, so
    the queue could render exactly one film and a second episode's `finish` stage re-cut a beat that
    episode never had. They live here now, in the document beside the shot table they draw.

    Refused rather than defaulted, for the reason `resolve()` documents: an unattended build that
    guesses spends the night rendering last week's film, and the master it assembles in the morning
    passes every gate, because the frames it holds are internally consistent with each other. The
    message names the file and the key — whoever reads it at three in the morning is being asked to
    author something, so it has to say what is missing in the words the document uses.
    """
    path = Path(episode) / EPISODE_DOCUMENT
    declared = document(episode).get(ROLLOUT_KEY)
    if not isinstance(declared, dict):
        raise ValueError(
            f"{path} declares no {ROLLOUT_KEY!r} object, so nothing says which script renders this "
            f"film; it needs {', '.join(ROLLOUT_FILES)} and {ROLLOUT_BEATS}")
    missing = [key for key in ROLLOUT_FILES if not str(declared.get(key, "")).strip()]
    if not isinstance(declared.get(ROLLOUT_BEATS), list):
        missing.append(ROLLOUT_BEATS)
    if missing:
        raise ValueError(f"{path}: {ROLLOUT_KEY} declares no {missing}, so the render queue would "
                         "have to guess the film it is rendering")

    plan = {key: Path(root) / _relative_posix(declared[key], f"{path}: {ROLLOUT_KEY}.{key}",
                                              base="repo")
            for key in ROLLOUT_FILES}
    if not plan["builder"].is_file():
        raise ValueError(f"{path}: the builder {declared['builder']!r} is not on disk at "
                         f"{plan['builder']}. An episode is rendered by a script somebody wrote for "
                         "it; the queue will not substitute another film's")
    beats = declared[ROLLOUT_BEATS]
    unnamed = [b for b in beats if not str(b).strip()]
    if unnamed:
        raise ValueError(f"{path}: {ROLLOUT_KEY}.{ROLLOUT_BEATS} holds {unnamed}, which name no "
                         "beat")
    plan[ROLLOUT_BEATS] = tuple(beats)
    return plan


def require_coverage(episode, shot_map: dict, utterance_ids) -> None:
    """Refuse a film whose shots and words do not describe the same timeline.

    Checked before the first ffmpeg call, not during the segment build: an uncovered utterance is
    a black frame in the master, and an orphan shot is GPU minutes burned on a clip nobody sees.
    """
    ids = list(utterance_ids)
    missing = [uid for uid in ids if uid not in shot_map]
    orphans = [uid for uid in shot_map if uid not in set(ids)]
    problems = []
    if missing:
        problems.append(f"{len(missing)} utterance(s) with no shot: {', '.join(missing)}")
    if orphans:
        problems.append(f"{len(orphans)} shot(s) no utterance speaks over: {', '.join(orphans)}")
    if problems:
        raise ValueError(f"{shots_path(episode)} and the narration manifest disagree for "
                         f"{Path(episode).name}: " + "; ".join(problems))
