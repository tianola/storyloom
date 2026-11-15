import assert from "node:assert/strict";
import { test } from "node:test";
import { planMasterAudio } from "../src/audio.ts";

const base = {
  dir: "work/jobs/job1/narration",
  sourceRate: 24000,
  sampleRate: 48000,
  utterances: [
    { id: "u001", file: "u001.wav", samples: 1001, text: "First line." },
    { id: "u002", file: "u002.wav", samples: 2002, text: "Second line." }
  ],
  pausesAfter: { u001: 4800 }
};

test("master plan resamples to 48k and counts real samples", () => {
  const plan = planMasterAudio(base);
  assert.equal(plan.expectedSamples, 2 * 1001 + 4800 + 2 * 2002);
  assert.equal(plan.masterDurationSeconds, plan.expectedSamples / 48000);
  assert.equal(plan.inputs.length, 3);
  assert.deepEqual(plan.inputs[0], { path: "work/jobs/job1/narration/u001.wav", kind: "wav" });
  assert.equal(plan.inputs[1]?.kind, "silence");
  assert.equal(plan.inputs[1]?.seconds, 0.1);
});

test("filter graph resamples every voice file and concatenates in order", () => {
  const plan = planMasterAudio(base);
  assert.equal(
    plan.filter,
    "[0:a]aresample=48000[a0];[1:a]aresample=48000[a1];[2:a]aresample=48000[a2];[a0][a1][a2]concat=n=3:v=0:a=1[aout]"
  );
  for (const segment of plan.filter.split(";").filter((part) => part.includes("aresample"))) {
    const options = segment.match(/aresample=([^\[]*)/)?.[1] ?? "";
    assert.equal(options, "48000", `FFmpeg 9 rejects extra aresample options: ${options}`);
  }
});

test("args pin pcm output into a temporary file", () => {
  const plan = planMasterAudio(base);
  const joined = plan.args.join(" ");
  assert.equal(plan.args[0], "ffmpeg");
  assert.match(joined, /-f lavfi -t 0\.1 -i anullsrc=r=48000:cl=mono/);
  assert.match(joined, /-map \[aout\] -ar 48000 -ac 1 -c:a pcm_s16le/);
  assert.equal(plan.args.at(-1), "work/jobs/job1/narration/master.wav.part");
  assert.equal(plan.args.slice(-3).join(" "), `-f wav ${plan.args.at(-1)}`, "a .part suffix hides the container from the format probe");
});

test("a non-integer resample ratio is refused rather than relabelled", () => {
  assert.throws(
    () => planMasterAudio({ ...base, sourceRate: 22050 }),
    /integer resample ratio/
  );
});

test("silence only between utterances and never after the last one", () => {
  const plan = planMasterAudio({ ...base, pausesAfter: { u001: 4800, u002: 9600 } });
  assert.equal(plan.inputs.filter((input) => input.kind === "silence").length, 1);
  assert.equal(plan.expectedSamples, 2 * 1001 + 4800 + 2 * 2002);
});
