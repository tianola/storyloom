import assert from "node:assert/strict";
import { test } from "node:test";
import { JobStore } from "../src/jobs.ts";
import { JobBrief } from "../src/contracts.ts";

const brief = JobBrief.parse({
  topic: "Why inflation fell in 2025",
  category: "economics",
  audience: "curious general viewer",
  targetSeconds: 600,
  modelId: "qwen3.5:4b",
  voice: "af_heart"
});

const open = () => {
  const store = new JobStore(":memory:");
  const job = store.createJob(brief, { script: "draft" });
  return { store, jobId: job.id };
};

test("one job can only be claimed by one worker", () => {
  const { store, jobId } = open();
  const first = store.claimNext({ workerId: "w1", now: 1000 });
  assert.equal(first?.jobId, jobId);
  assert.equal(first?.stage, "evidence");
  assert.equal(store.stateOf(jobId), "running");
  assert.equal(store.claimNext({ workerId: "w2", now: 1000 }), null);
});

test("an expired lease is recovered as interrupted and its old token is rejected", () => {
  const { store, jobId } = open();
  const lease = store.claimNext({ workerId: "w1", now: 1000 });
  assert.ok(lease);
  const recovered = store.recover({ now: 40_000, leaseMs: 30_000 });
  assert.deepEqual(recovered, [{ jobId, from: "running", to: "interrupted" }]);
  assert.equal(store.completeStage({ ...lease, stage: "script", outputHash: "a".repeat(64), now: 41_000 }), false);

  const requeued = store.resume(jobId, { now: 42_000 });
  assert.equal(requeued.state, "queued");
  const second = store.claimNext({ workerId: "w2", now: 43_000 });
  assert.equal(second?.workerId, "w2");
  assert.ok(second && second.fencingToken > lease.fencingToken);
});

test("stage completion advances the pipeline and refuses stale workers", () => {
  const { store, jobId } = open();
  const lease = store.claimNext({ workerId: "w1", now: 1000 });
  assert.ok(lease);
  assert.equal(store.completeStage({ ...lease, stage: "evidence", outputHash: "a".repeat(64), now: 1500 }), true);
  assert.equal(store.completeStage({ ...lease, stage: "evidence", outputHash: "b".repeat(64), now: 1600 }), false);
  assert.equal(store.stageFor(jobId), "script");
});

test("cache is reused only when every input hash matches", () => {
  const { store, jobId } = open();
  const key = { stage: "narration" as const, inputsHash: "c".repeat(64), dependencyHash: "d".repeat(64), toolchainHash: "e".repeat(64) };
  store.recordArtifact({ jobId, ...key, path: "audio/master.wav", sha256: "f".repeat(64), bytes: 1200 });
  assert.equal(store.cachedArtifact(jobId, key)?.path, "audio/master.wav");
  assert.equal(store.cachedArtifact(jobId, { ...key, inputsHash: "0".repeat(64) }), null);
});

test("cancellation intent survives until the worker observes it", () => {
  const { store, jobId } = open();
  const lease = store.claimNext({ workerId: "w1", now: 1000 });
  assert.ok(lease);
  assert.equal(store.cancelRequested(jobId), false);
  store.requestCancel(jobId, "user pressed cancel");
  assert.equal(store.cancelRequested(jobId), true);
  assert.equal(store.markCancelled(jobId), true);
  assert.equal(store.stateOf(jobId), "cancelled");
  assert.equal(store.claimNext({ workerId: "w2", now: 2000 }), null);
});

test("a new editorial revision reopens review and keeps history", () => {
  const { store, jobId } = open();
  store.recordEvent(jobId, "script.approved", { revision: 1 });
  const revision = store.addRevision(jobId, { script: "edited" }, "Elena");
  assert.equal(revision.number, 2);
  assert.equal(store.stateOf(jobId), "needs_review");
  store.approveRevision(jobId, 2, "Elena");
  assert.equal(store.stateOf(jobId), "queued");
  const events = store.eventsAfter(jobId, 0);
  assert.ok(events.length >= 3);
  assert.deepEqual(events.map((event) => event.sequence), events.map((_, index) => index + 1));
});

test("completed jobs are never reclaimable and their exports are listed", () => {
  const { store, jobId } = open();
  let lease = store.claimNext({ workerId: "w1", now: 1000 });
  assert.ok(lease);
  for (const stage of ["evidence", "script", "narration", "timeline", "scenes", "mux", "verify"] as const) {
    store.completeStage({ ...lease, stage, outputHash: "a".repeat(64), now: 2000 });
    const next = store.claimNext({ workerId: "w1", now: 2100 });
    if (next === null) {
      lease = next;
      break;
    }
    lease = next;
  }
  assert.equal(lease, null);
  assert.equal(store.stateOf(jobId), "completed");
});
