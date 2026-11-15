# -*- coding: utf-8 -*-
"""The rollout render must survive the thing that always kills it: the controller.

Task 5 runs Blender over all 19 beats, which is ~2 hours of GPU time. When `render()` kept
Blender as a child of the agent's own background Bash task, a killed controller left the
driver dead (exit 2, no summary line, a reported elapsed time that did not match the disk
timestamps) while its orphan quietly carried on — so the next session had to guess whether
a render was running by reading mtimes, and re-running `render` would have started a second
Blender writing into the same directories.

These tests pin the contract instead: the pid is recorded before anything waits, a second
call attaches rather than spawns, and the exit code is decided by the artifacts on disk, not
by whatever happened to the parent process.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "python"))

import rollout_render as R  # noqa: E402
from host_double import healthy_host  # noqa: E402
from workflow.capabilities import REFUSED  # noqa: E402


class Harness:
    """A render() call against faked Blender: no GPU, no real processes."""

    def __init__(self, tmp, alive=(), beats=(), host=None):
        self.tmp = Path(tmp)
        self.beats = list(beats)
        self.alive = list(alive)          # return values of successive liveness polls
        self.spawned = 0
        self.host = host                  # the machine the preflight guard probes
        self.state_reads = []
        self._orig = (R.BEATS, R.QC, R.STATE, R._alive, R._spawn, R._sleep,
                      R.beat_names, R.total_frames, R.preflight_host)

    def __enter__(self):
        qc = self.tmp / "qc"
        qc.mkdir(parents=True, exist_ok=True)
        beats = self.tmp / "3d"
        beats.mkdir(parents=True, exist_ok=True)
        for name in self.beats:
            (beats / f"{name}.mp4").write_bytes(b"\0")

        def spawn(args, log_path):
            self.spawned += 1
            Path(log_path).write_text("Fra:1 | Rendering 1 / 32 samples\n", encoding="utf-8")
            return 4242

        R.BEATS, R.QC, R.STATE = beats, qc, qc / "rollout-render.json"
        R._alive = lambda pid: self.alive.pop(0) if self.alive else False
        R._spawn = spawn
        R._sleep = lambda s: None
        R.beat_names = lambda: sorted(self.beats or ["a", "b"])
        R.total_frames = lambda: 100 * len(R.beat_names())
        R.preflight_host = lambda: self.host if self.host is not None else healthy_host(ROOT)
        return self

    def __exit__(self, *exc):
        (R.BEATS, R.QC, R.STATE, R._alive, R._spawn, R._sleep,
         R.beat_names, R.total_frames, R.preflight_host) = self._orig
        return False

    @property
    def state(self):
        return json.loads(R.STATE.read_text(encoding="utf-8"))


class TestLivenessProbe(unittest.TestCase):
    """`_alive` runs against real processes, because the bug it guards is a platform one:
    os.kill(pid, 0) on Windows is TerminateProcess, not a probe. Mocked tests cannot see it.
    """

    def test_probing_a_live_process_reports_alive_and_leaves_it_running(self):
        import subprocess
        import time
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3)"])
        for _ in range(2):
            self.assertTrue(R._alive(child.pid), "the probe called a live pid dead")
        time.sleep(0.2)
        self.assertEqual(child.wait(timeout=30), 0, "the probe killed the process it asked about")

    def test_a_pid_that_never_existed_is_not_alive(self):
        self.assertFalse(R._alive(None))
        self.assertFalse(R._alive(0))
        self.assertFalse(R._alive(2 ** 31 - 1))


class TestResumableRender(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="rollout-state-")

    def test_the_pid_is_on_disk_before_anything_waits(self):
        """A controller that dies mid-render must be able to answer 'is one running?'."""
        with Harness(self.tmp, alive=[False], beats=["a", "b"]):
            R.render()
        state = json.loads((Path(self.tmp) / "qc" / "rollout-render.json").read_text(
            encoding="utf-8"))
        self.assertEqual(state["pid"], 4242)
        self.assertIn(state["status"], ("done", "failed"))
        self.assertTrue(state["started"], "the render must stamp when it began")

    def test_a_second_call_attaches_instead_of_spawning_a_second_blender(self):
        """Two Blenders writing the same frame directories is how a rollout gets corrupted."""
        with Harness(self.tmp, alive=[True, False], beats=["a", "b"]) as h:
            R.render()                      # spawns and then loses its parent
            state = h.state
            state["status"] = "running"
            state["pid"] = 4242
            R.STATE.write_text(json.dumps(state), encoding="utf-8")
            h.alive = [True, False]         # still alive at the first poll of call two
            R.render()
            self.assertEqual(h.spawned, 1, "the second call started a second Blender")

    def test_exit_code_comes_from_the_beats_on_disk_not_from_the_parent(self):
        with Harness(self.tmp, alive=[False], beats=["a", "b"]) as h:
            R.BEATS.joinpath("b.mp4").unlink()      # beat b never finished
            code = R.render()
            self.assertEqual(code, 1)
            self.assertEqual(h.state["status"], "failed")
            self.assertEqual(h.state["missing"], ["b"])

    def test_every_beat_present_is_a_pass(self):
        with Harness(self.tmp, alive=[False], beats=["a", "b"]) as h:
            self.assertEqual(R.render(), 0)
            self.assertEqual(h.state["status"], "done")
            self.assertEqual(h.state["missing"], [])


class TestStageDispatch(unittest.TestCase):
    """An unknown stage must fail, not quietly print a report.

    `__main__` used `.get(stage, qc)`, so `python tools/rollout_render.py renaedr` ran the
    read-only QC pass and exited 0. Seen live 2026-11-12: a `--help` probe returned a
    plausible luma table and overwrote the before/after contact sheet. A typo that looks
    like a successful launch is the worst shape of failure for a six-hour render — the
    missing frames are discovered at the end.
    """

    def test_each_real_stage_maps_to_its_function(self):
        for name, fn in (("stash", R.stash), ("render", R.render), ("qc", R.qc),
                         ("assemble", R.assemble), ("gate", R.gate), ("finish", R.finish)):
            self.assertIs(R.stage_callable(name), fn, name)

    def test_report_is_an_alias_for_qc(self):
        self.assertIs(R.stage_callable("report"), R.qc)

    def test_an_unknown_stage_is_an_error_that_names_the_valid_ones(self):
        with self.assertRaises(SystemExit) as ctx:
            R.stage_callable("renedr")
        message = str(ctx.exception)
        self.assertIn("renedr", message)
        self.assertIn("render", message)

    def test_a_help_probe_does_not_run_a_stage(self):
        for probe in ("--help", "-h", ""):
            with self.assertRaises(SystemExit, msg=repr(probe)):
                R.stage_callable(probe)


class SteppedClock:
    """A `time` module whose `time()` advances a fixed step per call, for wait-loop tests."""

    def __init__(self, step):
        self.step = step
        self.now = 1_700_000_000.0

    def time(self):
        self.now += self.step
        return self.now

    def __getattr__(self, name):
        return getattr(__import__("time"), name)


class FinishHarness:
    """`finish()` against a faked Blender and faked liveness: no GPU, no real processes.

    Same reason as Harness above — the failure it guards is two Blenders writing one frame
    directory, and that cannot be rehearsed on the real rollout.
    """

    def __init__(self, tmp, alive=(), beats=(), status="running", exits=None,
                 frames=None, clock=0.0, host=None):
        self.tmp = Path(tmp)
        self.beats = list(beats)
        self.alive = list(alive)
        self.frames = None if frames is None else list(frames)  # R.frames_written() returns
        self.clock = clock                # seconds R.time.time() advances per call
        self.status = status
        self.host = host                  # the machine the preflight guard probes
        self.rendered = []      # beat args passed to Blender, with the queue still live
        self.counts = {"qc": 0, "assemble": 0, "gate": 0, "dist": 0}
        self.exits = dict(exits or {})   # per-stage exit codes, 0 unless stated

    def __enter__(self):
        # capture before any patch: a leaked tmp path in R.BEATS corrupts every later test
        self._orig = (R.BEATS, R.QC, R.STATE, R._alive, R._sleep, R.run_blender,
                      R.qc, R.assemble, R.gate, R.dist, R.beat_names, R.frames_written,
                      R.time, R.preflight_host)
        qc = self.tmp / "qc"
        qc.mkdir(parents=True, exist_ok=True)
        beats = self.tmp / "3d"
        beats.mkdir(parents=True, exist_ok=True)
        for name in self.beats:
            (beats / f"{name}.mp4").write_bytes(b"\0")
        R.BEATS, R.QC, R.STATE = beats, qc, qc / "rollout-render.json"
        R.STATE.write_text(json.dumps({"status": self.status, "pid": 4242,
                                       "beats": sorted(self.beats)}), encoding="utf-8")

        def alive(pid):
            return self.alive.pop(0) if self.alive else False

        def run_blender(args, log_path, timeout=None):
            # whatever of the poll queue is still True is a Blender the driver thinks is dead
            self.rendered.append((args, sum(1 for a in self.alive if a)))
            return 0, 60.0

        R._alive = alive
        R._sleep = lambda s: None
        R.run_blender = run_blender
        # Frames are counted from the harness, never from disk: the wait loop is being tested
        # for how it reacts to a sequence, not for what a real rollout happens to have written.
        seq = list(self.frames) if self.frames is not None else [0]
        R.frames_written = lambda: seq.pop(0) if len(seq) > 1 else seq[0]
        R.time = SteppedClock(self.clock)
        def stage(name):
            def run():
                self.counts[name] += 1
                return self.exits.get(name, 0)
            return run

        for name in ("qc", "assemble", "gate", "dist"):
            setattr(R, name, stage(name))
        R.beat_names = lambda: sorted(self.beats)
        R.preflight_host = lambda: self.host if self.host is not None else healthy_host(ROOT)
        return self

    def __exit__(self, *exc):
        (R.BEATS, R.QC, R.STATE, R._alive, R._sleep, R.run_blender,
         R.qc, R.assemble, R.gate, R.dist, R.beat_names,
         R.frames_written, R.time, R.preflight_host) = self._orig
        return False

    @property
    def state(self):
        return json.loads(R.STATE.read_text(encoding="utf-8"))


class TestFinishQueue(unittest.TestCase):
    """The finish queue re-renders the beats that changed during the rollout. It must not
    start a second Blender, and it must not assemble an episode with holes in it.

    Seen coming, measured 2026-11-12 05:48: the rollout runs at 1.844 s/frame over 12480
    frames = 6.4 h, and `render()` gives up at its own 6 h limit and writes status "timeout"
    with Blender still putting frames down. `finish()` keyed its wait on `status ==
    "running"`, so it would have fallen straight through that window and re-rendered into
    the same `frame-####.png` directories — and then assembled whatever beats existed.
    """

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="finish-")

    def test_it_waits_for_the_process_not_for_the_status_string(self):
        with FinishHarness(self.tmp, alive=[True, True, False],
                           beats=["a", "b"], status="timeout") as h:
            self.assertEqual(R.finish(beats=("a",)), 0)
            self.assertEqual(len(h.rendered), 1)
            self.assertEqual(h.rendered[0][1], 0,
                             "re-rendered while a Blender was still live")

    def test_a_rollout_with_missing_beats_is_refused_not_assembled(self):
        with FinishHarness(self.tmp, alive=[False], beats=["a"], status="failed") as h:
            R.BEATS.joinpath("a.mp4").unlink()
            self.assertEqual(R.finish(beats=("a",)), 1)
            self.assertEqual(h.rendered, [], "re-rendered a beat the rollout never finished")
            self.assertEqual(h.counts["qc"], 0)
            self.assertEqual(h.counts["assemble"], 0,
                             "assembled an episode with a hole in it")
            self.assertEqual(h.counts["gate"], 0)
            self.assertEqual(h.state["missing"], ["a"])

    def test_a_complete_rollout_re_renders_the_named_beats_then_assembles(self):
        with FinishHarness(self.tmp, alive=[False], beats=["a", "b"]) as h:
            self.assertEqual(R.finish(beats=("b",)), 0)
            self.assertEqual([args for args, _ in h.rendered], [["--only", "b"]])
            self.assertEqual(h.counts["qc"], 1)
            self.assertEqual(h.counts["assemble"], 1)
            self.assertEqual(h.counts["gate"], 1, "the queue stopped before the contract gate")
            self.assertEqual(h.state["status"], "finished")
            self.assertEqual(h.state["re_rendered"], ["b"])

    def test_a_luma_qc_failure_still_reaches_the_contract_gate(self):
        """A black beat is a finding, not a reason to skip the verdict that defines done.

        D-036 rule 3: the chain ends at the gate. `qc()` returns 1 for a black or absent
        still, and chaining it into the gate's guard stopped the run one step early — leaving
        an mp4 and no `canvas_resolution` / `music_bed_missing` verdict, which is the failure
        #125 was written to catch.
        """
        with FinishHarness(self.tmp, alive=[False], beats=["a"], exits={"qc": 1}) as h:
            self.assertEqual(R.finish(beats=("a",)), 1,
                             "the luma finding was swallowed")
            self.assertEqual(h.counts["gate"], 1, "a QC failure skipped the contract gate")

    def test_the_state_names_the_stage_that_set_each_exit_code(self):
        """`gate_exit` has to be the gate's own code, and absent when the gate never ran.

        `write_state` merges, so a field left out of this run keeps the previous run's value:
        recording `gate_exit=rc` unconditionally reported an assemble failure as though the
        contract had judged the episode and said no.
        """
        with FinishHarness(self.tmp, alive=[False], beats=["a"],
                           exits={"qc": 1, "gate": 2}) as h:
            self.assertEqual(R.finish(beats=("a",)), 2)
            self.assertEqual((h.state["qc_exit"], h.state["gate_exit"]), (1, 2))
        with FinishHarness(self.tmp, alive=[False], beats=["a"],
                           exits={"assemble": 1}) as h:
            self.assertEqual(R.finish(beats=("a",)), 1)
            self.assertEqual(h.counts["gate"], 0, "gated a master that was never assembled")
            self.assertIsNone(h.state["gate_exit"], "a stale gate verdict on a failed run")

    def test_only_a_clean_run_publishes_the_upload_artifact(self):
        """`dist/` is what a human clicks to upload, so a refused run must not refresh it.

        The gate is the verdict; publishing is the reward for passing it. Copying unconditionally
        would put a master with a black beat inside it under the deliverable's name — the same
        class of silence D-036 exists to stop, one step further along.
        """
        with FinishHarness(self.tmp, alive=[False], beats=["a"]) as h:
            self.assertEqual(R.finish(beats=("a",)), 0)
            self.assertEqual(h.counts["dist"], 1, "a clean run never published the artifact")
            self.assertEqual(h.state["dist_exit"], 0)

        with FinishHarness(self.tmp, alive=[False], beats=["a"], exits={"gate": 1}) as h:
            self.assertEqual(R.finish(beats=("a",)), 1)
            self.assertEqual(h.counts["dist"], 0, "published a master the contract gate refused")
            self.assertIsNone(h.state["dist_exit"], "a stale publish verdict on a refused run")

        with FinishHarness(self.tmp, alive=[False], beats=["a"], exits={"qc": 1}) as h:
            self.assertEqual(R.finish(beats=("a",)), 1)
            self.assertEqual(h.counts["dist"], 0, "published a master with a black beat in it")

    def test_a_failing_publish_reports_itself_and_is_not_the_gate_s_verdict(self):
        with FinishHarness(self.tmp, alive=[False], beats=["a"], exits={"dist": 1}) as h:
            self.assertEqual(R.finish(beats=("a",)), 1, "a broken copy reported clean")
            self.assertEqual(h.state["gate_exit"], 0, "the gate's pass was overwritten")
            self.assertEqual(h.state["dist_exit"], 1)


class TestFinishWaitsOnProgressNotOnAClock(unittest.TestCase):
    """The queue has to give up on a stalled render, not on a healthy one that runs long.

    Seen coming, measured 2026-11-12 17:14: `finish()` reached its 9 h ceiling with Blender
    alive and 4121 frames still owed — at the rate frames were landing at that moment, 1.6 h
    of work remained. It returned 2 and left nobody to re-render the stipple beats, QC,
    assemble or gate the episode. A wall-clock ceiling cannot tell that apart from a wedged
    render, because a render that keeps writing frames is never the failure being guarded.
    """

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="finish-progress-")

    def test_a_render_that_keeps_landing_frames_is_not_abandoned(self):
        with FinishHarness(self.tmp, alive=[True] * 12 + [False], beats=["a"],
                           frames=list(range(1000, 1000 + 13 * 100, 100)), clock=3600.0) as h:
            self.assertEqual(R.finish(beats=("a",)), 0,
                             "the queue gave up on a render that was still writing frames")
            self.assertEqual(h.counts["gate"], 1, "the chain stopped before the contract gate")

    def test_a_render_that_stops_writing_frames_is_given_up_on(self):
        with FinishHarness(self.tmp, alive=[True] * 40, beats=["a"],
                           frames=[500] * 40, clock=900.0) as h:
            self.assertEqual(R.finish(beats=("a",)), 2,
                             "waited on a wedged render forever instead of saying so")
            self.assertEqual(h.counts["qc"], 0, "re-rendered beats while a Blender was live")


class TestFinishBeatsFromArgv(unittest.TestCase):
    """The finish stage has to accept its beat list from the command line.

    `finish(beats=("sls-launch",))` was only ever callable with its default, because
    `__main__` resolved the stage and called it with no arguments. So the one thing the
    queue exists for — re-rendering whichever beats changed mid-rollout — could not be
    asked of it, and an unattended `finish` would have re-rendered `sls-launch` for the
    third time and skipped the three regolith beats #123 is fixing.

    `beats_from` receives the words after the stage, not the whole argv: the episode is a
    `--episode` flag and the driver's own name is nobody's beat.
    """

    def test_a_comma_list_becomes_a_beat_tuple(self):
        self.assertEqual(R.beats_from(["lunar-flyby,earth-rise"]),
                         ("lunar-flyby", "earth-rise"))

    def test_a_bare_finish_stage_yields_nothing_so_the_default_stands(self):
        self.assertEqual(R.beats_from([]), ())

    def test_empty_fields_from_a_stray_comma_are_dropped(self):
        self.assertEqual(R.beats_from(["gateway,", ",tli-burn"]),
                         ("gateway", "tli-burn"))


class TestGateStep(unittest.TestCase):
    """The finish queue has to end at the contract gate, not at an mp4 that exists.

    PRODUCTION-GUIDE section 8 says the episode is finished when `qc_episode.py` reports no
    errors — an episode rendered at the wrong canvas exits 0 with a clean log, which is the
    exact failure #125 was written to catch. Stopping the unattended queue at `assemble`
    would leave that judgement to whoever happens to be awake.
    """

    class FakeSubprocess:
        STDOUT = subprocess.STDOUT

        def __init__(self, returncode):
            self.returncode = returncode
            self.cmd = None

        def run(self, cmd, **kw):
            self.cmd = cmd
            return type("P", (), {"returncode": self.returncode})()

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp(prefix="gate-"))
        self.episode = self.tmp / "episode-gate"
        self.qc = self.tmp / "qc"
        self.qc.mkdir(parents=True, exist_ok=True)
        self._orig = (R.EPISODE, R.QC, R.MASTER, R.subprocess)

    def tearDown(self):
        (R.EPISODE, R.QC, R.MASTER, R.subprocess) = self._orig

    def _run(self, returncode):
        fake = TestGateStep.FakeSubprocess(returncode)
        R.EPISODE = self.episode
        R.QC = self.qc
        R.MASTER = self.tmp / "episode.mp4"
        R.MASTER.write_bytes(b"\0")
        R.subprocess = fake
        code = R.gate()
        return code, fake.cmd

    def test_it_runs_the_command_the_guide_documents(self):
        code, cmd = self._run(0)
        self.assertEqual(code, 0)
        self.assertEqual(Path(cmd[1]).name, "qc_episode.py")
        self.assertIn("--master", cmd)
        self.assertEqual(cmd[cmd.index("--master") + 1], str(R.MASTER))
        self.assertIn("--episode", cmd)
        self.assertEqual(cmd[cmd.index("--episode") + 1], str(self.episode),
                         "the gate judged an episode other than the one being rendered")
        self.assertEqual(Path(cmd[cmd.index("--json") + 1]).parent, self.qc)

    def test_a_breaching_gate_exits_nonzero_and_is_not_swallowed(self):
        code, _ = self._run(1)
        self.assertEqual(code, 1)


class TestEpisodeSelection(unittest.TestCase):
    """The driver has to be told which film it is rendering, and never guess one.

    Nine paths used to be pinned at `work/episode-artemis-ii` inside this module, so an
    unattended rollout for a second episode spent the night re-rendering the first one and
    then assembled that film's beats. The paths are now read off `--episode` at startup and
    nothing may default them: at the measured 1.84 s/frame, a rollout that guessed the
    episode is six GPU hours spent producing a master nobody asked for.

    The same argument reaches one step further, which is what #147 settles here: *which builder
    script* renders the layer, *which luma baseline* the QC compares against and *which beat* a
    `finish` re-cuts by default were the driver's own three literals. A queue that guesses a
    builder spends the night rendering last week's film with this week's shot table, which is
    worse than guessing the directory — the frames come back at the right size and the wrong
    shape. All three are episode authoring now, and they live next to the shot table.
    """

    PATHS = ("EPISODE", "BEATS", "ARCHIVE", "SEGMENTS", "QC", "STASH", "MASTER", "DIST",
             "STATE", "SHOT_LENGTHS", "SCRIPT", "BASELINE", "FINISH_BEATS")

    # An authored rollout: a builder that exists, a baseline, and the hero beat of a film
    # nobody has ever rendered here.
    ROLLOUT = {"builder": "tools/blender/vostok_beats.py",
               "baseline": "work/rollout-vostok/baseline-luma.txt",
               "finish_beats": ["gagarin-ascent"]}

    def document(self, rollout=ROLLOUT):
        body = {"slug": "episode-vostok", "title": "Vostok", "workflow_version": 3}
        if rollout is not None:
            body["rollout"] = rollout
        (self.episode / "episode.json").write_text(json.dumps(body), encoding="utf-8")

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp(prefix="select-"))
        self.episode = self.tmp / "work" / "episode-vostok"
        self.episode.mkdir(parents=True)
        self.document()
        builder = self.tmp / self.ROLLOUT["builder"]
        builder.parent.mkdir(parents=True)
        builder.write_text("# the vostok builder\n", encoding="utf-8")
        (self.episode / "shots.json").write_text(
            json.dumps({"u001": {"kind": "archive", "name": "tape"}}), encoding="utf-8")
        self._orig = {name: getattr(R, name) for name in self.PATHS}
        self._orig_subprocess = R.subprocess

    def tearDown(self):
        for name, value in self._orig.items():
            setattr(R, name, value)
        R.subprocess = self._orig_subprocess

    def test_every_path_is_read_off_the_episode_named_on_the_command_line(self):
        ep = R.select_episode("episode-vostok", root=self.tmp)
        expected = {
            "EPISODE": ep,
            "BEATS": ep / "renders" / "3d",
            "ARCHIVE": ep / "renders" / "archive",
            "SEGMENTS": ep / "segments",
            "QC": ep / "qc",
            "STASH": ep / "_pre-720-stash",
            "MASTER": ep / "episode-vostok.mp4",
            "DIST": ep / "dist" / "episode-vostok-broadcast.mp4",
            "STATE": ep / "qc" / "rollout-render.json",
            "SHOT_LENGTHS": ep / "shot_lengths.json",
            "SCRIPT": self.tmp / self.ROLLOUT["builder"],
            "BASELINE": self.tmp / self.ROLLOUT["baseline"],
            "FINISH_BEATS": ("gagarin-ascent",),
        }
        self.assertEqual(ep, self.episode)
        for name in self.PATHS:
            with self.subTest(name):
                self.assertEqual(getattr(R, name), expected[name],
                                 f"{name} still describes a film other than the one selected")

    def test_the_archive_directory_is_the_contract_path_not_a_renders_convention(self):
        """The archival layer's directory is style data with a `why` behind it; the queue that
        types `renders/archive` itself keeps looking in the old place after the rename that moved
        the film."""
        from workflow.archive import paths
        declared = paths(R.CONTRACT)["render_dir"]
        renamed = json.loads(json.dumps(R.CONTRACT))
        renamed["archive"]["paths"]["render_dir"] = "renders/archive-footage"
        original = R.CONTRACT
        try:
            R.CONTRACT = renamed
            R.select_episode("episode-vostok", root=self.tmp)
            self.assertEqual(R.ARCHIVE, self.episode / "renders" / "archive-footage")
        finally:
            R.CONTRACT = original
        R.select_episode("episode-vostok", root=self.tmp)
        self.assertEqual(R.ARCHIVE, self.episode / declared)

    def test_an_episode_that_declares_no_builder_is_refused_naming_file_and_key(self):
        """The refusal is the whole point: defaulting to last week's builder is how an unattended
        queue renders a film that is not the one its shot table describes."""
        self.document(rollout=None)
        with self.assertRaises(ValueError) as caught:
            R.select_episode("episode-vostok", root=self.tmp)
        message = str(caught.exception)
        self.assertIn("episode.json", message)
        self.assertIn("rollout", message)
        self.assertIn("builder", message)

    def test_a_partial_rollout_block_names_the_keys_that_are_missing(self):
        self.document(rollout={"builder": self.ROLLOUT["builder"]})
        with self.assertRaises(ValueError) as caught:
            R.select_episode("episode-vostok", root=self.tmp)
        message = str(caught.exception)
        self.assertIn("baseline", message)
        self.assertIn("finish_beats", message)

    def test_a_builder_that_is_not_on_disk_is_refused(self):
        """A missing script is a missing input, and D-043 says it stops the run: Blender would
        otherwise exit non-zero per beat against a file that was never there."""
        (self.tmp / self.ROLLOUT["builder"]).unlink()
        with self.assertRaises(ValueError) as caught:
            R.select_episode("episode-vostok", root=self.tmp)
        self.assertIn("vostok_beats.py", str(caught.exception))

    def test_the_ingest_stage_delegates_to_the_assembler(self):
        """One ffmpeg recipe for the archival layer. Duplicating it here is how the queue and the
        cutter start producing different clips from the same record."""
        class FakeAssembler:
            def __init__(self):
                self.calls = []

            def load_manifest(self, episode):
                return {"sampleRate": 24000, "totalSamples": 48000,
                        "utterances": [{"id": "u001", "file": "u001.wav", "samples": 48000}]}

            def ingest_archive(self, episode, manifest, shot_map, contract, root=None):
                self.calls.append({"episode": episode, "manifest": manifest,
                                   "shot_map": shot_map, "contract": contract, "root": root})
                return [episode / "renders" / "archive" / "tape.mp4"]

        fake = FakeAssembler()
        original = (R.assemble_episode, R.preflight_host)
        R.assemble_episode, R.preflight_host = fake, lambda: healthy_host(ROOT)
        try:
            R.select_episode("episode-vostok", root=self.tmp)
            self.assertEqual(R.ingest(), 0)
        finally:
            R.assemble_episode, R.preflight_host = original
        self.assertEqual(len(fake.calls), 1)
        call = fake.calls[0]
        self.assertEqual(call["episode"], self.episode)
        self.assertEqual(call["shot_map"], {"u001": ("archive", "tape")})
        self.assertEqual(call["root"], ROOT)

    def test_the_ingest_stage_refuses_before_it_encodes(self):
        """Same rule as the render stage's guard: the preflight runs before any ffmpeg process
        exists, because an archival ingest over a moved binary dies in the middle of the layer."""
        class RefusingAssembler:
            called = False

            def load_manifest(self, episode):
                RefusingAssembler.called = True
                return {}

            def ingest_archive(self, *a, **kw):
                RefusingAssembler.called = True
                return []

        original = (R.assemble_episode, R.preflight_host)
        R.assemble_episode, R.preflight_host = RefusingAssembler(), \
            lambda: healthy_host(ROOT, missing_executables=("ffmpeg",))
        try:
            R.select_episode("episode-vostok", root=self.tmp)
            self.assertEqual(REFUSED, R.ingest())
            self.assertFalse(RefusingAssembler.called,
                             "the ingest ran on a machine the preflight had already refused")
        finally:
            R.assemble_episode, R.preflight_host = original

    def test_ingest_is_a_stage_the_queue_knows(self):
        self.assertIs(R.stage_callable("ingest"), R.ingest)

    def test_the_assemble_step_hands_the_assembler_the_same_episode(self):
        """The renderer and the assembler must mean the same film or the master is a hybrid."""
        R.select_episode("episode-vostok", root=self.tmp)
        R.QC.mkdir(parents=True, exist_ok=True)
        fake = TestGateStep.FakeSubprocess(0)
        R.subprocess = fake
        self.assertEqual(R.assemble(), 0)
        self.assertEqual(Path(fake.cmd[1]).name, "assemble_episode.py")
        self.assertEqual(fake.cmd[fake.cmd.index("--episode") + 1], str(self.episode))

    def test_an_invocation_without_an_episode_is_refused_before_any_stage_runs(self):
        """`--episode` is required, so a bare `render` cannot quietly pick last week's film."""
        import contextlib
        import io
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as caught:
                R.main(["render"])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("--episode", stderr.getvalue())


