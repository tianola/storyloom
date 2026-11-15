import assert from "node:assert/strict";
import { test } from "node:test";
import { buildProjectPackage } from "../tools/make-project.ts";
import { ScriptSchema, type DraftScript } from "../src/writer.ts";
import type { JobBrief, Source } from "../src/contracts.ts";

const job: JobBrief = {
  topic: "Why people see colour differently",
  category: "science",
  audience: "curious general viewer",
  targetSeconds: 480,
  modelId: "qwen3.5:4b",
  voice: "af_heart"
};

const sources: Source[] = [
  {
    id: "src1",
    url: "https://spaceplace.nasa.gov/blue-sky/en/",
    title: "Why Is the Sky Blue?",
    publisher: "NASA Space Place",
    retrievedAt: "2026-11-06T01:11:14Z",
    excerpt: "Blue light is scattered more than the other colors because it travels as shorter, smaller waves.",
    locator: "section: why is the sky blue",
    snapshotHash: "9".repeat(64)
  }
];

const script: DraftScript = ScriptSchema.parse({
  schemaVersion: 1,
  title: "Why people see colour differently",
  language: "en",
  claims: [
    { id: "c1", text: "Shorter wavelengths scatter more strongly than longer ones.", evidence: [{ sourceId: "src1", locator: "section: why is the sky blue" }], material: true, review: "approved" },
    { id: "c2", text: "Sunlight is scattered by gases and particles in the atmosphere.", evidence: [{ sourceId: "src1", locator: "section: why is the sky blue" }], material: true, review: "approved" }
  ],
  chapters: [
    {
      id: "ch1",
      heading: "Short waves scatter",
      summary: "What happens to sunlight in the air.",
      utterances: [
        {
          id: "u001",
          spokenText: "Sunlight hits the air and the short blue waves scatter far more than the long red ones.",
          captionText: "Short waves scatter most",
          claimIds: ["c1"],
          scene: {
            schemaVersion: 1, id: "s01", kind: "bar-chart", utteranceIds: ["u001"], claimIds: ["c1"], assetIds: [],
            beats: [{ at: 0, action: "reveal", target: "title" }],
            props: { title: "Scattering by colour", unit: "relative", series: [{ label: "Blue", value: 5.5 }, { label: "Red", value: 1 }], axis: "category" }
          }
        }
      ]
    }
  ]
});

const licenses = [{
  id: "lic-model",
  scope: "model",
  origin: "kokoro-onnx v1.0 export of hexgrad/Kokoro-82M",
  author: "Hexgrad; thewh1teagle",
  licenseId: "Apache-2.0",
  licenseUrl: "https://www.apache.org/licenses/LICENSE-2.0",
  licenseTextHash: "c".repeat(64),
  artifactHash: "d".repeat(64),
  attribution: "Kokoro-82M speech model, Apache-2.0",
  modifications: "none",
  review: "approved"
}];

const reviewed = {
  c1: { reviewer: "Qoder main agent", reviewedAt: "2026-11-06T06:40:00Z" },
  c2: { reviewer: "Qoder main agent", reviewedAt: "2026-11-06T06:40:00Z" }
};

test("a fully reviewed draft becomes a package the project schema accepts", () => {
  const built = buildProjectPackage({ job, sources, script, reviews: reviewed, licenses, voice: job.voice, speed: 1 });
  const body = built as { reviews: Record<string, unknown>; script: DraftScript; narration: { voice: string } };
  assert.equal(Object.keys(body.reviews).length, 2);
  assert.equal(body.script.chapters[0]?.utterances.length, 1);
  assert.equal(body.narration.voice, "af_heart");
});

test("an unreviewed claim stops the package instead of shipping it", () => {
  const { c2: _dropped, ...oneReview } = reviewed;
  assert.throws(() => buildProjectPackage({ job, sources, script, reviews: oneReview, licenses, voice: job.voice, speed: 1 }), /claim c2 has no review record/);
});

test("a review record for a claim that does not exist is refused", () => {
  const withGhost = { ...reviewed, c9: { reviewer: "Qoder main agent", reviewedAt: "2026-11-06T06:40:00Z" } };
  assert.throws(() => buildProjectPackage({ job, sources, script, reviews: withGhost, licenses, voice: job.voice, speed: 1 }), /c9 matches no claim/);
});

test("a package without licenses is refused before the render", () => {
  assert.throws(() => buildProjectPackage({ job, sources, script, reviews: reviewed, licenses: [], voice: job.voice, speed: 1 }), /no license entries/);
});
