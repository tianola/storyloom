import assert from "node:assert/strict";
import { test } from "node:test";

import { checkScriptClaims, ProjectSchema } from "../src/cli.ts";
import { withReviews } from "../src/evidence.ts";

const claim = { id: "c1", text: "Short blue light scatters more than long red light.", evidence: [{ sourceId: "src1", locator: "section: blue" }], material: true, review: "approved" };

const script = {
  schemaVersion: 1,
  title: "Why sunsets are red",
  language: "en",
  claims: [claim],
  chapters: [
    {
      id: "ch1",
      heading: "Scattering",
      summary: "Light scatters in the air.",
      utterances: [
        {
          id: "u001",
          spokenText: "Short blue light scatters first.",
          captionText: "Blue scatters first",
          claimIds: ["c1"],
          scene: {
            schemaVersion: 1, id: "s01", kind: "process", utteranceIds: ["u001"], claimIds: ["c1"], assetIds: [],
            beats: [{ at: 0, action: "reveal", target: "title" }], props: { title: "Scattering", steps: ["Sun", "Air", "Eye"] }
          }
        }
      ]
    }
  ]
};

function project(overrides: Record<string, unknown> = {}) {
  return {
    job: { topic: "Why sunsets are red", category: "science", audience: "curious general viewer", targetSeconds: 75, modelId: "imported-reviewed-script", voice: "af_heart" },
    narration: { voice: "af_heart", speed: 1 },
    sources: [
      {
        id: "src1", url: "https://spaceplace.nasa.gov/blue-sky/en/", title: "Why Is the Sky Blue?", publisher: "NASA Space Place",
        retrievedAt: "2026-11-06T01:11:14Z", excerpt: "Blue light is scattered more.", locator: "page", snapshotHash: "9".repeat(64)
      }
    ],
    licenses: [
      {
        id: "lic-model", scope: "model", origin: "kokoro-onnx", author: "Hexgrad", licenseId: "Apache-2.0",
        licenseUrl: "https://www.apache.org/licenses/LICENSE-2.0", licenseTextHash: "a".repeat(64), artifactHash: "b".repeat(64),
        attribution: "Kokoro-82M", modifications: "none", review: "approved"
      }
    ],
    reviews: { c1: { reviewer: "Qoder main agent", reviewedAt: "2026-11-06T01:11:14Z" } },
    script,
    ...overrides
  };
}

test("a project whose claims live only in the script parses", () => {
  assert.equal(ProjectSchema.safeParse(project()).success, true);
});

test("a second claim ledger at the top level is rejected outright", () => {
  const result = ProjectSchema.safeParse(project({ claims: [claim] }));
  assert.equal(result.success, false);
});

test("utterances and scenes must cite claims the script actually states", () => {
  const parsed = ProjectSchema.parse(project());
  assert.deepEqual(checkScriptClaims(parsed.script, parsed.script.claims.map((item) => item.id)), []);
  const broken = structuredClone(parsed.script);
  broken.chapters[0]!.utterances[0]!.claimIds = ["c9"];
  broken.chapters[0]!.utterances[0]!.scene.claimIds = ["c8"];
  assert.equal(checkScriptClaims(broken, ["c1"]).length, 2);
});

test("reviews attach to approved claims and orphan records are reported", () => {
  const merged = withReviews([claim], { c1: { reviewer: "Ana", reviewedAt: "2026-11-06T01:11:14Z" }, c7: { reviewer: "Ana", reviewedAt: "2026-11-06T01:11:14Z" } });
  assert.deepEqual(merged.claims, [{ ...claim, reviewer: "Ana", reviewedAt: "2026-11-06T01:11:14Z" }]);
  assert.deepEqual(merged.problems, [{ code: "orphan-review", claimId: "c7" }]);
});

test("an approved claim with no review record is a problem, not a silent pass", () => {
  const merged = withReviews([claim], {});
  assert.deepEqual(merged.problems, [{ code: "missing-review-record", claimId: "c1" }]);
  assert.equal(merged.claims[0], claim);
});
