import assert from "node:assert/strict";
import { test } from "node:test";
import { assembleTimeline, makeSrt, sceneFramesFor } from "../src/timeline.ts";
import { TimedScene } from "../src/contracts.ts";
import { frameRange } from "../src/frames.ts";

const u = (id: string, samples: number, caption: string) => ({
  id, spokenText: caption, captionText: caption, claimIds: ["c1"], samples, pauseAfterSamples: 0
});

test("total frames come from total samples, not summed rounded durations", () => {
  const a = { id: "a", spokenText: "A.", captionText: "A.", claimIds: [], samples: 1001, pauseAfterSamples: 0 };
  const b = { id: "b", spokenText: "B.", captionText: "B.", claimIds: [], samples: 1001, pauseAfterSamples: 0 };
  const timeline = assembleTimeline([a, b], { sampleRate: 48000, frameRate: 30 });
  assert.equal(timeline.totalSamples, 2002);
  assert.equal(timeline.totalFrames, Math.ceil(2002 / 1600));
  assert.equal(timeline.utterances[1]?.startSample, 1001);
  assert.equal(timeline.utterances[1]?.endSampleExclusive, 2002);
});

test("pauses shift later utterances and the master length", () => {
  const first = { id: "a", spokenText: "A.", captionText: "A.", claimIds: [], samples: 4800, pauseAfterSamples: 2400 };
  const second = { id: "b", spokenText: "B.", captionText: "B.", claimIds: [], samples: 4800, pauseAfterSamples: 0 };
  const timeline = assembleTimeline([first, second], { sampleRate: 48000, frameRate: 30 });
  assert.equal(timeline.utterances[1]?.startSample, 7200);
  assert.equal(timeline.totalSamples, 12000);
  assert.equal(timeline.masterDurationSeconds, 0.25);
});

test("sampleAtFrame is the 48k to 30fps ratio", () => {
  const timeline = assembleTimeline([u("a", 3200, "A.")], { sampleRate: 48000, frameRate: 30 });
  assert.equal(timeline.sampleAtFrame(5), 8000);
  assert.equal(timeline.frameAtSample(8001), 6);
});

test("srt uses real utterance intervals and holds cues through deliberate pauses", () => {
  const first = { id: "a", spokenText: "Inflation measures price growth.", captionText: "Inflation measures price growth.", claimIds: [], samples: 96000, pauseAfterSamples: 4800 };
  const second = { id: "b", spokenText: "Rates are set by central banks.", captionText: "Rates: set by central banks.", claimIds: [], samples: 48000, pauseAfterSamples: 0 };
  const srt = makeSrt(assembleTimeline([first, second], { sampleRate: 48000, frameRate: 30 }));
  const lines = srt.trim().split(/\r?\n/);
  assert.equal(lines[0], "1");
  assert.equal(lines[1], "00:00:00,000 --> 00:00:02,100");
  assert.equal(lines[2], "Inflation measures price growth.");
  assert.equal(lines[3], "");
  assert.equal(lines[4], "2");
  assert.equal(lines[5], "00:00:02,100 --> 00:00:03,100");
  assert.equal(lines[6], "Rates: set by central banks.");
});

test("scene frames align to absolute boundaries rather than accumulated rounding", () => {
  const parts = [
    { sceneId: "s1", samples: 3301, pauseAfterSamples: 0 },
    { sceneId: "s2", samples: 3301, pauseAfterSamples: 0 },
    { sceneId: "s3", samples: 3301, pauseAfterSamples: 0 }
  ];
  const scenes = sceneFramesFor(parts, { sampleRate: 48000, frameRate: 30 });
  assert.equal(scenes[0]?.startFrame, 0);
  assert.equal(scenes[1]?.startFrame, Math.ceil(3301 / 1600));
  assert.equal(scenes[2]?.startFrame, Math.ceil(6602 / 1600));
  assert.equal(scenes[2]?.frameCount, Math.ceil(9903 / 1600) - Math.ceil(6602 / 1600));
});

test("empty narration cannot produce a timeline", () => {
  assert.throws(() => assembleTimeline([], { sampleRate: 48000, frameRate: 30 }), /at least one utterance/);
});

test("the frame rule has exactly one implementation across timeline, scenes and renderer", () => {
  const spans = [
    { sceneId: "s1", samples: 100_001 },
    { sceneId: "s2", samples: 250_007 },
    { sceneId: "s3", samples: 149_999 }
  ];
  const viaSpans = sceneFramesFor(spans, { sampleRate: 48_000, frameRate: 30 });
  const viaScenes = viaSpans.map((span) =>
    TimedScene.parse({
      schemaVersion: 1, id: span.sceneId, kind: "process", utteranceIds: ["u"], claimIds: [], assetIds: [],
      beats: [{ at: 0, action: "reveal", target: "title" }], props: { title: "T", steps: ["A", "B"] },
      startSample: span.startSample, endSampleExclusive: span.endSampleExclusive, sampleRate: 48_000, frameRate: 30
    })
  );
  viaScenes.forEach((scene, index) => {
    assert.equal(scene.startFrame, viaSpans[index]!.startFrame);
    assert.equal(scene.frameCount, viaSpans[index]!.frameCount);
    assert.deepEqual(frameRange(scene), { startFrame: scene.startFrame, endFrameExclusive: scene.startFrame + scene.frameCount, frameCount: scene.frameCount });
  });
  const total = viaScenes.reduce((sum, scene) => sum + scene.frameCount, 0);
  assert.equal(total, Math.ceil(spans.reduce((sum, span) => sum + span.samples, 0) / 1600));
});