class TestDistPublish(unittest.TestCase):
    """`dist/` is the file a human later uploads, so it may only ever hold a gated master.

    Measured 2026-11-12 06:30: `dist/episode-artemis-ii-broadcast.mp4` was a 02:06 encode
    (md5 `b443a5…`) while the master the gate judges was `c7213a…` — a stale artifact wearing
    the deliverable's exact name, kept by hand, and nothing in the repo could tell the
    difference. The upload click was two renders behind.
    """

    def setUp(self):
        import hashlib
        import tempfile
        self.hashlib = hashlib
        self._orig = (R.MASTER, R.DIST, R.shutil)
        self.tmp = Path(tempfile.mkdtemp(prefix="dist-"))
        R.MASTER = self.tmp / "episode-artemis-ii.mp4"
        R.DIST = self.tmp / "dist" / "episode-artemis-ii-broadcast.mp4"

    def tearDown(self):
        R.MASTER, R.DIST, R.shutil = self._orig

    def test_it_copies_the_master_byte_for_byte_instead_of_re_encoding(self):
        """PRODUCTION-GUIDE section 7: dist is a copy, not a second x264 pass."""
        R.MASTER.write_bytes(b"ftyp" * 4096)
        self.assertEqual(R.dist(), 0)
        self.assertEqual(R.DIST.read_bytes(), R.MASTER.read_bytes())

    def test_a_stale_artifact_with_the_same_name_is_replaced(self):
        R.MASTER.write_bytes(b"new master")
        R.DIST.parent.mkdir(parents=True, exist_ok=True)
        R.DIST.write_bytes(b"a master from two renders ago")
        self.assertEqual(R.dist(), 0)
        self.assertEqual(R.DIST.read_bytes(), b"new master")

    def test_a_missing_master_is_refused_rather_than_published_as_nothing(self):
        self.assertEqual(R.dist(), 1)
        self.assertFalse(R.DIST.exists(), "created an empty deliverable")

    def test_a_truncated_copy_never_lands_under_the_deliverable_name(self):
        """The digest check is the point, so it gets tested by breaking the copy.

        Fault injected at the I/O boundary, which is the only place a half-written 340 MB
        file can come from: a copy that dies mid-stream must leave the old artifact alone and
        exit non-zero, not leave a truncated mp4 that uploads as a broken episode.
        """
        class Truncating:
            @staticmethod
            def copyfile(src, dst):
                Path(dst).write_bytes(Path(src).read_bytes()[:4])

        R.MASTER.write_bytes(b"ftyp" * 4096)
        R.shutil = Truncating
        self.assertEqual(R.dist(), 1, "published a master whose copy did not match")
        self.assertFalse(R.DIST.exists())
        self.assertFalse(R.DIST.with_suffix(".part").exists(), "left the partial behind")


