# -*- coding: utf-8 -*-
"""Task 5 driver for the owned-surface rollout: stash stale media, render the beats at
the contract canvas, re-assemble, and pull QC frames with a luma table against the pre-rollout
baseline.

Deliberately staged so the expensive part is only reached after a measured cost estimate:

    python tools/rollout_render.py --episode <dir> cost    <beat>   # one beat, timed, nothing else
    python tools/rollout_render.py --episode <dir> stash            # old beat mp4s + segments aside
    python tools/rollout_render.py --episode <dir> ingest           # the archival layer's clips
    python tools/rollout_render.py --episode <dir> render           # every 3d beat, exit captured
    python tools/rollout_render.py --episode <dir> qc               # luma vs baseline + sheet
    python tools/rollout_render.py --episode <dir> assemble         # re-cut the episode
    python tools/rollout_render.py --episode <dir> gate             # judge against the contract
    python tools/rollout_render.py --episode <dir> dist             # copy the master into dist/
    python tools/rollout_render.py --episode <dir> finish a,b       # wait it out, re-render, QC
    python tools/rollout_render.py --episode <dir> report           # print the table again

`--episode` is required, and it is the only thing that says which film this is: every path below is
derived from it, so a second episode renders, assembles and gates without an edit to this file. The
beat list comes from that episode's `shots.json`, the same table the assembler cuts from, and so do
the three things that say *how* it is rendered — the builder script, the luma baseline and the hero
beats a bare `finish` re-cuts — which live in its `episode.json`, because a queue that guesses a
builder spends the night rendering last week's film.

Nothing here uploads or publishes anywhere but on this disk. Stashing is a move, not a delete,
so a bad render is reversible.
"""
import argparse
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The `ingest` stage delegates to the assembler rather than repeating its ffmpeg calls, so the
# edit tool has to be importable from a driver that is itself imported by tests from `python/`.
for _path in (ROOT, ROOT / "tools"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
from workflow.capabilities import REFUSED, stage_report  # noqa: E402
from workflow.config import blender_executable, style_contract  # noqa: E402
from workflow.episode import (dist_path, master, qc_dir, render_dir, rollout_plan,  # noqa: E402
                              resolve, segments_dir, shot_lengths_path, shots)

import assemble_episode  # noqa: E402

# Evidence is named for the canvas it measured. Labelling these by hand is how a cost table ended
# up describing a render the driver no longer does; the tag is read so it cannot go stale.
CONTRACT = style_contract(ROOT)
CANVAS = CONTRACT["canvas"]
CANVAS_TAG = f"{CANVAS['width']}x{CANVAS['height']}"

# The episode this process is driving, filled in by `select_episode()` from `--episode` before any
# stage runs. They stay module-level rather than becoming eleven parameters because one invocation
# picks one film at startup and every stage beneath it means that film; a detached two-hour render
# is exactly one such process. Nothing may default them — a rollout that guessed the episode would
# spend the night re-rendering the previous one.
EPISODE = BEATS = ARCHIVE = SEGMENTS = QC = STASH = MASTER = DIST = STATE = SHOT_LENGTHS = None
# The authoring side of the same film: which Blender script draws its beats, which luma table the
# QC pass compares against, which beats a bare `finish` re-cuts. Read from `episode.json` by
# `select_episode()` — see `workflow.episode.rollout_plan` for why none of the three may be
# guessed here.
SCRIPT = BASELINE = None
FINISH_BEATS = ()
BLENDER = str(blender_executable(ROOT))


def select_episode(spec, root=ROOT):
    """Point the driver at one episode; every path above is then read off that directory.

    `_pre-720-stash` keeps its era-named slug: it holds the pre-1080p frames the before/after
    sheet is built from, so renaming it would orphan the only "before" the comparison has.
    """
    global EPISODE, BEATS, ARCHIVE, SEGMENTS, QC, STASH, MASTER, DIST, STATE, SHOT_LENGTHS
    global SCRIPT, BASELINE, FINISH_BEATS
    episode = resolve(root, spec)
    plan = rollout_plan(episode, root)
    EPISODE = episode
    BEATS = render_dir(episode, "3d", CONTRACT)
    ARCHIVE = render_dir(episode, "archive", CONTRACT)
    SEGMENTS = segments_dir(episode)
    QC = qc_dir(episode)
    STASH = episode / "_pre-720-stash"
    MASTER = master(episode)
    DIST = dist_path(episode)
    STATE = QC / "rollout-render.json"
    SHOT_LENGTHS = shot_lengths_path(episode)
    SCRIPT = plan["builder"]
    BASELINE = plan["baseline"]
    FINISH_BEATS = plan["finish_beats"]
    return episode


def shot_map():
    return shots(EPISODE, CONTRACT)


def beat_names():
    """The beats this queue renders: the 3D layer, and only it.

    `render` drives Blender, and the layers with another producer — cards drawn by the assembler,
    diagrams built by manim, archive clips ingested below — have no frames for this queue to write.
    `total_frames()` is the same cost model, so it follows the same scope.
    """
    names = {e[1] for e in shot_map().values() if e[0] == "3d"}
    table = json.loads(SHOT_LENGTHS.read_text(encoding="utf-8"))
    unknown = sorted(names - set(table))
    if unknown:
        raise SystemExit("3d shots with no shot length: " + ", ".join(unknown))
    return sorted(names)


def total_frames():
    table = json.loads(SHOT_LENGTHS.read_text(encoding="utf-8"))
    return sum(int(round(table[n] * CANVAS["fps"])) for n in beat_names())


def frames_written():
    """Frames the rollout has put on disk: the one progress signal a wait loop can act on.

    `total_frames()` is the planned total read from shot_lengths.json, so it says nothing
    about whether a render is advancing.
    """
    return len(list(BEATS.glob("*/*.png")))


def preflight_host():
    """The machine the guard probes: this box in production, a fake one under test.

    A function rather than an argument because `__main__` calls the stages with no arguments at
    all — an unattended queue must not be able to skip the check by forgetting to pass one.
    """
    return None


def guard():
    """Refuse to *start* work this machine cannot finish. Returns REFUSED, or None to proceed.

    The motion phase owes both Blender and manim, and a rollout is hours of GPU time that the
    finish queue runs while nobody is awake. #138 found manim missing and #139 installed it, which
    is the class of failure this catches; the optional capabilities (latex, for MathTex) report
    but do not refuse, because a gate that blocks on optional work gets routed around.
    """
    refusal = stage_report(ROOT, "motion", host=preflight_host())
    if refusal:
        print("rollout refused - the motion stage needs capabilities this machine lacks:",
              flush=True)
        print(refusal, flush=True)
        return REFUSED
    return None


def run_blender(args, log_path, timeout=None):
    """Run Blender and return (exit_code, seconds). The exit code is captured from Blender
    itself; piping through grep/tail would report the pipe's status instead."""
    cmd = [BLENDER, "-b", "-P", str(SCRIPT)] + args
    t0 = time.time()
    with open(log_path, "w", encoding="utf-8") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout)
    dt = time.time() - t0
    return proc.returncode, dt


