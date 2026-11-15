import assert from "node:assert/strict";
import { test } from "node:test";
import { frameState } from "../src/scene-state.ts";
import { frameSvg } from "../src/svg-scene.ts";
import { TimedScene } from "../src/contracts.ts";

const style = { width: 1920, height: 1080, sampleRate: 48000, frameRate: 30 };

const comparison = TimedScene.parse({
  schemaVersion: 1,
  id: "s01",
  kind: "comparison",
  utteranceIds: ["u001", "u002"],
  claimIds: ["c1"],
  assetIds: [],
  beats: [
    { at: 0, action: "reveal", target: "title" },
    { at: 1, action: "reveal", target: "left" },
    { at: 2, action: "reveal", target: "right" },
    { at: 4, action: "count", target: "left-value" },
    { at: 5, action: "count", target: "right-value" },
    { at: 6, action: "highlight", target: "right-value" }
  ],
  props: { title: "Inflation vs policy rate", left: "Inflation", right: "Policy rate", unit: "% per year", values: [{ label: "Inflation", value: 3.2 }, { label: "Policy rate", value: 4.5 }] },
  startSample: 0,
  endSampleExclusive: 480000,
  sampleRate: 48000,
  frameRate: 30
});

test("elements stay hidden until their reveal beat and are gone before frame zero", () => {
  const before = frameState(comparison, -1, style);
  assert.equal(before.elements.get("left")?.opacity, 0);
  const starting = frameState(comparison, 0, style);
  assert.equal(starting.elements.get("title")?.opacity, 0);
  const midReveal = frameState(comparison, 6, style);
  assert.ok(midReveal.elements.get("title")!.opacity > 0 && midReveal.elements.get("title")!.opacity < 1);
  const revealed = frameState(comparison, 12, style);
  assert.equal(revealed.elements.get("title")?.opacity, 1);
});

test("count beats ramp to the real value without exceeding it", () => {
  assert.equal(frameState(comparison, 120, style).elements.get("left-value")?.text, "0.0");
  const half = frameState(comparison, 126, style).elements.get("left-value")!;
  const eased = Number(half.text);
  assert.ok(eased > 0 && eased < 3.2, `got ${half.text}`);
  assert.equal(frameState(comparison, 156, style).elements.get("left-value")?.text, "3.2");
  assert.equal(frameState(comparison, 400, style).elements.get("right-value")?.text, "4.5");
});

test("highlight adds a bounded emphasis and does not remove the element", () => {
  const peak = frameState(comparison, 192, style).elements.get("right-value")!;
  assert.ok(peak.scale > 1 && peak.scale <= 1.08, `scale ${peak.scale}`);
  assert.equal(peak.opacity, 1);
  const after = frameState(comparison, 240, style).elements.get("right-value")!;
  assert.equal(after.scale, 1);
});

test("a process scene moves a packet between anchors and draws its connectors", () => {
  const scene = TimedScene.parse({
    schemaVersion: 1, id: "s02", kind: "process", utteranceIds: ["u01"], claimIds: [], assetIds: [],
    beats: [
      { at: 0, action: "reveal", target: "title" },
      { at: 0.5, action: "reveal", target: "node-0" },
      { at: 1.5, action: "draw", target: "link-0" },
      { at: 2.5, action: "move", target: "packet", to: "node-1" },
      { at: 4.5, action: "move", target: "packet", to: "node-2" }
    ],
    props: { title: "How a packet travels", steps: ["App", "Router", "Server"], flowDirection: "left-right" },
    startSample: 0, endSampleExclusive: 480000, sampleRate: 48000, frameRate: 30
  });
  const atMoveStart = frameState(scene, 75, style).elements.get("packet")!;
  const midMove = frameState(scene, 87, style).elements.get("packet")!;
  const atMoveEnd = frameState(scene, 99, style).elements.get("packet")!;
  assert.ok(midMove.x > atMoveStart.x && midMove.x < atMoveEnd.x, `x ${midMove.x}`);
  assert.equal(atMoveEnd.x, frameState(scene, 120, style).elements.get("packet")!.x);
  // the packet rests centred on its destination node rather than on a pixel the layout happened to produce
  const node2 = frameState(scene, 159, style).elements.get("node-2")!;
  const parked = frameState(scene, 159, style).elements.get("packet")!;
  assert.equal(parked.x, node2.x + (node2.width - parked.width) / 2);
  assert.equal(parked.y, node2.y + (node2.height - parked.height) / 2);
  const link = frameState(scene, 57, style).elements.get("link-0")!;
  assert.ok(link.drawProgress > 0 && link.drawProgress < 1, `progress ${link.drawProgress}`);
  assert.equal(frameState(scene, 69, style).elements.get("link-0")?.drawProgress, 1);
});

