import assert from "node:assert/strict";
import { test } from "node:test";
import { SceneSpec, TimedScene, LicenseEntry, Source, Claim } from "../src/contracts.ts";

test("scene spec accepts a process scene built only from validated data", () => {
  const parsed = SceneSpec.parse({
    schemaVersion: 1,
    id: "s01",
    kind: "process",
    utteranceIds: ["u001", "u002"],
    claimIds: ["c01"],
    assetIds: [],
    beats: [
      { at: 0, action: "reveal", target: "packet" },
      { at: 2.5, action: "move", target: "packet", to: "router" }
    ],
    props: { title: "How a packet reaches its destination", steps: ["App", "Router", "Server"] }
  });
  assert.equal(parsed.kind, "process");
});

test("scene spec rejects executable content and free-form urls", () => {
  const bad = [
    { kind: "process", props: { code: "eval(1)" } },
    { kind: "comparison", props: { title: "https://evil.example/x" } },
    { kind: "bar-chart", props: { title: "GDP", series: [{ label: "a", value: "3" }] } }
  ];
  for (const scene of bad) {
    assert.equal(SceneSpec.safeParse({ schemaVersion: 1, id: "s1", utteranceIds: ["u1"], claimIds: [], assetIds: [], beats: [], ...scene }).success, false);
  }
});

test("unknown scene kind is rejected", () => {
  assert.equal(
    SceneSpec.safeParse({
      schemaVersion: 1, id: "s1", kind: "slides", utteranceIds: ["u1"], claimIds: [], assetIds: [], beats: [], props: {}
    }).success,
    false
  );
});

test("timed scene derives frames from absolute sample boundaries", () => {
  const scene = {
    schemaVersion: 1, id: "s01", kind: "comparison", utteranceIds: ["u001", "u002"],
    claimIds: [], assetIds: [], beats: [{ at: 0, action: "reveal", target: "left" }], props: { title: "Inflation vs rates", left: "Inflation", right: "Rates", unit: "% per year", values: [{ label: "Inflation", value: 3.2 }, { label: "Rates", value: 4.5 }] }
  };
  const timed = TimedScene.parse({
    ...scene,
    startSample: 48000,
    endSampleExclusive: 150000,
    sampleRate: 48000,
    frameRate: 30
  });
  assert.equal(timed.startFrame, 30);
  assert.equal(timed.frameCount, 64);
  assert.equal(timed.beatFrames[0]?.frame, 30);
});

test("licenses require a known license id and reviewed rights", () => {
  assert.equal(LicenseEntry.safeParse({
    id: "l1", scope: "voice", origin: "kokoro", author: "Hexgrad", licenseId: "Apache-2.0",
    licenseUrl: "https://www.apache.org/licenses/LICENSE-2.0", licenseTextHash: "a".repeat(64),
    artifactHash: "b".repeat(64), attribution: "Kokoro-82M", modifications: "none", review: "approved"
  }).success, true);
  assert.equal(LicenseEntry.safeParse({
    id: "l2", scope: "music", origin: "youtube audio library", author: "unknown", licenseId: "unknown",
    licenseUrl: "https://example.com", licenseTextHash: "c".repeat(64), artifactHash: "d".repeat(64),
    attribution: "none", modifications: "none", review: "pending"
  }).success, false);
});

test("source records keep provenance and refuse urls without publisher", () => {
  assert.equal(Source.safeParse({
    id: "src1", url: "https://data.worldbank.org/indicator/FP.CPI.TOTL.ZG", title: "Inflation, annual %",
    publisher: "World Bank", retrievedAt: "2026-11-05T20:00:00.000Z", excerpt: "Annual CPI percentage change.",
    locator: "series 1990-2024", snapshotHash: "e".repeat(64)
  }).success, true);
  assert.equal(Source.safeParse({ id: "src2", title: "no origin" }).success, false);
});

test("claims reference existing source ids only", () => {
  const parsed = Claim.parse({
    id: "c1", text: "Global inflation peaked in 2022.", evidence: [{ sourceId: "src1", locator: "series 2022" }],
    review: "unreviewed"
  });
  assert.equal(parsed.evidence[0]?.sourceId, "src1");
  assert.equal(Claim.safeParse({ id: "c2", text: "x", evidence: [{ sourceId: "", locator: "y" }], review: "unreviewed" }).success, false);
});
test("adjacent scenes tile the frame axis exactly once", () => {
  const boundaries = [0, 100_001, 250_007, 400_000];
  const scenes = boundaries.slice(0, -1).map((startSample, index) =>
    TimedScene.parse({
      schemaVersion: 1, id: `s${index}`, kind: "process", utteranceIds: [`u${index}`], claimIds: [], assetIds: [],
      beats: [{ at: 0, action: "reveal", target: "title" }], props: { title: "Step", steps: ["A", "B"] },
      startSample, endSampleExclusive: boundaries[index + 1]!, sampleRate: 48_000, frameRate: 30
    })
  );
  scenes.forEach((scene, index) => {
    if (index === 0) return;
    const previous = scenes[index - 1]!;
    assert.equal(scene.startFrame, previous.startFrame + previous.frameCount, `s${index} overlaps or gaps s${index - 1}`);
  });
  const last = scenes.at(-1)!;
  assert.equal(last.startFrame + last.frameCount, Math.ceil(400_000 / 1600));
  assert.equal(scenes.reduce((total, scene) => total + scene.frameCount, 0), Math.ceil(400_000 / 1600));
});
