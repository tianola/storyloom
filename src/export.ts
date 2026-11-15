export type Chapter = { startSeconds: number; title: string };

export type AssemblyInput = {
  concatList: string;
  chapters: string;
  masterAudio: string;
  output: string;
  frameRate: number;
  sampleRate: number;
  targetLufs: number;
};

export type MediaProbe = {
  format: { duration: string | "N/A" | undefined; nb_streams: string | undefined };
  streams: ProbeStream[];
};

export type ProbeStream = {
  index: number;
  codec_type: string;
  codec_name?: string | undefined;
  avg_frame_rate?: string | undefined;
  nb_frames?: string | undefined;
  sample_rate?: string | undefined;
  channels?: string | undefined;
  width?: number | undefined;
  height?: number | undefined;
};

export type ExportExpectation = {
  durationSeconds: number;
  frameRate: number;
  totalFrames: number;
  sampleRate: number;
  videoStreams: number;
  audioStreams: number;
};

export type VerificationProblem = { code: string; message: string };
export type Verification = { ok: boolean; problems: VerificationProblem[]; notes: string[] };

const DURATION_TOLERANCE_SECONDS = 0.5;
const BLANK_DISTINCT_RATIO = 0.02;

export function buildConcatList(segments: { path: string; durationSeconds: number }[]): string {
  if (segments.length === 0) throw new RangeError("At least one scene file is required");
  const lines = ["ffconcat version 1.0"];
  for (const segment of segments) {
    if (!Number.isFinite(segment.durationSeconds) || segment.durationSeconds <= 0) {
      throw new RangeError(`Scene ${segment.path} has no positive duration`);
    }
    lines.push(`file '${segment.path.replace(/'/g, "'\\''")}'`, `duration ${segment.durationSeconds.toFixed(3)}`);
  }
  // Repeating the final file is an image-sequence idiom; for encoded video it appends the whole scene a second time.
  return `${lines.join("\n")}\n`;
}

export function buildChaptersMetadata(chapters: Chapter[], input: { frameRate: number; durationSeconds: number }): string {
  if (chapters.length === 0) throw new RangeError("At least one chapter is required");
  if (!Number.isInteger(input.frameRate) || input.frameRate <= 0) throw new RangeError("frameRate must be a positive integer");
  if (!Number.isFinite(input.durationSeconds) || input.durationSeconds <= 0) throw new RangeError("durationSeconds must be positive");
  const sorted = [...chapters].sort((a, b) => a.startSeconds - b.startSeconds);
  const total = Math.floor(input.durationSeconds * 1000);
  const toTime = (seconds: number) => Math.round((Math.floor(seconds * input.frameRate) / input.frameRate) * 1000);
  const blocks = sorted.map((chapter, index) => {
    const start = toTime(chapter.startSeconds);
    const end = index + 1 < sorted.length ? toTime(sorted[index + 1]!.startSeconds) : total;
    if (end <= start) throw new RangeError(`chapter ${chapter.title} ends at or before it starts`);
    // FFmpeg 9 reads only uppercase START/END here; the lowercase spelling parses as zero-length chapters.
    return ["[CHAPTER]", "TIMEBASE=1/1000", `START=${start}`, `END=${end}`, `title=${chapter.title.replace(/\s+/g, " ")}`, ""].join("\n");
  });
  return [";FFMETADATA1", ...blocks].join("\n");
}