def _alive(pid):
    """Is this pid still running?

    Never `os.kill(pid, 0)`: on Windows that is not a probe, it is TerminateProcess — a
    liveness check that can kill the two-hour render it is asking about, and on this machine
    it returned False for a Blender that was measurably still writing frames. Query-only here,
    and tasklist is not parsed either, because a transient tasklist failure reads as
    'the render died' and invites the same double-spawn this file exists to prevent.
    """
    if not pid:
        return False
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def _spawn(args, log_path):
    """Start Blender outside this process tree and return its pid.

    Whoever drives a two-hour render gets killed eventually — the harness, a compaction, a
    closed terminal. When Blender is a child, that kill costs the whole rollout; when it is
    detached, the render finishes and the next session only has to find it again. Hence this
    and STATE: the pid is on disk before anything waits.
    """
    QC.mkdir(parents=True, exist_ok=True)
    # A regular empty file, not NUL: a character device still reports isatty() and a headless
    # Blender that reaches a prompt would block forever with no console to answer it.
    stdin_file = QC / "render-stdin.txt"
    stdin_file.touch(exist_ok=True)
    cmd = [BLENDER, "-b", "-P", str(SCRIPT)] + list(args)
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    with open(log_path, "w", encoding="utf-8") as out, open(stdin_file) as fh:
        proc = subprocess.Popen(cmd, stdin=fh, stdout=out, stderr=subprocess.STDOUT,
                                creationflags=flags, cwd=str(ROOT))
    return proc.pid