class TestTheModuleTheReRenderLoads(unittest.TestCase):
    """`artemis_beats.py` is handed to Blender by the queue, hours after anyone last read it.

    Every fast guard over that file (`test_episode_canvas`) matches its *text*, so a module that
    no longer parses passes them all — and the first thing that notices is the unattended re-render
    stage, after the rollout it was supposed to protect. Parsing costs no GPU and no Blender, so
    say it here instead.
    """

    BEAT_MODULE = ROOT / "tools" / "blender" / "artemis_beats.py"

    @staticmethod
    def _syntax_error(source, name="<beat module>"):
        try:
            compile(source, name, "exec")
        except SyntaxError as exc:
            return exc
        return None

    def test_the_check_rejects_a_module_that_does_not_parse(self):
        """The control: without this, the guard below could be asserting nothing at all."""
        self.assertIsNotNone(self._syntax_error("def add_regolith_stipple(:\n    pass\n"))

    def test_the_beat_module_the_re_render_loads_compiles(self):
        error = self._syntax_error(self.BEAT_MODULE.read_text(encoding="utf-8"))
        self.assertIsNone(error, f"the re-render stage would die on: {error}")


class TestMotionPreflight(unittest.TestCase):
    """A rollout is the most expensive thing this repo does, so it has to start last.

    #140 put the machine's capabilities in a registry the workflow reads on every run — the
    user's «να τα διαβάζει κάθε φορά που τρέχει το workflow ώστε να είμαστε σίγουροι ότι θα
    λειτουργούν». The motion phase needs Blender *and* manim, and both have been absent on this
    box before (#138 audited it, #139 installed it). The failure mode is not an error line: it is
    a driver spawning a Blender that cannot find its executable, or 19 3D beats rendered and only
    then discovered unmakeable diagram beats.
    """

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="preflight-")

    def test_a_machine_without_blender_never_starts_a_render(self):
        host = healthy_host(ROOT, blender=False)
        with Harness(self.tmp, alive=[False], beats=["a"], host=host) as h:
            self.assertEqual(REFUSED, R.render())
            self.assertEqual(h.spawned, 0, "spawned a Blender the registry says is absent")

    def test_a_machine_without_manim_never_starts_a_render(self):
        """The diagram beats are part of what this stage owes, so its interpreter is checked too."""
        host = healthy_host(ROOT, missing_modules=["manim"])
        with Harness(self.tmp, alive=[False], beats=["a"], host=host) as h:
            self.assertEqual(REFUSED, R.render())
            self.assertEqual(h.spawned, 0, "started a rollout that cannot make half the shots")

    def test_an_absent_optional_capability_does_not_stop_the_render(self):
        """Only required capabilities refuse. `latex-for-mathtext` is optional, and no beat in
        this episode uses MathTex — a gate that blocks on optional work is a gate people route
        around."""
        host = healthy_host(ROOT, missing_executables=["xelatex", "pdflatex", "latex", "tectonic"])
        with Harness(self.tmp, alive=[False], beats=["a", "b"], host=host) as h:
            self.assertEqual(0, R.render())
            self.assertEqual(h.spawned, 1, "an unavailable optional capability blocked a rollout")

    def test_attaching_to_a_live_blender_is_never_refused(self):
        """The guard protects *starting* a render, not waiting one out.

        The frames are already paid for, and walking away would skip the state write that tells
        the next session whether the rollout finished — the exact guess this file exists to
        remove.
        """
        with Harness(self.tmp, alive=[True, False], beats=["a", "b"]) as h:
            self.assertEqual(0, R.render())
            state = h.state
            state.update(status="running", pid=4242)
            R.STATE.write_text(json.dumps(state), encoding="utf-8")
            h.alive = [True, False]
            h.host = healthy_host(ROOT, blender=False)
            self.assertEqual(0, R.render(), "abandoned a render that was already running")
            self.assertEqual(h.spawned, 1, "the attach path started a second Blender")

    def test_the_cost_probe_refuses_before_it_touches_blender(self):
        calls = []
        original = R.run_blender        # Harness does not own this global, so this test restores it
        try:
            R.run_blender = lambda args, log, timeout=None: (
                calls.append(args), (0, 1.0))[1]
            with Harness(self.tmp, alive=[False], beats=["a"],
                         host=healthy_host(ROOT, blender=False)):
                self.assertEqual(REFUSED, R.cost("a"))
                self.assertEqual(calls, [], "timed a beat on a machine with no Blender")
        finally:
            R.run_blender = original

    def test_the_finish_queue_refuses_before_it_re_renders(self):
        with FinishHarness(self.tmp, alive=[False], beats=["a", "b"],
                           host=healthy_host(ROOT, missing_modules=["manim"])) as h:
            self.assertEqual(REFUSED, R.finish(beats=("a",)))
            self.assertEqual(h.rendered, [], "re-rendered beats without the diagram toolchain")
            self.assertEqual(h.counts["qc"], 0, "judged frames the queue never made")


if __name__ == "__main__":
    unittest.main()
