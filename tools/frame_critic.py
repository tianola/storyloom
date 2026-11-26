"""A second pair of eyes on the rendered 3D beats: stills go to Claude, a verdict comes back.

The QC gate measures what numbers can measure (motion, loudness, rhythm, captions). What it cannot
see is whether a picture *works*: people that read as shop mannequins, a figure too small to read in
a wide shot, a beat whose picture does not show what the narrator is saying, a label on top of a
face, a frame that is nearly black. Those were found by eye, after a full render, every time.

    python tools/frame_critic.py --episode work/X               # every rendered beat
    python tools/frame_critic.py --episode work/X --beats beat-01,beat-04
    python tools/frame_critic.py --episode work/X --dry-run     # what would be sent, no API call
    python tools/frame_critic.py --episode work/X --strict      # exit 1 on any major problem

For each beat with `renders/3d/<beat>.mp4`, three stills (15%, 50%, 85%) are sent with the beat's
storyboard entry and its narration. The answer is structured (verdict, problems with kind, severity,
frame and a note) and lands in `qc/frame-critic.json`. A beat whose stills and storyboard entry have
not changed since its last review is not sent again. Advisory: it never edits anything, and it only
fails the run with --strict.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

AT = (0.15, 0.5, 0.85)
STILL_WIDTH = 1280
KINDS = ["mannequin_people", "subject_too_small", "off_story", "framing", "too_dark", "text_clash",
         "geometry", "anachronism", "empty_frame", "other"]

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fix"]},
        "summary": {"type": "string"},
        "problems": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": KINDS},
                    "severity": {"type": "string", "enum": ["minor", "major"]},
                    "frame": {"type": "integer"},
                    "note": {"type": "string"},
                },
                "required": ["kind", "severity", "frame", "note"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdict", "summary", "problems"],
    "additionalProperties": False,
}

SYSTEM = """You review stills from the 3D beats of a narrated documentary film, the way a picture editor
does before the cut is locked. Each beat is one continuous scene rendered in Blender; you get three
stills from it (numbered 1, 2, 3 in time order), the storyboard entry the scene was built from and the
narration the viewer hears over it.

Judge only what a viewer would notice. Report a problem when it is visible in a still, with the still's
number, and say what to change in one sentence a 3D artist can act on.

Kinds of problem:
- mannequin_people: people read as dolls or shop dummies (smooth featureless skin, identical faces or
  clothes, bald when they should have hair, skin showing through clothing gaps, stiff T-pose arms).
- subject_too_small: the person or object the narration is about is too small to read on a phone screen.
- off_story: the picture does not show what the narration says at that moment, or contradicts it.
- framing: the subject is cropped badly, the camera looks at nothing, or the horizon or composition is off.
- too_dark: the subject is lost in darkness or crushed blacks (night scenes may be dark, not unreadable).
- text_clash: on-screen text is unreadable, overlaps a face or another label, or leaves the frame.
- geometry: objects intersect, float, or are visibly broken.
- anachronism: something that does not belong in the period and place of the story.
- empty_frame: a still that is black, blank or missing its scene.
- other: anything else a viewer would notice.

