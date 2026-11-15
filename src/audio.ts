export type AudioInput = { path: string; kind: "wav" | "silence"; seconds?: number };

export type NarrationUtterance = { id: string; file: string; samples: number; text: string };

export type AudioPlan = {
  inputs: AudioInput[];
  filter: string;
  args: string[];
  expectedSamples: number;
  masterDurationSeconds: number;
};

type AudioRequest = {
  dir: string;
  utterances: NarrationUtterance[];
  pausesAfter: Record<string, number>;
  sourceRate?: number;
  sampleRate?: number;
  outputName?: string;
};

export function planMasterAudio(request: AudioRequest): AudioPlan {
  const sampleRate = request.sampleRate ?? 48000;
  const sourceRate = request.sourceRate ?? 24000;
  const ratio = sampleRate / sourceRate;
  if (!Number.isInteger(ratio)) {
    throw new RangeError(`planMasterAudio needs an integer resample ratio, got ${sampleRate}/${sourceRate}`);
  }
  if (request.utterances.length === 0) throw new RangeError("Narration needs at least one utterance");

  const inputs: AudioInput[] = [];
  let expectedSamples = 0;
  request.utterances.forEach((utterance, index) => {
    inputs.push({ path: `${request.dir}/${utterance.file}`, kind: "wav" });
    expectedSamples += utterance.samples * ratio;
    const pause = request.pausesAfter[utterance.id] ?? 0;
    if (pause > 0 && index < request.utterances.length - 1) {
      const seconds = Math.round(pause) / sampleRate;
      inputs.push({ path: "anullsrc", kind: "silence", seconds });
      expectedSamples += Math.round(seconds * sampleRate);
    }
  });

  // aresample rejects aoffset/async in this FFmpeg build; the whole graph fails at runtime if they reappear.
  const splits = inputs.map((_, index) => `[${index}:a]aresample=${sampleRate}[a${index}]`);
  const labels = inputs.map((_, index) => `[a${index}]`);
  const filter = `${splits.join(";")};${labels.join("")}concat=n=${inputs.length}:v=0:a=1[aout]`;

  const args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"];
  for (const input of inputs) {
    if (input.kind === "silence") args.push("-f", "lavfi", "-t", String(input.seconds), "-i", `anullsrc=r=${sampleRate}:cl=mono`);
    else args.push("-i", input.path);
  }
  const output = `${request.dir}/${request.outputName ?? "master.wav"}`;
  // The .part suffix hides the container from FFmpeg's format probe, so the muxer is named explicitly.
  args.push("-filter_complex", filter, "-map", "[aout]", "-ar", String(sampleRate), "-ac", "1", "-c:a", "pcm_s16le", "-f", "wav", `${output}.part`);

  return { inputs, filter, args, expectedSamples, masterDurationSeconds: expectedSamples / sampleRate };
}