export function buildAssemblyCommand(input: AssemblyInput): string[] {
  if (!Number.isInteger(input.sampleRate) || input.sampleRate <= 0) throw new RangeError("sampleRate must be a positive integer");
  if (!Number.isInteger(input.frameRate) || input.frameRate <= 0) throw new RangeError("frameRate must be a positive integer");
  return [
    "ffmpeg",
    "-y",
    "-hide_banner",
    "-loglevel",
    "error",
    "-f",
    "concat",
    "-safe",
    "0",
    "-i",
    input.concatList,
    "-i",
    input.chapters,
    "-i",
    input.masterAudio,
    "-map",
    "0:v:0",
    "-map",
    "2:a:0",
    "-map_metadata",
    "1",
    "-r",
    String(input.frameRate),
    "-c:v",
    "libx264",
    "-preset",
    "medium",
    "-crf",
    "20",
    "-pix_fmt",
    "yuv420p",
    "-af",
    `loudnorm=I=${input.targetLufs}:TP=-1.5:LRA=11`,
    "-ar",
    String(input.sampleRate),
    "-ac",
    "2",
    "-c:a",
    "aac",
    "-b:a",
    "192k",
    "-movflags",
    "+faststart",
    // The .part suffix hides the container from FFmpeg's format probe, so the muxer is named explicitly.
    "-f",
    "mp4",
    `${input.output}.part`
  ];
}

function rateOf(value: string | undefined): number | null {
  if (!value || value === "0/0") return null;
  const [num, den] = value.split("/").map(Number);
  if (!num || !den) return null;
  return num / den;
}

export function verifyExport(input: {
  probe: MediaProbe;
  expected: ExportExpectation;
  distinctFrameDigests: number;
  sampledFrames: number;
}): Verification {
  const problems: VerificationProblem[] = [];
  const notes: string[] = [];
  const duration = Number(input.probe.format.duration);
  if (!Number.isFinite(duration) || duration <= 0) {
    problems.push({ code: "duration-missing", message: `probe duration is ${input.probe.format.duration ?? "missing"}` });
  } else if (Math.abs(duration - input.expected.durationSeconds) > DURATION_TOLERANCE_SECONDS) {
    problems.push({ code: "duration-drift", message: `got ${duration}s, expected ${input.expected.durationSeconds}s` });
  }

  const video = input.probe.streams.filter((stream) => stream.codec_type === "video");
  const audio = input.probe.streams.filter((stream) => stream.codec_type === "audio");
  if (video.length !== input.expected.videoStreams) {
    problems.push({ code: video.length === 0 ? "video-stream-missing" : "video-stream-count", message: `${video.length} video stream(s)` });
  }
  if (audio.length !== input.expected.audioStreams) {
    problems.push({ code: audio.length === 0 ? "audio-stream-missing" : "audio-stream-count", message: `${audio.length} audio stream(s)` });
  }

  const frameRate = rateOf(video[0]?.avg_frame_rate);
  if (frameRate === null) problems.push({ code: "frame-rate-missing", message: "video stream has no readable frame rate" });
  else if (Math.abs(frameRate - input.expected.frameRate) > 0.01) problems.push({ code: "frame-rate-mismatch", message: `got ${frameRate} fps, expected ${input.expected.frameRate} fps` });

  const frames = Number(video[0]?.nb_frames);
  if (!Number.isFinite(frames) || frames <= 0) {
    const derived = Number.isFinite(duration) && duration > 0 ? Math.round(duration * input.expected.frameRate) : 0;
    if (derived > 0 && Math.abs(derived - input.expected.totalFrames) <= 1) {
      notes.push(`frame count derived from duration (${derived} frames); the container did not store nb_frames`);
    } else {
      problems.push({ code: "frame-count-missing", message: `container has no frame count and ${derived} derived frames against ${input.expected.totalFrames} expected` });
    }
  } else if (frames !== input.expected.totalFrames) {
    problems.push({ code: "frame-count-mismatch", message: `got ${frames} frames, expected ${input.expected.totalFrames}` });
  }

  const sampleRate = Number(audio[0]?.sample_rate);
  if (!Number.isFinite(sampleRate) || sampleRate !== input.expected.sampleRate) {
    problems.push({ code: "sample-rate-mismatch", message: `got ${audio[0]?.sample_rate ?? "none"} Hz, expected ${input.expected.sampleRate} Hz` });
  }

  if (input.sampledFrames > 0 && input.distinctFrameDigests / input.sampledFrames < BLANK_DISTINCT_RATIO) {
    problems.push({ code: "blank-frames", message: `${input.distinctFrameDigests} distinct digests across ${input.sampledFrames} sampled frames` });
  }

  return { ok: problems.length === 0, problems, notes };
}
