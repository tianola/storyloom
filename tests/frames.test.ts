import assert from "node:assert/strict";
import { test } from "node:test";
import { createHash } from "node:crypto";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { frameRange, rasterize, sceneVideoArgs } from "../src/frames.ts";
import { writeThumbnail, sceneKey, renderSceneFrames } from "../src/run.ts";
import { TimedScene } from "../src/contracts.ts";
import { frameState } from "../src/scene-state.ts";
import { AVERAGE_ADVANCE, MIN_FONT_SIZE, frameSvg } from "../src/svg-scene.ts";

const scene = TimedScene.parse({
  schemaVersion: 1, id: "s01", kind: "comparison", utteranceIds: ["u001"], claimIds: [], assetIds: [],
  beats: [{ at: 0, action: "reveal", target: "title" }],
  props: { title: "Energy in, light out", left: "Input", right: "Output", unit: "watts", values: [{ label: "Input", value: 100 }, { label: "Output", value: 35 }] },
  startSample: 0, endSampleExclusive: 96000, sampleRate: 48000, frameRate: 30
});

const sha = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");

test("frame range matches the scene span at the pinned rate", () => {
  assert.deepEqual(frameRange(scene), { startFrame: 0, endFrameExclusive: 60, frameCount: 60 });
});

test("rasterizing the same frame twice produces identical bytes", () => {
  const svg = frameSvg(frameState(scene, 30, { width: 1920, height: 1080, sampleRate: 48000, frameRate: 30 }), { width: 1920, height: 1080 });
  const a = rasterize(svg, { width: 1920, height: 1080 });
  const b = rasterize(svg, { width: 1920, height: 1080 });
  assert.equal(sha(a), sha(b));
  assert.equal(a.subarray(1, 4).toString(), "PNG");
});

test("different frames produce different pixels", () => {
  const style = { width: 1920, height: 1080, sampleRate: 48000, frameRate: 30 };
  const early = rasterize(frameSvg(frameState(scene, 2, style), { width: 1920, height: 1080 }), { width: 1920, height: 1080 });
  const late = rasterize(frameSvg(frameState(scene, 45, style), { width: 1920, height: 1080 }), { width: 1920, height: 1080 });
  assert.notEqual(sha(early), sha(late));
});

test("scene video args consume exactly the rendered frame count", () => {
  const args = sceneVideoArgs({ framesDir: "work/s01/frames", sceneId: "s01", frameCount: 60, frameRate: 30, output: "work/s01/scene.mp4" });
  const joined = args.join(" ");
  assert.match(joined, /-framerate 30/);
  assert.match(joined, /-start_number 0/);
  assert.match(joined, /-i work\/s01\/frames\/frame-%05d\.png/);
  assert.match(joined, /-frames:v 60/);
  assert.match(joined, /-pix_fmt yuv420p/);
  assert.equal(args.at(-1), "work/s01/scene.mp4.part");
  assert.equal(args.slice(-3).join(" "), `-f mp4 ${args.at(-1)}`, "a .part suffix hides the container from the format probe");
});

test("a frame count of zero is rejected before ffmpeg is invoked", () => {
  assert.throws(() => sceneVideoArgs({ framesDir: "x", sceneId: "s", frameCount: 0, frameRate: 30, output: "o.mp4" }), /at least one frame/);
});

test("the thumbnail is a real frame of the scene covering the requested time", async () => {
  const second = TimedScene.parse({
    schemaVersion: 1, id: "s02", kind: "bar-chart", utteranceIds: ["u002"], claimIds: [], assetIds: [],
    beats: [{ at: 0, action: "reveal", target: "title" }, { at: 0.4, action: "grow", target: "bar-0" }],
    props: { title: "Scattering by colour", unit: "relative", series: [{ label: "Blue", value: 5.06 }, { label: "Green", value: 2.63 }, { label: "Red", value: 1 }] },
    startSample: 96000, endSampleExclusive: 192000, sampleRate: 48000, frameRate: 30
  });
  const dir = await mkdtemp(join(tmpdir(), "longform-thumb-"));
  const style = { width: 1920, height: 1080, sampleRate: 48000, frameRate: 30 };
  const shot = await writeThumbnail({ scenes: [scene, second], atFrame: 90, dir, style });
  assert.equal(shot.sceneId, "s02");
  assert.equal(shot.path, join(dir, "thumbnail.png"));
  const png = await readFile(shot.path);
  assert.equal(png.subarray(1, 4).toString(), "PNG");
  assert.ok(shot.bytes > 2000, `thumbnail was only ${shot.bytes} bytes`);
  await assert.rejects(() => writeThumbnail({ scenes: [scene, second], atFrame: 5000, dir, style }), /no scene covers frame/);
});

