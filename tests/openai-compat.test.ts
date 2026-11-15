import assert from "node:assert/strict";
import { test } from "node:test";
import { ChatError, quotaWaitSeconds } from "../src/openai-compat.ts";

// shaped like the gateway's own answer on 2026-11-06, with the timestamps made relative to the test
const quotaError = (resetAt: string): string =>
  `openrouter/nvidia/nemotron-3.5-super-vl:free failed after 1 attempts: 429: {"error":{"message":"[openrouter/nvidia/nemotron-3.5-super-vl:free] Quota preflight blocked for nvidia/nemotron-3.5-super-vl:free: 100%","retry_after":3070,"reset_at":"${resetAt}"}}`;

test("a shared free-tier block yields the wait until the reset window", () => {
  const seconds = quotaWaitSeconds(new ChatError(quotaError(new Date(Date.now() + 60_000).toISOString())));
  assert.ok(seconds !== null && seconds >= 55 && seconds <= 60, `${seconds}`);
});

test("a reset window already in the past means retry now", () => {
  assert.equal(quotaWaitSeconds(quotaError("1970-01-01T00:00:00.000Z")), 0);
});

test("retry_after is used when the gateway gives no reset timestamp", () => {
  assert.equal(quotaWaitSeconds('upstream failed: 429 {"error":{"message":"slow down","retry_after":120}}'), 120);
});

test("a wait longer than an hour is refused rather than parked on", () => {
  assert.equal(quotaWaitSeconds(`429 {"error":{"message":"quota","retry_after":${5 * 3600}}}`), 3600);
});

test("anything that is not a quota block waits nothing", () => {
  assert.equal(quotaWaitSeconds('failed after 1 attempts: 400 {"error":{"message":"Model is not available in the active live catalog","retry_after":300}}'), null);
  assert.equal(quotaWaitSeconds(new Error("empty-reply")), null);
});
