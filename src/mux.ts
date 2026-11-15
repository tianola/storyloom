import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { buildAssemblyCommand, buildChaptersMetadata, buildConcatList, verifyExport } from "./export.ts";
import { probeJson, digestFile, renameInto, runProcess, type RenderedScene } from "./run.ts";
import type { AudioTimeline } from "./timeline.ts";
import type { MediaProbe } from "./export.ts";

export type MuxInput = {
  dir: string;
  scenes: RenderedScene[];
  masterAudio: { path: string; samples: number; seconds: number };
  timeline: AudioTimeline;
  chapters: { id: string; title: string; startSeconds: number }[];
  frameRate: number;
  outputName: string;
  signal?: AbortSignal;
};

export type MuxResult = { path: string; sha256: string; bytes: number; problems: string[]; expectedFrames: number };

export async function muxExport(input: MuxInput): Promise<MuxResult> {
  await mkdir(input.dir, { recursive: true });
  const sceneFrames = input.scenes.reduce((total, scene) => total + scene.frameCount, 0);
  if (sceneFrames !== input.timeline.totalFrames) {
    throw new RangeError(`scene spans cover ${sceneFrames} frames but the timeline has ${input.timeline.totalFrames}`);
  }
  const totalFrames = input.timeline.totalFrames;
  const concatPath = join(input.dir, "concat.txt");
  const chaptersPath = join(input.dir, "chapters.txt");
  const outputPath = join(input.dir, input.outputName);

  await writeFile(concatPath, buildConcatList(input.scenes.map((scene) => ({ path: scene.path, durationSeconds: scene.durationSeconds }))), "utf8");
  await writeFile(chaptersPath, buildChaptersMetadata(input.chapters, { frameRate: input.frameRate, durationSeconds: input.timeline.masterDurationSeconds }), "utf8");

  const args = buildAssemblyCommand({
    concatList: concatPath,
    chapters: chaptersPath,
    masterAudio: input.masterAudio.path,
    output: outputPath,
    frameRate: input.frameRate,
    sampleRate: input.timeline.sampleRate,
    targetLufs: -15
  });
  const encoded = await runProcess(args, { signal: input.signal });
  if (encoded.code !== 0) throw new Error(`mux failed: ${encoded.stderr.slice(-1200)}`);
  await renameInto(`${outputPath}.part`, outputPath);

  const probe = (await probeJson(outputPath, ["-show_entries", "stream=index,codec_type,codec_name,avg_frame_rate,nb_frames,sample_rate", "-show_entries", "format=duration,nb_streams"])) as unknown as MediaProbe;
  const expectedSeconds = input.timeline.masterDurationSeconds;
  const verification = verifyExport({
    probe,
    expected: {
      durationSeconds: expectedSeconds,
      frameRate: input.frameRate,
      totalFrames,
      sampleRate: input.timeline.sampleRate,
      videoStreams: 1,
      audioStreams: 1
    },
    distinctFrameDigests: input.scenes.reduce((total, scene) => total + scene.distinctFrameDigests, 0),
    sampledFrames: input.scenes.reduce((total, scene) => total + scene.sampledFrames, 0)
  });
  const digest = await digestFile(outputPath);
  return { path: outputPath, sha256: digest.sha256, bytes: digest.bytes, problems: verification.problems.map((problem) => `${problem.code}: ${problem.message}`), expectedFrames: totalFrames };
}

export async function readJson<T>(path: string): Promise<T> {
  return JSON.parse(await readFile(path, "utf8")) as T;
}

export async function writeJson(path: string, value: unknown): Promise<void> {
  await mkdir(join(path, ".."), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}