test("the reuse key changes when the scene content changes", () => {
  const style = { width: 1920, height: 1080 };
  const values = [{ label: "Input", value: 100 }, { label: "Output", value: 35 }];
  const base = {
    schemaVersion: 1, id: "s01", kind: "comparison", utteranceIds: ["u001"], claimIds: [], assetIds: [],
    beats: [{ at: 0, action: "reveal", target: "title" }],
    props: { title: "Energy in, light out", left: "Input", right: "Output", unit: "watts", values },
    startSample: 0, endSampleExclusive: 96000, sampleRate: 48000, frameRate: 30
  };
  const before = sceneKey(TimedScene.parse(base), style);
  const recoloured = TimedScene.parse({ ...base, props: { ...base.props, values: [{ ...values[0]!, color: "#123456" }, values[1]!] } });
  assert.notEqual(before, sceneKey(recoloured, style), "a colour change must force a re-render");
  assert.equal(before, sceneKey(TimedScene.parse(base), style));
  assert.notEqual(before, sceneKey(TimedScene.parse(base), { width: 1280, height: 720 }));
});

test("the worker pool draws the same pixels the sequential loop does", async () => {
  const style = { width: 640, height: 360, sampleRate: 48000, frameRate: 30 };
  const dirs = { serial: await mkdtemp(join(tmpdir(), "frames-serial-")), pool: await mkdtemp(join(tmpdir(), "frames-pool-")) };
  const progress: number[] = [];
  const serial = await renderSceneFrames({ scene, framesDir: dirs.serial, style, concurrency: 1 });
  const parallel = await renderSceneFrames({
    scene,
    framesDir: dirs.pool,
    style,
    concurrency: 4,
    onFrame: (done) => progress.push(done)
  });
  assert.equal(serial.written, 60);
  assert.equal(parallel.written, 60);
  assert.deepEqual(parallel.digests.slice().sort(), serial.digests.slice().sort(), "sampled digests must match");
  for (let frame = 0; frame < 60; frame += 1) {
    const name = `frame-${String(frame).padStart(5, "0")}.png`;
    const a = await readFile(join(dirs.serial, name));
    const b = await readFile(join(dirs.pool, name));
    assert.equal(sha(new Uint8Array(a)), sha(new Uint8Array(b)), `${name} differs between serial and pooled`);
  }
  assert.deepEqual(progress, Array.from({ length: 60 }, (_, index) => index + 1), "progress must count every frame once, in order");
});

test("a long step label is wrapped whole and drawn under the box the packet visits", () => {
  const wide = TimedScene.parse({
    schemaVersion: 1, id: "s02", kind: "process", utteranceIds: ["u001"], claimIds: [], assetIds: [],
    beats: [{ at: 0, action: "reveal", target: "node-0" }],
    props: { title: "Colour vision deficiency", steps: ["Hard to distinguish certain colors", "Sees colors differently"], flowDirection: "left-right" },
    startSample: 0, endSampleExclusive: 96000, sampleRate: 48000, frameRate: 30
  });
  const svgStyle = { width: 1920, height: 1080, sampleRate: 48000, frameRate: 30 };
  const state = frameState(wide, 30, svgStyle);
  const box = state.elements.get("node-0")!;
  const label = state.elements.get("step-0")!;
  const svg = frameSvg(state, svgStyle);
  assert.equal(box.text, "", "the packet parks in the centre of the box, so the label cannot live there");
  assert.ok(label.y >= box.y + box.height, `label at ${label.y} must sit below the box ending at ${box.y + box.height}`);
  const group = svg.match(/<g id="step-0"[^>]*>(.*?)<\/g>/u)?.[1] ?? "";
  const lines = [...group.matchAll(/<tspan[^>]*>([^<]*)<\/tspan>/gu)].map((match) => match[1] ?? "");
  const size = Number(group.match(/font-size="(\d+)"/u)?.[1] ?? 0);
  assert.ok(lines.length > 1, `a 34-character label must wrap, got ${JSON.stringify(lines)}`);
  assert.equal(lines.join(" "), "Hard to distinguish certain colors", "wrapping must split the label without dropping words");
  assert.ok(size >= MIN_FONT_SIZE, `font-size ${size} is below the legible floor`);
  for (const line of lines) {
    assert.ok(line.length * size * AVERAGE_ADVANCE <= label.width, `"${line}" at ${size}px overflows ${label.width}px`);
  }
});
