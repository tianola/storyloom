import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { renderSceneFrames } from "../src/run.ts";
import { TimedScene } from "../src/contracts.ts";

const scene = TimedScene.parse({
  schemaVersion: 1,
  id: "bench",
  kind: "comparison",
  utteranceIds: ["u001"],
  claimIds: [],
  assetIds: [],
  beats: [
    { at: 0, action: "reveal", target: "title" },
    { at: 20, action: "grow", target: "left-bar" },
    { at: 40, action: "highlight", target: "right-value" }
  ],
  props: {
    title: "Rayleigh scattering across the sky",
    left: "Short blue wavelengths",
    right: "Long red wavelengths",
    unit: "relative intensity",
    values: [
      { label: "Blue", value: 5.5 },
      { label: "Red", value: 1 }
    ]
  },
  startSample: 0,
  endSampleExclusive: 192_000,
  sampleRate: 48_000,
  frameRate: 30
});

const style = { width: 1920, height: 1080, sampleRate: 48_000, frameRate: 30 };
const frames = Math.round((192_000 / 48_000) * 30);

async function timed(concurrency: number): Promise<{ ms: number; perFrame: number }> {
  const dir = await mkdtemp(join(tmpdir(), "raster-bench-"));
  const started = Date.now();
  const result = await renderSceneFrames({ scene, framesDir: dir, style, concurrency });
  const ms = Date.now() - started;
  await rm(dir, { recursive: true, force: true });
  if (result.written !== frames) throw new Error(`bench rendered ${result.written} frames, expected ${frames}`);
  return { ms, perFrame: Math.round((ms / result.written) * 10) / 10 };
}

for (const concurrency of [1, 2, 4, 8]) {
  const run = await timed(concurrency);
  console.log(`${concurrency} worker(s): ${run.ms} ms total, ${run.perFrame} ms per frame at 1920x1080`);
}
console.log(`a 15 minute episode is ${Math.round((15 * 60 - 1) * 30)} frames`);