_sleep = time.sleep


def read_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def write_state(**changed):
    QC.mkdir(parents=True, exist_ok=True)
    state = read_state()
    state.update(changed)
    STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
    return state


def mean_luma(path):
    import numpy as np
    from PIL import Image
    arr = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    return float(arr[::3, ::3].mean() / 255.0)


def cost(name):
    refusal = guard()
    if refusal:
        return refusal
    QC.mkdir(parents=True, exist_ok=True)
    log = QC / f"cost-{name}.log"
    print(f"timed {CANVAS_TAG} render of one beat: {name}", flush=True)
    code, dt = run_blender(["--only", name], log, timeout=3600)
    table = json.loads(SHOT_LENGTHS.read_text(encoding="utf-8"))
    frames = int(round(table[name] * CANVAS["fps"]))
    if code != 0:
        print(f"BLENDER_EXIT={code} — see {log}")
        return 1
    spf = dt / max(frames, 1)
    all_frames = total_frames()
    print(f"  beat {name}: {frames} frames in {dt:.1f}s -> {spf:.3f} s/frame")
    print(f"  whole episode: {all_frames} frames -> {spf * all_frames / 60:.1f} min at this rate")
    ratio = (CANVAS["width"] * CANVAS["height"]) / (640 * 360)
    print(f"  (baseline was 0.197 s/frame at 640x360; {ratio:.0f}x the pixels now)")
    (QC / f"cost-{CANVAS_TAG}.json").write_text(json.dumps(
        {"beat": name, "frames": frames, "seconds": round(dt, 1),
         "s_per_frame": round(spf, 4), "episode_frames": all_frames,
         "episode_minutes": round(spf * all_frames / 60, 1),
         "measured": datetime.now().isoformat(timespec="seconds")}, indent=1),
        encoding="utf-8")
    return 0


def stash():
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = STASH / stamp
    moved = 0
    # The mid-frame PNGs go too: they are the only "before" the after/after sheet can be
    # built from, and the next render overwrites them in place.
    for src_dir, patterns in ((BEATS, ("*.mp4", "*-mid.png")), (SEGMENTS, ("*.mp4",))):
        files = [f for pat in patterns for f in src_dir.glob(pat)]
        if not files:
            continue
        out = dest / src_dir.name
        out.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.move(str(f), str(out / f.name))
            moved += 1
    print(f"stashed {moved} files under {dest} (moved, not deleted)")
    print(f"remaining beat mp4s: {len(list(BEATS.glob('*.mp4')))}")
    print(f"stashed mid frames: {len(list((dest / BEATS.name).glob('*-mid.png')))}")
    print(f"remaining segments:  {len(list(SEGMENTS.glob('*.mp4')))}")
    (STASH / "latest").write_text(str(dest), encoding="utf-8")
    return 0


def latest_stash():
    pointer = STASH / "latest"
    if pointer.exists():
        p = Path(pointer.read_text(encoding="utf-8").strip())
        if p.exists():
            return p
    dirs = sorted(d for d in STASH.glob("*-*-*") if d.is_dir()) if STASH.exists() else []
    return dirs[-1] if dirs else None


