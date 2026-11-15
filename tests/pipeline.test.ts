import assert from "node:assert/strict";
import { test } from "node:test";
import { chaptersFromTimeline, narrationRequest, pausePolicy, provenanceManifest, timelineFromManifest } from "../src/pipeline.ts";
import { ScriptSchema } from "../src/writer.ts";
import type { DraftScript } from "../src/writer.ts";

const script: DraftScript = ScriptSchema.parse({
  schemaVersion: 1,
  title: "Why inflation fell",
  language: "en",
  claims: [{ id: "c1", text: "Inflation fell between 2022 and 2024.", evidence: [{ sourceId: "src1", locator: "series" }], material: true, review: "unreviewed" }],
  chapters: [
    {
      id: "ch1",
      heading: "The numbers",
      summary: "What happened to prices.",
      utterances: [
        {
          id: "u001", spokenText: "Worldwide inflation fell sharply after 2022.", captionText: "Inflation fell after 2022", claimIds: ["c1"],
          scene: { schemaVersion: 1, id: "s01", kind: "bar-chart", utteranceIds: ["u001"], claimIds: ["c1"], assetIds: [], beats: [{ at: 0, action: "reveal", target: "title" }], props: { title: "Inflation", unit: "% per year", series: [{ label: "2022", value: 8.1 }, { label: "2024", value: 5.1 }] } }
        },
        {
          id: "u002", spokenText: "The drop was roughly three percentage points.", captionText: "About 3 points lower", claimIds: ["c1"],
          scene: { schemaVersion: 1, id: "s02", kind: "bar-chart", utteranceIds: ["u002"], claimIds: ["c1"], assetIds: [], beats: [{ at: 0, action: "reveal", target: "title" }], props: { title: "Change", unit: "points", series: [{ label: "2022", value: 8.1 }, { label: "2024", value: 5.1 }] } }
        }
      ]
    },
    {
      id: "ch2",
      heading: "Why it happened",
      summary: "Borrowing costs moved demand.",
      utterances: [
        {
          id: "u003", spokenText: "Costlier borrowing slowed spending and price growth.", captionText: "Costlier borrowing slowed spending", claimIds: ["c1"],
          scene: { schemaVersion: 1, id: "s03", kind: "process", utteranceIds: ["u003"], claimIds: ["c1"], assetIds: [], beats: [{ at: 0, action: "reveal", target: "title" }], props: { title: "Rate to prices", steps: ["Rate", "Borrowing", "Demand", "Prices"] } }
        }
      ]
    }
  ]
});

const manifest = {
  sampleRate: 24000,
  voice: "af_heart",
  totalSamples: 36000,
  utterances: [
    { id: "u001", file: "u001.wav", text: "Worldwide inflation fell sharply after 2022.", samples: 12000, startSample: 0, endSample: 12000 },
    { id: "u002", file: "u002.wav", text: "The drop was roughly three percentage points.", samples: 12000, startSample: 12000, endSample: 24000 },
    { id: "u003", file: "u003.wav", text: "Costlier borrowing slowed spending and price growth.", samples: 12000, startSample: 24000, endSample: 36000 }
  ]
};

test("pause policy converts the documented silence seconds into whole samples", () => {
  assert.equal(pausePolicy({ withinChapter: true, sampleRate: 48000, frameRate: 30 }), 16800);
  assert.equal(pausePolicy({ withinChapter: false, sampleRate: 48000, frameRate: 30 }), 43200);
});

test("narration request lists every utterance once in document order", () => {
  const request = narrationRequest(script, { voice: "af_heart", speed: 1 });
  assert.deepEqual(request.utterances.map((item) => item.id), ["u001", "u002", "u003"]);
  assert.equal(request.utterances[0]?.text, "Worldwide inflation fell sharply after 2022.");
  assert.equal(request.voice, "af_heart");
  assert.equal(request.speed, 1);
});

test("timeline rescales 24k manifest samples to the master clock and adds pauses", () => {
  const WITHIN = 16800;
  const CHAPTER_END = 43200;
  const timeline = timelineFromManifest(manifest, script, { sampleRate: 48000, frameRate: 30 });
  assert.equal(timeline.utterances[0]?.samples, 24000);
  assert.equal(timeline.utterances[1]?.startSample, 24000 + WITHIN);
  assert.equal(timeline.utterances[2]?.startSample, 24000 * 2 + WITHIN + CHAPTER_END);
  assert.equal(timeline.utterances[2]?.pauseAfterSamples, 0);
});

test("a manifest that misses an utterance fails loudly", () => {
  assert.throws(() => timelineFromManifest({ ...manifest, utterances: manifest.utterances.slice(0, 2) }, script, { sampleRate: 48000, frameRate: 30 }), /missing narration for u003/);
});

test("chapters start at their first utterance", () => {
  const timeline = timelineFromManifest(manifest, script, { sampleRate: 48000, frameRate: 30 });
  assert.deepEqual(
    chaptersFromTimeline(timeline, script).map((chapter) => [chapter.id, Number(chapter.startSeconds.toFixed(3))]),
    [["ch1", 0], ["ch2", 2.25]]
  );
});

test("provenance manifest records models, hashes and rights", () => {
  const timeline = timelineFromManifest(manifest, script, { sampleRate: 48000, frameRate: 30 });
  const doc = provenanceManifest({
    job: { id: "job1", revision: 2, title: "Why inflation fell", category: "economics", targetSeconds: 30 },
    writer: { provider: "ollama", modelId: "qwen3.5:4b", digest: "sha256:abc", seed: 7 },
    narrator: { engine: "kokoro-onnx", version: "0.6.1", modelSha256: "a".repeat(64), voice: "af_heart", speed: 1 },
    renderer: { engine: "svg-deterministic", versions: { resvg: "0.4.x", ffmpeg: "9.0.2" }, toolchainHash: "b".repeat(64) },
    timeline,
    sourceIds: ["src1"],
    licenses: [{ id: "lic1", licenseId: "Apache-2.0", artifactHash: "c".repeat(64) }]
  });
  assert.equal(doc.schemaVersion, 1);
  assert.equal(doc.writer.modelId, "qwen3.5:4b");
  assert.deepEqual(doc.sourceIds, ["src1"]);
  assert.equal(doc.timeline.totalSamples, timeline.totalSamples);
  assert.equal(doc.timeline.masterDurationSeconds, timeline.masterDurationSeconds);
  assert.equal(doc.licenses[0]?.licenseId, "Apache-2.0");
});