test("no sustained empty shot: three frames or fewer without visible content", () => {
  let blankRun = 0;
  let worst = 0;
  for (let frame = 0; frame <= comparison.frameCount; frame += 1) {
    const state = frameState(comparison, frame, style);
    const visible = [...state.elements.values()].some((element) => element.opacity > 0.02);
    blankRun = visible ? 0 : blankRun + 1;
    worst = Math.max(worst, blankRun);
  }
  assert.ok(worst <= 3, `blankest run was ${worst} frames`);
});

test("rendering is a pure function of frame and scene", () => {
  const a = frameSvg(frameState(comparison, 200, style), { width: style.width, height: style.height });
  const b = frameSvg(frameState(comparison, 200, style), { width: style.width, height: style.height });
  assert.equal(a, b);
  const c = frameSvg(frameState(comparison, 201, style), { width: style.width, height: style.height });
  assert.notEqual(a, c);
});

test("generated svg carries geometry but no executable content or remote references", () => {
  const svg = frameSvg(frameState(comparison, 200, style), { width: style.width, height: style.height });
  assert.match(svg, /^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" width="1920" height="1080" viewBox="0 0 1920 1080"/);
  assert.equal(svg.split("http").length - 1, 1, "only the svg namespace may reference a uri");
  for (const forbidden of ["<script", "onload", "onclick", "eval(", "foreignObject", "image "]) {
    assert.equal(svg.includes(forbidden), false, forbidden);
  }
});

test("scene geometry stays inside the title-safe area", () => {
  const state = frameState(comparison, 200, style);
  for (const element of state.elements.values()) {
    assert.ok(element.x >= 0 && element.y >= 0, element.id);
    assert.ok(element.x + element.width <= style.width, `${element.id} right overflow`);
    assert.ok(element.y + element.height <= style.height, `${element.id} bottom overflow`);
  }
});

test("a bar the model only highlighted is still drawn, and its label's colour word colours it", () => {
  const chart = TimedScene.parse({
    schemaVersion: 1, id: "s08", kind: "bar-chart", utteranceIds: ["u008"], claimIds: ["c8"], assetIds: [],
    // s008 as delivered: no grow beat anywhere, which left both bars at zero height
    beats: [
      { at: 0, action: "reveal", target: "title" },
      { at: 1.5, action: "highlight", target: "bar-0" },
      { at: 3, action: "highlight", target: "bar-1" }
    ],
    props: { title: "Scattering strength relative to red", unit: "× red", series: [{ label: "Green 530 nm", value: 2.63 }, { label: "Yellow 580 nm", value: 1.83 }], axis: "category" },
    startSample: 0, endSampleExclusive: 480000, sampleRate: 48000, frameRate: 30
  });
  const late = frameState(chart, 150, style);
  const green = late.elements.get("bar-0")!;
  const yellow = late.elements.get("bar-1")!;
  assert.equal(green.grow, 1, "a highlighted bar must have height even without a grow beat");
  assert.equal(yellow.grow, 1);
  assert.equal(green.fill, "#4fc47f", `a bar labelled Green was drawn ${green.fill}`);
  assert.equal(yellow.fill, "#f5c85c", `a bar labelled Yellow was drawn ${yellow.fill}`);
  assert.notEqual(green.fill, yellow.fill);
});
