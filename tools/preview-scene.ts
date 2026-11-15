// Renders one scene of a packaged project to a PNG at a chosen frame, without narration or the full pipeline. Layout QA
// only: it exists so a visual defect can be looked at in seconds instead of waiting on a 19-minute render.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { TimedScene } from "../src/contracts.ts";
import { rasterize } from "../src/frames.ts";
import { frameState } from "../src/scene-state.ts";
import { frameSvg } from "../src/svg-scene.ts";

const [projectPath, sceneId, frameArg = "60", outPath = `work/preview-${sceneId}.png`] = process.argv.slice(2);
if (!projectPath || !sceneId) throw new Error("usage: preview-scene.ts <project.json> <sceneId> [frame] [out.png]");

const project = JSON.parse(await readFile(projectPath, "utf8")) as {
  script: { chapters: { utterances: { id: string; scene: Record<string, unknown> }[] }[] };
};

const found = project.script.chapters
  .flatMap((chapter) => chapter.utterances)
  .find((utterance) => String(utterance.scene.id) === sceneId);
if (!found) throw new Error(`${sceneId} is not a scene of ${projectPath}`);

// a stand-in five-second cue: the layout does not depend on the real narration length
const scene = TimedScene.parse({
  ...found.scene,
  startSample: 0,
  endSampleExclusive: 150 * 48_000,
  sampleRate: 48_000,
  frameRate: 30
});
const style = { width: 1920, height: 1080, sampleRate: 48_000, frameRate: 30 };
const png = rasterize(frameSvg(frameState(scene, Number(frameArg), style), style), style);
await mkdir(outPath.replace(/[^/\\]+$/, ""), { recursive: true });
await writeFile(outPath, png);
console.log(JSON.stringify({ scene: sceneId, kind: scene.kind, frame: Number(frameArg), bytes: png.byteLength, out: outPath }));
