import assert from "node:assert/strict";
import { test } from "node:test";
import { clamp01, easeInOutCubic, easeOutCubic, lerp, progress } from "../src/animation.ts";

test("progress clamps before and after the window", () => {
  assert.equal(progress(9, 10, 30), 0);
  assert.equal(progress(10, 10, 30), 0);
  assert.equal(progress(40, 10, 30), 1);
  assert.equal(progress(25, 10, 30), 0.5);
  assert.equal(Number(progress(20, 10, 30).toFixed(4)), 0.3333);
});

test("progress handles a zero-length window without dividing by zero", () => {
  assert.equal(progress(5, 5, 0), 1);
  assert.equal(progress(4, 5, 0), 0);
});

test("easing endpoints are exact and monotonic", () => {
  for (const ease of [easeOutCubic, easeInOutCubic]) {
    assert.equal(ease(0), 0);
    assert.equal(ease(1), 1);
    let previous = -1;
    for (let i = 0; i <= 20; i += 1) {
      const value = ease(i / 20);
      assert.ok(value >= previous, `monotonic at ${i}`);
      previous = value;
    }
  }
});

test("ease out front-loads motion and ease in-out is symmetric", () => {
  assert.ok(easeOutCubic(0.25) > 0.25);
  assert.ok(easeInOutCubic(0.25) < 0.25);
  assert.equal(Number(easeInOutCubic(0.5).toFixed(6)), 0.5);
});

test("lerp and clamp01", () => {
  assert.equal(lerp(10, 20, 0.25), 12.5);
  assert.equal(clamp01(2), 1);
  assert.equal(clamp01(-2), 0);
});
