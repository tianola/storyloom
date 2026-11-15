import assert from "node:assert/strict";
import { test } from "node:test";
import { cpus } from "node:os";
import { createRasterPool, rasterizePool, rasterPoolSize } from "../src/raster.ts";
import { rasterize } from "../src/frames.ts";

function svgOf(color: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80"><rect width="120" height="80" fill="${color}"/></svg>`;
}

const SIZE = { width: 120, height: 80 };

test("the pool returns the same bytes as the sequential rasterizer, in order", async () => {
  const colors = ["#0b1118", "#152230", "#e8632b", "#2b8be8", "#7a3fd1"];
  const jobs = colors.map((color) => ({ svg: svgOf(color), ...SIZE }));
  const expected = colors.map((color) => rasterize(svgOf(color), SIZE));
  const got = await rasterizePool(jobs, { concurrency: 3 });
  assert.equal(got.length, expected.length);
  for (let index = 0; index < expected.length; index += 1) {
    assert.deepEqual([...got[index]!], [...expected[index]!], `frame ${index} differs`);
  }
});

test("a persistent pool serves several chunks and closes without leaking handles", async () => {
  const pool = createRasterPool({ concurrency: 2 });
  try {
    const first = await pool.run([{ svg: svgOf("#ff0000"), ...SIZE }, { svg: svgOf("#00ff00"), ...SIZE }]);
    const second = await pool.run([{ svg: svgOf("#0000ff"), ...SIZE }]);
    assert.equal(first.length, 2);
    assert.equal(second.length, 1);
    assert.deepEqual([...second[0]!], [...rasterize(svgOf("#0000ff"), SIZE)]);
    assert.notDeepEqual([...first[0]!], [...first[1]!]);
  } finally {
    await pool.close();
  }
});

test("a bad svg rejects the chunk instead of hanging the render", async () => {
  const pool = createRasterPool({ concurrency: 2 });
  try {
    await assert.rejects(
      () => pool.run([{ svg: svgOf("#abcdef"), ...SIZE }, { svg: "this is not svg", ...SIZE }, { svg: svgOf("#fedcba"), ...SIZE }]),
      (error: unknown) => /raster pool failed/i.test(String(error)) && /SVG data parsing failed/i.test(String(error))
    );
    await assert.rejects(() => pool.run([{ svg: svgOf("#123456"), ...SIZE }]), /closed/i);
  } finally {
    await pool.close();
  }
});

test("cancelling waits for the workers to stop", async () => {
  const pool = createRasterPool({ concurrency: 2 });
  const jobs = Array.from({ length: 60 }, (_, index) => ({ svg: svgOf(`#00${String(index % 250).padStart(2, "0")}18`), ...SIZE }));
  const run = pool.run(jobs);
  const settled = assert.rejects(() => run, /closed|cancel/i);
  await pool.close();
  await settled;
});

test("the pool never asks for more workers than cores, and at least one", () => {
  const cores = cpus().length;
  assert.ok(rasterPoolSize() >= 1);
  assert.ok(rasterPoolSize() <= cores);
  assert.equal(rasterPoolSize(1), 1);
  assert.equal(rasterPoolSize(cores * 4), cores);
});
