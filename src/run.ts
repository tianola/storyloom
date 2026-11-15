import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { createReadStream, readFileSync } from "node:fs";
import { mkdir, readFile, readdir, rename, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { frameRange, rasterize, sceneVideoArgs } from "./frames.ts";
import { createRasterPool } from "./raster.ts";
import { frameState } from "./scene-state.ts";
import { frameSvg } from "./svg-scene.ts";
import { planMasterAudio, type NarrationUtterance } from "./audio.ts";
import type { TimedScene } from "./contracts.ts";
import type { AudioTimeline } from "./timeline.ts";

export type ProcessResult = { code: number; stdout: string; stderr: string };

/** A scene cache keyed on the scene alone silently reuses frames drawn by the previous renderer, which is how a fixed
 * defect survives a rebuild. The drawing code is therefore part of the key. */
const RENDERER_SOURCES = ["./animation.ts", "./scene-state.ts", "./svg-scene.ts", "./frames.ts", "./raster.ts", "./raster-worker.ts"];
export const RENDERER_FINGERPRINT = createHash("sha256")
  .update(RENDERER_SOURCES.map((file) => readFileSync(new URL(file, import.meta.url))).join("\n"))
  .digest("hex")
  .slice(0, 16);

export function runProcess(args: string[], options: { cwd?: string | undefined; signal?: AbortSignal | undefined } = {}): Promise<ProcessResult> {
  const [command, ...rest] = args;
  if (!command) return Promise.reject(new RangeError("runProcess needs a command"));
  return new Promise((resolve, reject) => {
    const child = spawn(command, rest, { cwd: options.cwd, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => (stdout += chunk));
    child.stderr.on("data", (chunk: string) => (stderr += chunk));
    const abort = () => child.kill("SIGKILL");
    options.signal?.addEventListener("abort", abort, { once: true });
    child.on("error", (error) => {
      options.signal?.removeEventListener("abort", abort);
      reject(error);
    });
    child.on("close", (code) => {
      options.signal?.removeEventListener("abort", abort);
      resolve({ code: code ?? 1, stdout, stderr });
    });
  });
}

export async function renameInto(part: string, final: string): Promise<void> {
  // Windows refuses a rename while another process (a player, an editor) holds the destination open.
  let lastError: unknown;
  for (let attempt = 0; attempt < 12; attempt += 1) {
    try {
      await rename(part, final);
      return;
    } catch (error) {
      lastError = error;
      if ((error as NodeJS.ErrnoException).code !== "EPERM" && (error as NodeJS.ErrnoException).code !== "EBUSY") throw error;
      await new Promise((resolveSleep) => setTimeout(resolveSleep, 500 * (attempt + 1)));
    }
  }
  throw new Error(`cannot replace ${final}: it is still open elsewhere after 12 attempts (${(lastError as Error).message}); close the player and re-run`);
}

export async function digestFile(path: string): Promise<{ sha256: string; bytes: number }> {
  const hash = createHash("sha256");
  await new Promise<void>((resolve, reject) => {
    const stream = createReadStream(path);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("end", resolve);
    stream.on("error", reject);
  });
  return { sha256: hash.digest("hex"), bytes: (await stat(path)).size };
}

export type NarrationRun = { manifestPath: string; manifest: { sampleRate: number; voice: string; totalSamples: number; utterances: { id: string; file: string; text: string; samples: number }[] } };

export async function synthesizeNarration(input: {
  python: string;
  script: string;
  model: string;
  voices: string;
  outDir: string;
  request: unknown;
  signal?: AbortSignal;
}): Promise<NarrationRun> {
  await mkdir(input.outDir, { recursive: true });
  const requestPath = join(input.outDir, "request.json");
  await writeFile(requestPath, `${JSON.stringify(input.request, null, 2)}\n`, "utf8");
  const result = await runProcess(
    [input.python, input.script, "--input", requestPath, "--output", input.outDir, "--model", input.model, "--voices", input.voices],
    { signal: input.signal }
  );
  if (input.signal?.aborted) throw new Error("narration cancelled");
  if (result.code !== 0) throw new Error(`narration failed with exit ${result.code}: ${result.stderr.slice(-800)}`);
  const manifestPath = join(input.outDir, "manifest.json");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8")) as NarrationRun["manifest"];
  return { manifestPath, manifest };
}

export async function probeJson(path: string, args: string[] = []): Promise<Record<string, unknown>> {
  const result = await runProcess(["ffprobe", "-v", "error", ...args, "-of", "json", path]);
  if (result.code !== 0) throw new Error(`ffprobe failed for ${path}: ${result.stderr.slice(-400)}`);
  return JSON.parse(result.stdout) as Record<string, unknown>;
}

export async function buildMasterAudio(input: {
  dir: string;
  utterances: NarrationUtterance[];
  pausesAfter: Record<string, number>;
  signal?: AbortSignal;
}): Promise<{ path: string; samples: number; seconds: number; sha256: string; bytes: number }> {
  const plan = planMasterAudio({ dir: input.dir, utterances: input.utterances, pausesAfter: input.pausesAfter });
  const result = await runProcess(plan.args, { signal: input.signal });
  if (result.code !== 0) throw new Error(`master audio failed: ${result.stderr.slice(-800)}`);
  const part = `${input.dir}/master.wav.part`;
  const finalPath = `${input.dir}/master.wav`;
  await renameInto(part, finalPath);
  const probe = await probeJson(finalPath, ["-show_entries", "stream=sample_rate,channels", "-show_entries", "format=duration,size"]);
  const streams = (probe.streams as { sample_rate: string; channels: number }[]) ?? [];
  const format = probe.format as { duration?: string; size?: string };
  const seconds = Number(format?.duration);
  if (!Number.isFinite(seconds) || seconds <= 0) throw new Error("master audio has no readable duration");
  if (Number(streams[0]?.sample_rate) !== 48000) throw new Error(`master audio sample rate is ${streams[0]?.sample_rate}, expected 48000`);
  const drift = Math.abs(seconds - plan.masterDurationSeconds);
  if (drift > 0.25) throw new Error(`master audio drift ${drift.toFixed(3)}s against the sample-accurate plan`);
  const digest = await digestFile(finalPath);
  return { path: finalPath, samples: Math.round(seconds * 48000), seconds, sha256: digest.sha256, bytes: digest.bytes };
}

export type RenderedScene = {
  sceneId: string;
  path: string;
  frameCount: number;
  durationSeconds: number;
  sha256: string;
  bytes: number;
  distinctFrameDigests: number;
  sampledFrames: number;
};

export const RASTER_CHUNK_FRAMES = 64;

/** Draws every frame of a scene to disk, rasterizing each chunk across a worker pool. */
export async function renderSceneFrames(input: {
  scene: TimedScene;
  framesDir: string;
  style: { width: number; height: number; sampleRate: number; frameRate: number };
  concurrency?: number | undefined;
  signal?: AbortSignal | undefined;
  onFrame?: (done: number, total: number) => void;
}): Promise<{ digests: string[]; written: number }> {
  const { startFrame, endFrameExclusive, frameCount } = frameRange(input.scene);
  await mkdir(input.framesDir, { recursive: true });
  const digests = new Set<string>();
  const pool = createRasterPool({ concurrency: input.concurrency });
  let written = 0;
  try {
    for (let chunk = 0; chunk < frameCount; chunk += RASTER_CHUNK_FRAMES) {
      if (input.signal?.aborted) throw new Error("render cancelled");
      const size = Math.min(RASTER_CHUNK_FRAMES, frameCount - chunk);
      const jobs = [];
      for (let offset = 0; offset < size; offset += 1) {
        const frame = startFrame + chunk + offset;
        jobs.push({
          svg: frameSvg(frameState(input.scene, frame, input.style), { width: input.style.width, height: input.style.height }),
          width: input.style.width,
          height: input.style.height
        });
      }
      const pngs = await pool.run(jobs);
      for (let offset = 0; offset < size; offset += 1) {
        const frame = startFrame + chunk + offset;
        const png = pngs[offset];
        if (!png) throw new Error(`raster pool returned no frame ${frame} of ${input.scene.id}`);
        await writeFile(join(input.framesDir, `frame-${String(frame - startFrame).padStart(5, "0")}.png`), png);
        if ((frame - startFrame) % 10 === 0) digests.add(createHash("sha256").update(png).digest("hex"));
        written += 1;
        input.onFrame?.(written, frameCount);
      }
    }
  } finally {
    await pool.close();
  }
  if (written !== frameCount) throw new Error(`scene ${input.scene.id} wrote ${written} frames, expected ${frameCount}`);
  return { digests: [...digests], written };
}

export async function renderScene(input: {
  scene: TimedScene;
  dir: string;
  style: { width: number; height: number; sampleRate: number; frameRate: number };
  signal?: AbortSignal;
  onFrame?: (done: number, total: number) => void;
}): Promise<RenderedScene> {
  const { startFrame, frameCount } = frameRange(input.scene);
  const framesDir = join(input.dir, "frames");
  const drawn = await renderSceneFrames({
    scene: input.scene,
    framesDir,
    style: input.style,
    ...(input.signal ? { signal: input.signal } : {}),
    ...(input.onFrame ? { onFrame: input.onFrame } : {})
  });
  const digests = new Set(drawn.digests);
  const outPath = join(input.dir, "scene.mp4");
  const args = sceneVideoArgs({
    framesDir,
    sceneId: input.scene.id,
    frameCount,
    frameRate: input.style.frameRate,
    output: outPath
  });
  const encoded = await runProcess(args, { signal: input.signal });
  if (encoded.code !== 0) throw new Error(`scene encode failed for ${input.scene.id}: ${encoded.stderr.slice(-800)}`);
  await renameInto(`${outPath}.part`, outPath);
  const probe = await probeJson(outPath, ["-count_frames", "-show_entries", "stream=nb_read_frames,avg_frame_rate", "-show_entries", "format=duration"]);
  const streams = (probe.streams as { nb_read_frames?: string; avg_frame_rate?: string }[]) ?? [];
  const counted = Number(streams[0]?.nb_read_frames);
  if (counted !== frameCount) throw new Error(`scene ${input.scene.id} decoded ${counted} frames, expected ${frameCount}`);
  const digest = await digestFile(outPath);
  await writeFile(join(input.dir, "scene.sha256"), sceneKey(input.scene, input.style), "utf8");
  return {
    sceneId: input.scene.id,
    path: outPath,
    frameCount,
    durationSeconds: Number((probe.format as { duration?: string })?.duration ?? 0),
    sha256: digest.sha256,
    bytes: digest.bytes,
    distinctFrameDigests: digests.size,
    sampledFrames: digests.size
  };
}

export function sceneKey(scene: TimedScene, style: { width: number; height: number }): string {
  return createHash("sha256").update(`${JSON.stringify(scene)}|${style.width}x${style.height}|${RENDERER_FINGERPRINT}`).digest("hex");
}

export async function readRenderedScene(scene: TimedScene, dir: string, style: { width: number; height: number }): Promise<RenderedScene | null> {
  const recorded = await readFile(join(dir, "scene.sha256"), "utf8").catch(() => null);
  if (recorded === null || recorded.trim() !== sceneKey(scene, style)) return null;
  const path = join(dir, "scene.mp4");
  const probe = await probeJson(path, [
    "-count_frames",
    "-show_entries",
    "stream=nb_read_frames,avg_frame_rate",
    "-show_entries",
    "format=duration"
  ]).catch(() => null);
  if (!probe) return null;
  const streams = (probe.streams as { nb_read_frames?: string; avg_frame_rate?: string }[]) ?? [];
  const { frameCount } = frameRange(scene);
  if (Number(streams[0]?.nb_read_frames) !== frameCount) return null;
  if (streams[0]?.avg_frame_rate !== `${scene.frameRate}/1`) return null;
  const files = await readdir(join(dir, "frames")).catch(() => [] as string[]);
  const pngs = files.filter((file) => file.endsWith(".png")).sort();
  const digests = new Set<string>();
  for (let index = 0; index < pngs.length; index += 10) {
    const bytes = await readFile(join(dir, "frames", pngs[index]!));
    digests.add(createHash("sha256").update(bytes).digest("hex"));
  }
  const digest = await digestFile(path);
  return {
    sceneId: scene.id,
    path,
    frameCount,
    durationSeconds: Number((probe.format as { duration?: string })?.duration ?? 0),
    sha256: digest.sha256,
    bytes: digest.bytes,
    distinctFrameDigests: digests.size,
    sampledFrames: digests.size
  };
}

export function captionsFor(timeline: AudioTimeline & { utterances: { captionText: string }[] }): string {
  const msPerSample = 1000 / timeline.sampleRate;
  const clock = (milliseconds: number) => {
    const total = Math.max(0, Math.round(milliseconds));
    const pad = (value: number, width = 2) => String(value).padStart(width, "0");
    return `${pad(Math.floor(total / 3600000))}:${pad(Math.floor(total / 60000) % 60)}:${pad(Math.floor(total / 1000) % 60)},${pad(total % 1000, 3)}`;
  };
  return timeline.utterances
    .map((item, index) => `${index + 1}\n${clock(item.startSample * msPerSample)} --> ${clock(item.cueEndSample * msPerSample)}\n${item.captionText}\n`)
    .join("\n");
}

export async function writeThumbnail(input: {
  scenes: TimedScene[];
  atFrame: number;
  dir: string;
  style: { width: number; height: number; sampleRate: number; frameRate: number };
}): Promise<{ path: string; sceneId: string; frame: number; sha256: string; bytes: number }> {
  const scene = input.scenes.find((candidate) => {
    const span = frameRange(candidate);
    return input.atFrame >= span.startFrame && input.atFrame < span.endFrameExclusive;
  });
  if (!scene) throw new RangeError(`no scene covers frame ${input.atFrame}`);
  const span = frameRange(scene);
  const frame = span.startFrame + Math.round((span.frameCount - 1) * 0.6);
  const state = frameState(scene, frame, input.style);
  if (!Array.from(state.elements.values()).some((element) => element.opacity > 0.02)) {
    throw new Error(`thumbnail frame ${frame} of scene ${scene.id} carries no visible content`);
  }
  const png = rasterize(frameSvg(state, { width: input.style.width, height: input.style.height }), {
    width: input.style.width,
    height: input.style.height
  });
  const path = join(input.dir, "thumbnail.png");
  await writeFile(path, png);
  const digest = await digestFile(path);
  return { path, sceneId: scene.id, frame, sha256: digest.sha256, bytes: digest.bytes };
}

export async function ensureDir(path: string): Promise<string> {
  await mkdir(dirname(path), { recursive: true });
  await mkdir(path, { recursive: true });
  return path;
}