major = a viewer would notice it in passing and it hurts the film; minor = worth fixing if cheap.
verdict is "fix" when there is at least one major problem, else "pass". Keep the summary to two
sentences. Do not invent problems to have something to say: a clean beat is a pass with no problems."""


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def stills(video, out_dir, at=AT):
    """JPEG stills at the given fractions of the clip, STILL_WIDTH wide."""
    total = duration(video)
    paths = []
    for i, f in enumerate(at, start=1):
        path = Path(out_dir) / f"{Path(video).stem}-{i}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{total * f:.3f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={STILL_WIDTH}:-2", "-q:v", "3", str(path)], check=True)
        paths.append(path)
    return paths


def narration_by_beat(episode):
    """{beat: what the viewer hears over it}; empty when the episode has not got that far."""
    try:
        import plan_storyboard
        return {b["name"]: b["text"] for b in plan_storyboard.beats_of(episode)}
    except (OSError, ValueError, KeyError):
        return {}


def fingerprint(images, entry, narration):
    h = hashlib.sha1(json.dumps([entry, narration], sort_keys=True).encode("utf-8"))
    for p in images:
        h.update(Path(p).read_bytes())
    return h.hexdigest()


def brief(beat, entry, narration):
    return (f"BEAT {beat}\n\nSTORYBOARD ENTRY\n{json.dumps(entry, indent=1, ensure_ascii=False)}\n\n"
            f"NARRATION OVER THIS BEAT\n{narration or '(not available)'}\n\n"
            "Review stills 1, 2 and 3 above.")


def review(episode, beats=None, ask=None, dry_run=False, log=print):
    """-> the report dict (also written to qc/frame-critic.json unless dry_run)."""
    episode = Path(episode)
    board = json.loads((episode / "storyboard.json").read_text(encoding="utf-8"))["beats"]
    renders = episode / "renders" / "3d"
    report_path = episode / "qc" / "frame-critic.json"
    previous = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {"beats": {}}
    said = narration_by_beat(episode)
    wanted = [b for b in board if beats is None or b in beats]
    report = {"model": None, "beats": {}}
    if ask is None and not dry_run:
        import claude_client
        report["model"] = claude_client.MODEL

        def ask(system, user, images):
            return claude_client.ask_json(system, user, SCHEMA, images=images)
    with tempfile.TemporaryDirectory() as tmp:
        for beat in wanted:
            video = renders / f"{beat}.mp4"
            if not video.is_file():
                log(f"[{beat}] no render, skipped")
                continue
            images = stills(video, tmp)
            entry, narration = board[beat], said.get(beat, "")
            key = fingerprint(images, entry, narration)
            old = previous.get("beats", {}).get(beat)
            if old and old.get("fingerprint") == key:
                report["beats"][beat] = old
                log(f"[{beat}] unchanged since its last review: {old['verdict']}")
                continue
            if dry_run:
                log(f"[{beat}] would send {len(images)} stills + storyboard entry + {len(narration.split())} words")
                continue
            answer = ask(SYSTEM, brief(beat, entry, narration), images)
            answer["fingerprint"] = key
            report["beats"][beat] = answer
            majors = sum(1 for p in answer["problems"] if p["severity"] == "major")
            log(f"[{beat}] {answer['verdict']}: {majors} major, {len(answer['problems']) - majors} minor. {answer['summary']}")
    if not dry_run:
        kept = {b: v for b, v in previous.get("beats", {}).items() if b not in report["beats"] and b in board}
        report["beats"] = {**kept, **report["beats"]}
        report_path.parent.mkdir(exist_ok=True)
        partial = report_path.with_name(report_path.name + ".tmp")
        partial.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
        partial.replace(report_path)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episode", type=Path, required=True)
    ap.add_argument("--beats", help="comma-separated beat names (default: every beat with a render)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 when any beat has a major problem")
    args = ap.parse_args(argv)
    episode = args.episode if args.episode.is_absolute() else ROOT / args.episode
    beats = {b for b in args.beats.split(",") if b} if args.beats else None
    try:
        report = review(episode, beats, dry_run=args.dry_run)
    except RuntimeError as exc:                 # ClaudeError
        print(f"frame_critic: {exc}", file=sys.stderr)
        return 2
    if args.dry_run:
        return 0
    fixes = [b for b, v in report["beats"].items() if v["verdict"] == "fix"]
    print(f"\n{len(report['beats'])} beat(s) reviewed, {len(fixes)} to fix" + (f": {', '.join(fixes)}" if fixes else ""))
    print(f"report: {episode / 'qc' / 'frame-critic.json'}")
    return 1 if args.strict and fixes else 0


if __name__ == "__main__":
    sys.exit(main())
