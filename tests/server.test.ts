import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { AddressInfo } from "node:net";
import { startServer } from "../src/server/api.ts";

const hash = "a".repeat(64);

const package_ = {
  job: { topic: "Test Topic", category: "science", audience: "general", targetSeconds: 60, modelId: "imported-reviewed-script", voice: "af_heart" },
  narration: { voice: "af_heart", speed: 1 },
  sources: [
    { id: "src1", url: "https://example.com/a", title: "A page", publisher: "Example", retrievedAt: "2026-11-06T01:11:14Z", excerpt: "A fact.", locator: "page", snapshotHash: hash }
  ],
  licenses: [
    { id: "lic1", scope: "model", origin: "kokoro", author: "Hexgrad", licenseId: "Apache-2.0", licenseUrl: "https://www.apache.org/licenses/LICENSE-2.0", licenseTextHash: hash, artifactHash: hash, attribution: "Kokoro", modifications: "none", review: "approved" }
  ],
  reviews: { c1: { reviewer: "Ana", reviewedAt: "2026-11-06T01:11:14Z" } },
  script: {
    schemaVersion: 1,
    title: "Test Topic",
    language: "en",
    claims: [{ id: "c1", text: "A statement that is long enough.", evidence: [{ sourceId: "src1", locator: "page" }], material: true, review: "approved" }],
    chapters: [
      {
        id: "ch1", heading: "Opening", summary: "What this covers.",
        utterances: [
          {
            id: "u001", spokenText: "A statement that is long enough.", captionText: "A statement", claimIds: ["c1"],
            scene: { schemaVersion: 1, id: "s01", kind: "process", utteranceIds: ["u001"], claimIds: ["c1"], assetIds: [], beats: [{ at: 0, action: "reveal", target: "title" }], props: { title: "Steps", steps: ["A", "B"] } }
          }
        ]
      }
    ]
  }
};

let root = "";
let base = "";
let server: ReturnType<typeof startServer>["server"];
let store: ReturnType<typeof startServer>["store"];

before(async () => {
  root = await mkdtemp(join(tmpdir(), "longform-studio-"));
  await mkdir(join(root, "topics"), { recursive: true });
  await mkdir(join(root, "public"), { recursive: true });
  await mkdir(join(root, "work", "test-topic", "exports"), { recursive: true });
  await writeFile(join(root, "topics", "test.project.json"), JSON.stringify(package_), "utf8");
  await writeFile(join(root, "public", "index.html"), "<h1>studio</h1>", "utf8");
  await writeFile(join(root, "work", "test-topic", "exports", "report.json"), "{\"ok\":true}", "utf8");
  await writeFile(join(root, "work", "test-topic", "secrets.txt"), "do not read me", "utf8");
  const started = startServer({ root, port: 0 });
  server = started.server;
  store = started.store;
  await new Promise<void>((resolveListen) => server.once("listening", () => resolveListen()));
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

after(async () => {
  await new Promise<void>((resolveClose) => server.close(() => resolveClose()));
  store.close();
  await rm(root, { recursive: true, force: true });
});

test("the studio refuses to bind outside loopback", () => {
  assert.throws(() => startServer({ root, host: "0.0.0.0", port: 0 }), /refusing to bind outside loopback/);
});

test("packages are listed with their real chapter and utterance counts", async () => {
  const response = await fetch(`${base}/api/episodes`);
  assert.equal(response.status, 200);
  const list = (await response.json()) as { name: string; topic: string; chapters: number; utterances: number }[];
  assert.equal(list.length, 1);
  assert.deepEqual([list[0]!.topic, list[0]!.chapters, list[0]!.utterances], ["Test Topic", 1, 1]);
});

test("an unknown package cannot be started", async () => {
  const response = await fetch(`${base}/api/jobs`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ episode: "ghost.project.json" }) });
  assert.equal(response.status, 404);
});

test("media serving stops at the work directory", async () => {
  const ok = await fetch(`${base}/media/test-topic/exports/report.json`);
  assert.equal(ok.status, 200);
  assert.match(ok.headers.get("content-type") ?? "", /application\/json/);
  assert.deepEqual(await ok.json(), { ok: true });
  for (const escape of ["/media/%2e%2e%2fsecrets.txt", "/media/test-topic%2f%2e%2e%2f%2e%2e/secrets.txt"]) {
    const blocked = await fetch(`${base}${escape}`);
    assert.equal(blocked.status, 403, `${escape} returned ${blocked.status}`);
  }
  // A literal or fully decoded .. is collapsed by the URL parser before the handler runs, so it never reaches media.
  for (const collapsed of ["/media/../secrets.txt", "/media/%2e%2e/secrets.txt", "/media/test-topic/../../secrets.txt"]) {
    const response = await fetch(`${base}${collapsed}`);
    assert.equal(response.status, 404, `${collapsed} returned ${response.status}`);
    assert.ok(!(await response.text()).includes("do not read me"), `${collapsed} leaked the file`);
  }
});

test("media honours byte ranges so the player can seek", async () => {
  const partial = await fetch(`${base}/media/test-topic/exports/report.json`, { headers: { range: "bytes=0-5" } });
  assert.equal(partial.status, 206);
  assert.equal(partial.headers.get("content-range"), "bytes 0-5/11");
  assert.equal((await partial.text()).length, 6);
  const beyond = await fetch(`${base}/media/test-topic/exports/report.json`, { headers: { range: "bytes=99999-" } });
  assert.equal(beyond.status, 416);
  assert.equal(beyond.headers.get("content-range"), "bytes */11");
});

test("the browser UI is served from the root", async () => {
  const response = await fetch(`${base}/`);
  assert.equal(response.status, 200);
  assert.match(await response.text(), /<h1>studio<\/h1>/);
  assert.equal((await fetch(`${base}/api/nothing`)).status, 404);
});

test("starting the studio releases a run whose lease expired with it", async () => {
  const root = await mkdtemp(join(tmpdir(), "studio-recover-"));
  await mkdir(join(root, "data"), { recursive: true });
  const { JobStore } = await import("../src/jobs.ts");
  const pre = new JobStore(join(root, "data", "jobs.db"));
  const created = pre.createJob({ topic: "Stale Run", category: "science", audience: "general", targetSeconds: 60, modelId: "m", voice: "af_heart" }, { package: "stale" });
  const lease = pre.claimNext({ workerId: "dead-worker", now: 1_000 });
  assert.ok(lease);
  pre.close();

  const started = startServer({ root, host: "127.0.0.1", port: 0 });
  try {
    assert.deepEqual(started.recovered.map((entry) => [entry.jobId, entry.to]), [[created.id, "interrupted"]]);
    const stored = started.store.listJobs().find((row) => row.id === created.id);
    assert.equal(stored?.state, "interrupted", "the database, not only the return value, must say interrupted");
  } finally {
    await new Promise<void>((resolve) => started.server.close(() => resolve()));
    started.store.close();
    await rm(root, { recursive: true, force: true });
  }
});