def ingest():
    """Produce this episode's archival clips, by asking the assembler to make them.

    The recipe — the record, the rights row, the screen time, the mirror guard, the credit plate —
    is `tools/assemble_episode.py`'s, and repeating it here would hand the queue and the cutter two
    ideas of what `renders/archive/<shot>.mp4` means, which is the same divergence that puts a black
    frame in a master. The stage exists so an unattended rollout has a step that makes the layer
    before `assemble` refuses to cut without it.
    """
    refusal = stage_report(ROOT, "edit", host=preflight_host())
    if refusal:
        print("rollout refused - the ingest stage needs capabilities this machine lacks:",
              flush=True)
        print(refusal, flush=True)
        return REFUSED
    manifest = assemble_episode.load_manifest(EPISODE)
    map_ = shot_map()
    made = assemble_episode.ingest_archive(EPISODE, manifest, map_, CONTRACT, root=ROOT)
    # The declared total comes from the shot table rather than from the assembler's own source
    # lookup: this line reports progress, and a helper that refuses an incomplete archive has
    # already had its turn inside `ingest_archive`.
    declared = {e[1] for e in map_.values() if e[0] == "archive"}
    on_disk = len(list(ARCHIVE.glob("*.mp4"))) if ARCHIVE.is_dir() else 0
    print(f"archive ingest: {len(made)} clip(s) produced, {on_disk} of {len(declared)} archival "
          f"shot(s) now on disk under {ARCHIVE}", flush=True)
    return 0


def render(poll=30, limit=6 * 3600):
    names = beat_names()
    # Named for the canvas, not the beat count: `render-all19-v4.log` was written by a driver that
    # had already stopped rendering 19 beats, which is how an evidence file starts lying.
    log = QC / f"render-all-{CANVAS_TAG}.log"
    state = read_state()
    pid = state.get("pid")
    if state.get("status") == "running" and _alive(pid):
        print(f"attaching to the Blender already running as pid {pid}", flush=True)
    else:
        # The check is on the spawn, not on the attach: those frames are already paid for, and
        # walking away would skip the state write that tells the next session how it ended.
        refusal = guard()
        if refusal:
            return refusal
        pid = _spawn([], log)
        print(f"spawned detached blender pid {pid} — {len(names)} beats, "
              f"{total_frames()} frames at {CANVAS_TAG}, log {log}", flush=True)
    write_state(status="running", pid=pid, log=str(log), beats=names,
                started=datetime.now().isoformat(timespec="seconds"))
    t0 = time.time()
    while _alive(pid):
        if time.time() - t0 > limit:
            write_state(status="timeout")
            print(f"still rendering after {limit / 3600:.0f} h; pid {pid} left running",
                  flush=True)
            return 2
        _sleep(poll)
        done = sum(1 for n in names if (BEATS / f"{n}.mp4").exists())
        print(f"  {done}/{len(names)} beats, {len(list(BEATS.glob('*/*.png')))} frames "
              f"written (pid {pid})", flush=True)
    missing = [n for n in names if not (BEATS / f"{n}.mp4").exists()]
    write_state(status="failed" if missing else "done",
                finished=datetime.now().isoformat(timespec="seconds"), missing=missing)
    if missing:
        print("MISSING:", ", ".join(missing), flush=True)
    print(f"beat mp4s present: {len(names) - len(missing)} of {len(names)}", flush=True)
    return 1 if missing else 0


