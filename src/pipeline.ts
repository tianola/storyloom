import { assembleTimeline, type AudioTimeline } from "./timeline.ts";
import type { DraftScript } from "./writer.ts";

export const PAUSE_WITHIN_CHAPTER_SECONDS = 0.35;
export const PAUSE_AT_CHAPTER_END_SECONDS = 0.9;

export type NarrationManifest = {
  sampleRate: number;
  voice: string;
  totalSamples: number;
  utterances: { id: string; file: string; text: string; samples: number }[];
};

export function pausePolicy(input: { withinChapter: boolean; sampleRate: number; frameRate: number }): number {
  void input.frameRate;
  const seconds = input.withinChapter ? PAUSE_WITHIN_CHAPTER_SECONDS : PAUSE_AT_CHAPTER_END_SECONDS;
  return Math.round(seconds * input.sampleRate);
}
function orderedUtterances(script: DraftScript) {
  return script.chapters.flatMap((chapter) => chapter.utterances.map((utterance) => ({ chapter, utterance })));
}

export function narrationRequest(script: DraftScript, options: { voice: string; speed: number }): {
  voice: string;
  speed: number;
  utterances: { id: string; text: string }[];
} {
  return {
    voice: options.voice,
    speed: options.speed,
    utterances: orderedUtterances(script).map(({ utterance }) => ({ id: utterance.id, text: utterance.spokenText }))
  };
}

export function timelineFromManifest(
  manifest: NarrationManifest,
  script: DraftScript,
  rates: { sampleRate: number; frameRate: number }
): AudioTimeline {
  const scale = rates.sampleRate / manifest.sampleRate;
  if (!Number.isInteger(scale)) throw new RangeError(`narration sample rate ${manifest.sampleRate} does not divide ${rates.sampleRate}`);
  const byId = new Map(manifest.utterances.map((item) => [item.id, item]));
  const ordered = orderedUtterances(script);

  const utterances = ordered.map((entry, index) => {
    const utterance = entry.utterance;
    const recorded = byId.get(utterance.id);
    if (!recorded) throw new RangeError(`missing narration for ${utterance.id}`);
    if (recorded.text !== utterance.spokenText) throw new RangeError(`narration text mismatch for ${utterance.id}`);
    const next = ordered[index + 1];
    const withinChapter = next !== undefined && next.chapter.id === entry.chapter.id;
    return {
      id: utterance.id,
      spokenText: utterance.spokenText,
      captionText: utterance.captionText,
      claimIds: utterance.claimIds,
      samples: recorded.samples * scale,
      pauseAfterSamples: next === undefined ? 0 : pausePolicy({ withinChapter, sampleRate: rates.sampleRate, frameRate: rates.frameRate })
    };
  });

  return assembleTimeline(utterances, rates);
}

export function chaptersFromTimeline(timeline: AudioTimeline, script: DraftScript): { id: string; title: string; startSeconds: number }[] {
  const byId = new Map(timeline.utterances.map((item) => [item.id, item]));
  return script.chapters.map((chapter) => {
    const first = chapter.utterances[0];
    if (!first) throw new RangeError(`chapter ${chapter.id} has no utterances`);
    const placed = byId.get(first.id);
    if (!placed) throw new RangeError(`missing narration for ${first.id}`);
    return { id: chapter.id, title: chapter.heading, startSeconds: placed.startSample / timeline.sampleRate };
  });
}

export type ProvenanceInput = {
  job: { id: string; revision: number; title: string; category: string; targetSeconds: number };
  writer: { provider: string; modelId: string; digest: string; seed: number };
  narrator: { engine: string; version: string; modelSha256: string; voice: string; speed: number };
  renderer: { engine: string; versions: Record<string, string>; toolchainHash: string };
  timeline: AudioTimeline;
  sourceIds: string[];
  licenses: { id: string; licenseId: string; artifactHash: string }[];
};

export function provenanceManifest(input: ProvenanceInput): {
  schemaVersion: 1;
  generatedAt: string;
  job: ProvenanceInput["job"];
  writer: ProvenanceInput["writer"];
  narrator: ProvenanceInput["narrator"];
  renderer: ProvenanceInput["renderer"];
  timeline: { sampleRate: number; frameRate: number; totalSamples: number; totalFrames: number; masterDurationSeconds: number };
  sourceIds: string[];
  licenses: ProvenanceInput["licenses"];
} {
  return {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    job: input.job,
    writer: input.writer,
    narrator: input.narrator,
    renderer: input.renderer,
    timeline: {
      sampleRate: input.timeline.sampleRate,
      frameRate: input.timeline.frameRate,
      totalSamples: input.timeline.totalSamples,
      totalFrames: input.timeline.totalFrames,
      masterDurationSeconds: input.timeline.masterDurationSeconds
    },
    sourceIds: input.sourceIds,
    licenses: input.licenses
  };
}
