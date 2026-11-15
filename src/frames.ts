import { Resvg } from "@resvg/resvg-js";
import type { TimedScene } from "./contracts.ts";

export type FrameRange = { startFrame: number; endFrameExclusive: number; frameCount: number };

export function frameRange(scene: TimedScene): FrameRange {
  const startFrame = scene.startFrame;
  const frameCount = scene.frameCount;
  if (!Number.isInteger(startFrame) || !Number.isInteger(frameCount) || frameCount < 1) {
    throw new RangeError(`scene ${scene.id} has no valid frame span`);
  }
  return { startFrame, endFrameExclusive: startFrame + frameCount, frameCount };
}

export function rasterize(svg: string, options: { width: number; height: number }): Uint8Array {
  if (!Number.isInteger(options.width) || options.width <= 0) throw new RangeError("width must be a positive integer");
  const resvg = new Resvg(svg, {
    fitTo: { mode: "width", value: options.width },
    font: { loadSystemFonts: true, defaultFontFamily: "sans-serif" }
  });
  return resvg.render().asPng();
}

export function sceneVideoArgs(input: {
  framesDir: string;
  sceneId: string;
  frameCount: number;
  frameRate: number;
  output: string;
  crf?: number;
}): string[] {
  if (!Number.isInteger(input.frameCount) || input.frameCount < 1) throw new RangeError(`Scene ${input.sceneId} needs at least one frame`);
  if (!Number.isInteger(input.frameRate) || input.frameRate <= 0) throw new RangeError("frameRate must be a positive integer");
  const crf = input.crf ?? 18;
  return [
    "ffmpeg",
    "-y",
    "-hide_banner",
    "-loglevel",
    "error",
    "-framerate",
    String(input.frameRate),
    "-start_number",
    "0",
    "-i",
    `${input.framesDir}/frame-%05d.png`,
    "-frames:v",
    String(input.frameCount),
    "-c:v",
    "libx264",
    "-preset",
    "medium",
    "-crf",
    String(crf),
    "-pix_fmt",
    "yuv420p",
    "-r",
    String(input.frameRate),
    "-an",
    "-f",
    "mp4",
    `${input.output}.part`
  ];
}
