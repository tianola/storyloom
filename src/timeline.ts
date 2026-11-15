import { frameSpan, type Utterance } from "./contracts.ts";

export type Rate = { sampleRate: number; frameRate: number };

export type TimelineUtterance = Utterance & {
  startSample: number;
  endSampleExclusive: number;
  cueEndSample: number;
};

export type AudioTimeline = {
  sampleRate: number;
  frameRate: number;
  samplesPerFrame: number;
  utterances: TimelineUtterance[];
  totalSamples: number;
  totalFrames: number;
  masterDurationSeconds: number;
  sampleAtFrame: (frame: number) => number;
  frameAtSample: (sample: number) => number;
};

export type SceneSpan = { sceneId: string; samples: number };

export type SceneFrame = { sceneId: string; startSample: number; endSampleExclusive: number; startFrame: number; frameCount: number };

export function assembleTimeline(utterances: Utterance[], rate: Rate): AudioTimeline {
  if (utterances.length === 0) throw new RangeError("Narration needs at least one utterance");
  if (!Number.isInteger(rate.sampleRate) || rate.sampleRate <= 0) throw new RangeError("sampleRate must be a positive integer");
  if (!Number.isInteger(rate.frameRate) || rate.frameRate <= 0) throw new RangeError("frameRate must be a positive integer");

  const samplesPerFrame = rate.sampleRate / rate.frameRate;
  let cursor = 0;
  const placed: TimelineUtterance[] = utterances.map((item) => {
    const startSample = cursor;
    const endSampleExclusive = startSample + item.samples;
    const cueEndSample = endSampleExclusive + item.pauseAfterSamples;
    cursor = cueEndSample;
    return { ...item, startSample, endSampleExclusive, cueEndSample };
  });

  const totalSamples = cursor;
  return {
    sampleRate: rate.sampleRate,
    frameRate: rate.frameRate,
    samplesPerFrame,
    utterances: placed,
    totalSamples,
    totalFrames: Math.ceil(totalSamples / samplesPerFrame),
    masterDurationSeconds: totalSamples / rate.sampleRate,
    sampleAtFrame: (frame) => Math.round(frame * samplesPerFrame),
    frameAtSample: (sample) => Math.ceil(sample / samplesPerFrame)
  };
}

export function sceneFramesFor(spans: SceneSpan[], rate: Rate): SceneFrame[] {
  if (spans.length === 0) throw new RangeError("Scene list must not be empty");
  let cursor = 0;
  return spans.map((span) => {
    if (!Number.isInteger(span.samples) || span.samples <= 0) throw new RangeError(`Scene ${span.sceneId} has no audio span`);
    const startSample = cursor;
    cursor += span.samples;
    const { startFrame, frameCount } = frameSpan(startSample, cursor, rate.sampleRate, rate.frameRate);
    return { sceneId: span.sceneId, startSample, endSampleExclusive: cursor, startFrame, frameCount };
  });
}

function clock(milliseconds: number): string {
  const total = Math.max(0, Math.round(milliseconds));
  const ms = total % 1000;
  const seconds = Math.floor(total / 1000) % 60;
  const minutes = Math.floor(total / 60000) % 60;
  const hours = Math.floor(total / 3600000);
  const pad = (value: number, width = 2) => String(value).padStart(width, "0");
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)},${pad(ms, 3)}`;
}

export function makeSrt(timeline: AudioTimeline): string {
  const msPerSample = 1000 / timeline.sampleRate;
  return timeline.utterances
    .map((item, index) => {
      const start = clock(item.startSample * msPerSample);
      const end = clock(item.cueEndSample * msPerSample);
      return `${index + 1}\n${start} --> ${end}\n${item.captionText}\n`;
    })
    .join("\n");
}
