import assert from "node:assert/strict";
import { test } from "node:test";
import { exportGate, validateClaims, validateEvidence, verifySnapshots } from "../src/evidence.ts";

const source = {
  id: "src1",
  url: "https://data.worldbank.org/indicator/FP.CPI.TOTL.ZG",
  title: "Inflation, consumer prices",
  publisher: "World Bank",
  retrievedAt: "2026-11-05T20:00:00.000Z",
  excerpt: "Annual inflation percentage change by economy.",
  locator: "series 1990-2024",
  snapshotHash: "a".repeat(64)
};

const claim = { id: "c1", text: "Inflation spiked in 2022.", evidence: [{ sourceId: "src1", locator: "2022" }], material: true, review: "unreviewed" as const };
const license = {
  id: "lic1", scope: "voice" as const, origin: "kokoro-onnx", author: "Hexgrad", licenseId: "Apache-2.0",
  licenseUrl: "https://www.apache.org/licenses/LICENSE-2.0", licenseTextHash: "b".repeat(64),
  artifactHash: "c".repeat(64), attribution: "Kokoro-82M", modifications: "none", review: "approved" as const
};

test("evidence packet requires at least one identified source", () => {
  assert.deepEqual(validateEvidence([]).problems, [
    { code: "no-sources", message: "An explainer needs at least one evidence source" }
  ]);
  assert.equal(validateEvidence([source]).problems.length, 0);
});

test("claims citing unknown sources are rejected rather than trusted", () => {
  const result = validateClaims([{ ...claim, evidence: [{ sourceId: "ghost", locator: "x" }] }], [source]);
  assert.deepEqual(result.problems, [{ code: "unknown-source", claimId: "c1", sourceId: "ghost" }]);
});

test("approved claims must record who approved and when", () => {
  const approved = { ...claim, review: "approved" };
  assert.equal(validateClaims([approved], [source]).problems[0]?.code, "missing-reviewer");
  assert.equal(validateClaims([{ ...approved, reviewer: "Elena", reviewedAt: "2026-11-05T21:00:00.000Z" }], [source]).problems.length, 0);
});

test("export is blocked while a material claim is unreviewed", () => {
  const gate = exportGate({ claims: [claim], licenses: [license] });
  assert.equal(gate.ready, false);
  assert.deepEqual(gate.blockers, [{ code: "unreviewed-material-claim", claimId: "c1" }]);
});

test("non-material nuance does not block export but is still reported", () => {
  const gate = exportGate({ claims: [{ ...claim, material: false }], licenses: [license] });
  assert.equal(gate.ready, true);
  assert.deepEqual(gate.warnings, [{ code: "unreviewed-claim", claimId: "c1" }]);
});

test("rejected claims and unapproved licenses block export", () => {
  const gate = exportGate({
    claims: [{ ...claim, review: "rejected", reviewer: "Elena", reviewedAt: "2026-11-05T21:00:00.000Z" }],
    licenses: [{ ...license, review: "pending" }]
  });
  assert.equal(gate.ready, false);
  assert.deepEqual(gate.blockers, [
    { code: "rejected-claim", claimId: "c1" },
    { code: "license-not-approved", licenseId: "lic1", review: "pending" }
  ]);
});

test("a local source must exist and match its recorded snapshot hash", async () => {
  const local = { ...source, url: "file:///F:/AI-PROJECTS/longform-explainer/tools/numbers.md", snapshotHash: "f".repeat(64) };
  const { sources } = validateEvidence([local]);
  assert.deepEqual(await verifySnapshots(sources, async () => {
    throw new Error("ENOENT");
  }), [{ code: "snapshot-missing", sourceId: "src1", message: "F:/AI-PROJECTS/longform-explainer/tools/numbers.md" }]);
  assert.deepEqual(await verifySnapshots(sources, async () => "a".repeat(64)), [
    { code: "snapshot-hash-mismatch", sourceId: "src1", message: `disk ${"a".repeat(64)}` }
  ]);
  assert.deepEqual(await verifySnapshots(sources, async () => "f".repeat(64)), []);
  assert.deepEqual(await verifySnapshots(validateEvidence([source]).sources, async () => "z".repeat(64)), [], "remote sources are not read from disk");
});