def sheet(cols=5, thumb=(360, 203)):
    """Before/after contact sheet: stashed pre-rollout mid frames above the new ones.

    The user judges this pipeline by looking at frames, not by reading numbers, so the
    sheet is the deliverable and the luma table is its footnote.
    """
    from PIL import Image, ImageDraw
    old_dir = latest_stash()
    names = beat_names()
    cw, ch = thumb
    pad, label_h = 6, 18
    per = label_h * 2 + ch * 2 + pad * 3
    w = cols * (cw + pad) + pad
    h = ((len(names) + cols - 1) // cols) * per + pad
    canvas = Image.new("RGB", (w, h), (8, 10, 24))
    draw = ImageDraw.Draw(canvas)
    pairs = 0
    for i, name in enumerate(names):
        new = BEATS / f"{name}-mid.png"
        old = (old_dir / BEATS.name / f"{name}-mid.png") if old_dir else None
        r, c = divmod(i, cols)
        x = pad + c * (cw + pad)
        y = pad + r * per
        for row, path, tag in ((0, old, "before"), (1, new, "after")):
            ty = y + row * (ch + label_h + pad) + label_h
            if path and path.exists():
                im = Image.open(path).convert("RGB").resize((cw, ch))
                canvas.paste(im, (x, ty))
                if row == 0:
                    pairs += 1
            else:
                draw.rectangle([x, ty, x + cw, ty + ch], outline=(60, 60, 70))
            draw.text((x + 2, ty - label_h), f"{name}  [{tag}]", fill=(200, 200, 210))
    out = QC / "rollout-before-after.png"
    canvas.save(str(out))
    print(f"contact sheet: {out}  ({pairs}/{len(names)} beats have a before frame)")
    return out


def qc():
    QC.mkdir(parents=True, exist_ok=True)
    base = {}
    if BASELINE.exists():
        for line in BASELINE.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0].replace(".", "").isdigit():
                base[Path(parts[1]).name.replace("-mid.png", "")] = float(parts[0])
    rows = []
    for name in beat_names():
        mid = BEATS / f"{name}-mid.png"
        if not mid.exists():
            rows.append((name, None, base.get(name), "no still"))
            continue
        luma = mean_luma(mid)
        rows.append((name, round(luma, 3), base.get(name), ""))
        shutil.copyfile(str(mid), str(QC / f"rollout-{name}.png"))
    print(f"{'beat':22} {'now':>6} {'base':>6}  note")
    for name, now, b, note in rows:
        flag = ""
        if now is not None and now < 0.02:
            flag = "BLACK"
        elif now is not None and b is not None and abs(now - b) > 0.25:
            flag = "big shift"
        print(f"{name:22} {str(now):>6} {str(b):>6}  {note or flag}")
    blacks = [r[0] for r in rows if r[1] is not None and r[1] < 0.02]
    absent = [r[0] for r in rows if r[3] == "no still"]
    (QC / "rollout-luma.json").write_text(json.dumps(
        {"per_beat": {r[0]: {"now": r[1], "baseline": r[2]} for r in rows},
         "black": blacks, "missing_still": absent}, indent=1), encoding="utf-8")
    print(f"\nblack beats: {blacks or 'none'}")
    print(f"missing stills: {absent or 'none'}")
    print(f"qc frames copied to {QC}")
    sheet()
    return 1 if (blacks or absent) else 0


def assemble():
    cmd = [sys.executable, str(ROOT / "tools/assemble_episode.py"),
           "--episode", str(EPISODE)]
    log = QC / f"assemble-{CANVAS_TAG}.log"
    with open(log, "w", encoding="utf-8") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT)
    print(f"ASSEMBLE_EXIT={proc.returncode} — log {log}")
    ep = MASTER
    if ep.exists():
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", str(ep)], capture_output=True, text=True)
        size = ep.stat().st_size / 1e6
        print(f"episode: {ep}  {dur.stdout.strip()}s  {size:.1f} MB")
    return proc.returncode


def gate():
    """Judge the assembled master against the style contract, the way the guide documents it.

    PRODUCTION-GUIDE section 8: the episode is finished when `qc_episode.py` reports no
    errors. An mp4 that exists is not that — the wrong-canvas master #125 was written to catch
    assembled to exit 0 with a clean log, so the judgement has to be part of the unattended
    queue rather than something someone remembers to type at noon.
    """
    QC.mkdir(parents=True, exist_ok=True)
    out = QC / "qc-episode.json"
    log = QC / f"gate-{CANVAS_TAG}.log"
    cmd = [sys.executable, str(ROOT / "tools/qc_episode.py"),
           "--episode", str(EPISODE), "--master", str(MASTER), "--json", str(out)]
    with open(log, "w", encoding="utf-8") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT)
    print(f"GATE_EXIT={proc.returncode} — findings {out}, log {log}", flush=True)
    return proc.returncode


def _digest(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def dist():
    """Copy the gated master into `dist/` byte for byte — the artifact that gets uploaded.

    PRODUCTION-GUIDE section 7: this is a copy, not a second encode. The loudnorm and look
    passes already happened inside the assembler, so re-encoding here would cost quality for
    nothing. It is scripted because the hand-kept copy was, at 06:30, a 02:06 render sitting
    under the deliverable's exact name while the master the gate judges had moved on.

    The copy lands as `.part` and is renamed only after both digests match: a 340 MB stream
    that dies half-way must leave the previous artifact alone, not replace it with a
    truncated mp4 that uploads as a broken episode.
    """
    if not MASTER.exists():
        print(f"DIST refused: no master at {MASTER}", flush=True)
        return 1
    DIST.parent.mkdir(parents=True, exist_ok=True)
    part = DIST.with_suffix(".part")
    shutil.copyfile(MASTER, part)
    src, got = _digest(MASTER), _digest(part)
    if src != got:
        part.unlink(missing_ok=True)
        print(f"DIST refused: copy {got} does not match master {src}", flush=True)
        return 1
    part.replace(DIST)
    print(f"DIST: {DIST}  {DIST.stat().st_size / 1e6:.1f} MB  md5 {src}", flush=True)
    return 0


def beats_from(values):
    """The finish queue's beat list, from the names typed after the stage.

    Trailing and doubled commas are dropped rather than turned into an `--only` field that
    matches no beat, because Blender would then render nothing and exit 0.
    """
    return tuple(b for a in values for b in a.split(",") if b)


def finish(beats=(), poll=60, stall=45 * 60, limit=24 * 3600):
    """Wait for the rollout to end, re-render the beats polished after it started, then
    QC and assemble — so that nobody has to be awake at three in the morning to type it.

    With no beats typed, the list is the episode's own — `FINISH_BEATS`, read from `episode.json`
    by `select_episode()`. A bare `finish` on a second film must re-cut that film's hero shots, not
    the ones this queue was written for.

    A Blender process reads its builder script once, at startup. Any detail pass written
    while the rollout is running is therefore absent from the mp4s that job is producing,
    and those beats have to be rendered a second time after it finishes. Rendering them
    concurrently instead would put two Blenders into the same frame directory.

    Refuses outright if the rollout left beats unencoded: assembling 12 of 19 beats is a
    shorter episode, and the assembler exits 0 doing it.

    The wait gives up on a render that has stopped writing frames, not on one that has been
    running a long time. Seen coming, measured 2026-11-12 17:14: at the old 9 h wall-clock
    ceiling Blender was alive with 4121 frames owed, which at the 44 frames/min the disk was
    then accepting left 1.6 h of work — and a queue that quits there leaves the episode with
    no re-render, no QC, no master and no contract verdict, which is the whole point of it.
    `limit` stays as a last resort for a render that advances so slowly it is not worth
    waiting another day for.
    """
    beats = tuple(beats) or FINISH_BEATS
    state = read_state()
    pid = state.get("pid")
    t0 = time.time()
    seen = frames_written()
    last_advance = t0
    # The process is the ground truth, not its status string. `render()` gives up at its own
    # six-hour limit and writes "timeout" while Blender is still putting frames down — and at
    # the measured 1.84 s/frame over 12480 frames the 1080p rollout runs past that limit.
    # Keyed on `status == "running"`, finish() fell straight through the window and started a
    # second Blender into the same frame-####.png directories.
    while _alive(pid):
        now = time.time()
        written = frames_written()
        if written > seen:
            seen, last_advance = written, now
        if now - last_advance > stall:
            print(f"no new frame for {stall / 60:.0f} min with pid {pid} still alive; "
                  f"finish queue gave up waiting", flush=True)
            return 2
        if now - t0 > limit:
            print(f"the rollout is still advancing but has run {limit / 3600:.0f} h; "
                  f"finish queue gave up waiting", flush=True)
            return 2
        _sleep(poll)
        state = read_state()
        pid = state.get("pid")
    print(f"rollout ended (pid {pid} gone, status={state.get('status')})", flush=True)

    # Go/no-go from the artifacts, not from the status: an episode assembled with beats missing
    # is shorter than scripted, and the assembler exits 0 doing it.
    missing = [n for n in beat_names() if not (BEATS / f"{n}.mp4").exists()]
    if missing:
        write_state(status="failed", missing=missing,
                    finished=datetime.now().isoformat(timespec="seconds"))
        print(f"MISSING: {', '.join(missing)} — refusing to re-render or assemble on top of "
              f"them; re-run `render` first", flush=True)
        return 1

    # Checked after the wait, not before it: waiting launches nothing, and the queue that gave up
    # on a wedged render still has to say so rather than quietly become a refusal.
    refusal = guard()
    if refusal:
        return refusal

    for beat in beats:
        log = QC / f"finish-{beat}.log"
        code, dt = run_blender(["--only", beat], log, timeout=3 * 3600)
        print(f"re-rendered {beat}: exit {code} in {dt / 60:.1f} min — log {log}", flush=True)
        if code != 0:
            write_state(status="finish-failed", failed_beat=beat,
                        finished=datetime.now().isoformat(timespec="seconds"))
            return 1

    qrc = qc()
    arc = assemble()
    # The gate runs whenever there is a master to gate. A black beat is a fact about the
    # frames, not a reason to stop one step before the verdict that defines done — and an
    # assemble that produced nothing has nothing to gate.
    grc = gate() if arc == 0 else None
    rc = arc
    if rc == 0:
        rc = qrc if grc is None else (grc or qrc)
    # Publishing is the reward for a clean run, never part of the judgement itself: dist/ is
    # the file a human uploads, so a chain that was refused must leave the previous artifact
    # alone rather than dress a rejected master in the deliverable's name.
    drc = dist() if rc == 0 else None
    if drc:
        rc = drc
    write_state(status="finished", re_rendered=list(beats), qc_exit=qrc,
                assemble_exit=arc, gate_exit=grc, dist_exit=drc,
                finished=datetime.now().isoformat(timespec="seconds"))
    print(f"finish queue done, exit {rc}", flush=True)
    return rc


STAGES = {"stash": stash, "ingest": ingest, "render": render, "qc": qc, "report": qc,
          "assemble": assemble, "gate": gate, "dist": dist, "finish": finish}


def stage_callable(stage):
    """Resolve a command-line stage. An unknown name is an error, not the report.

    `.get(stage, qc)` made a typo exit 0 with a plausible QC table printed, which on a
    six-hour render means the mistake surfaces only when the frames are missing.
    """
    if stage not in STAGES:
        raise SystemExit(f"unknown stage {stage!r}; expected one of "
                         + ", ".join(sorted(STAGES)))
    return STAGES[stage]


def main(argv=None, root=ROOT):
    argv = sys.argv[1:] if argv is None else list(argv)
    parser = argparse.ArgumentParser(
        description="Drive one episode's render rollout: cost, stash, ingest, render, qc, "
                    "assemble, gate, dist, finish.")
    parser.add_argument("--episode", required=True,
                        help="episode directory or slug under work/ (required: this driver has no "
                             "current episode of its own)")
    parser.add_argument("stage", nargs="?", default="report",
                        help="one of " + ", ".join(sorted(set(STAGES) | {"cost"}))
                             + " (default: report)")
    parser.add_argument("rest", nargs="*",
                        help="the beat list: the one beat to time for `cost`, the comma-separated "
                             "beats to re-cut for `finish`")
    args = parser.parse_args(argv)
    select_episode(args.episode, root)

    if args.stage == "cost":
        if not args.rest:
            raise SystemExit("`cost` needs the one beat to time: "
                             "... --episode <dir> cost <beat>")
        return cost(args.rest[0])
    fn = stage_callable(args.stage)
    if args.stage == "finish":
        return fn(beats=beats_from(args.rest))
    return fn()


if __name__ == "__main__":
    sys.exit(main())
