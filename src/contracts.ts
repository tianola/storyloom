import { z } from "zod";

const id = z.string().regex(/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/);
const hash = z.string().regex(/^[0-9a-f]{64}$/);
const isoDateTime = z.string().datetime({ offset: true }).or(z.string().datetime());
const noUrls = (value: string) => !/https?:\/\/|file:|\\\\|\.\/\.\./.test(value);
const plainText = z.string().min(1).max(400).refine(noUrls, "Scene text must not contain urls or paths");
const nonNegativeSeconds = z.number().finite().nonnegative().max(3600);

export const Beat = z.object({
  at: nonNegativeSeconds,
  action: z.enum([
    "reveal", "hide", "emphasize", "move", "transform", "grow", "draw", "count", "highlight", "fade"
  ]),
  target: z.string().regex(/^[a-z][a-z0-9-]{0,39}$/),
  to: z.string().regex(/^[a-z][a-z0-9-]{0,39}$/).optional()
});

const LabelledValue = z.object({
  label: plainText,
  value: z.number().finite(),
  color: z.string().regex(/^#[0-9a-f]{6}$/).optional()
});

const SceneBase = {
  schemaVersion: z.literal(1),
  id,
  utteranceIds: z.array(id).min(1).max(60),
  claimIds: z.array(id).max(60),
  assetIds: z.array(id).max(40),
  beats: z.array(Beat).min(1).max(200)
};

export const ProcessScene = z.object({
  ...SceneBase,
  kind: z.literal("process"),
  props: z
    .object({
      title: plainText,
      steps: z.array(plainText).min(2).max(8),
      flowDirection: z.enum(["left-right", "bottom-top", "circular"]).optional()
    })
    .strict()
});

export const ComparisonScene = z.object({
  ...SceneBase,
  kind: z.literal("comparison"),
  props: z
    .object({
      title: plainText,
      left: plainText,
      right: plainText,
      unit: plainText,
      values: z.array(LabelledValue).min(2).max(2)
    })
    .strict()
});

export const BarChartScene = z.object({
  ...SceneBase,
  kind: z.literal("bar-chart"),
  props: z
    .object({
      title: plainText,
      unit: plainText,
      series: z.array(LabelledValue).min(2).max(24),
      axis: z.enum(["year", "category"]).optional()
    })
    .strict()
});

export const SceneSpec = z.discriminatedUnion("kind", [ProcessScene, ComparisonScene, BarChartScene]);
export type SceneSpec = z.infer<typeof SceneSpec>;

export const Source = z.object({
  id,
  url: z.string().url().max(2048).optional(),
  title: plainText,
  publisher: plainText,
  retrievedAt: isoDateTime,
  excerpt: z.string().min(1).max(20000),
  locator: z.string().min(1).max(300),
  snapshotHash: hash
});
export type Source = z.infer<typeof Source>;

export const Claim = z.object({
  id,
  text: z.string().min(3).max(1200),
  evidence: z.array(z.object({ sourceId: id, locator: z.string().min(1).max(300) })).min(1),
  material: z.boolean().default(true),
  review: z.enum(["unreviewed", "approved", "rejected"]).default("unreviewed"),
  reviewer: z.string().min(1).max(120).optional(),
  reviewedAt: isoDateTime.optional()
});
export type Claim = z.infer<typeof Claim>;

export const Utterance = z.object({
  id,
  spokenText: z.string().min(2).max(5000),
  captionText: z.string().min(2).max(240),
  claimIds: z.array(id).max(30),
  samples: z.number().int().positive(),
  pauseAfterSamples: z.number().int().nonnegative().default(0)
});
export type Utterance = z.infer<typeof Utterance>;

export const LicenseEntry = z.object({
  id,
  scope: z.enum(["font", "dataset", "model", "voice", "software", "music", "image", "sound-effect"]),
  origin: plainText,
  author: z.string().min(1).max(300).refine((v) => v !== "unknown", "Rights holder must be identified"),
  licenseId: z
    .string()
    .regex(/^[A-Za-z0-9][A-Za-z0-9.+-]{1,63}$/)
    .refine((v) => v.toLowerCase() !== "unknown", "A concrete license id is required"),
  licenseUrl: z.string().url().max(2048),
  licenseTextHash: hash,
  artifactHash: hash,
  attribution: z.string().min(1).max(500),
  modifications: z.string().min(1).max(500),
  review: z.enum(["approved", "pending", "rejected"])
});
export type LicenseEntry = z.infer<typeof LicenseEntry>;

const TimedSceneBase = z.object({
  ...SceneBase,
  kind: z.enum(["process", "comparison", "bar-chart"]),
  props: z.record(z.unknown()),
  startSample: z.number().int().nonnegative(),
  endSampleExclusive: z.number().int().positive(),
  sampleRate: z.number().int().min(8000).max(192000),
  frameRate: z.number().int().min(12).max(120)
}).superRefine((scene, ctx) => {
  if (scene.endSampleExclusive <= scene.startSample) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Scene must span at least one sample" });
  }
});

export function frameSpan(startSample: number, endSampleExclusive: number, sampleRate: number, frameRate: number) {
  const samplesPerFrame = sampleRate / frameRate;
  const startFrame = Math.ceil(startSample / samplesPerFrame);
  const endFrame = Math.ceil(endSampleExclusive / samplesPerFrame);
  return { startFrame, frameCount: Math.max(1, endFrame - startFrame) };
}

export const TimedScene = TimedSceneBase.transform((scene) => {
  const { startFrame, frameCount } = frameSpan(scene.startSample, scene.endSampleExclusive, scene.sampleRate, scene.frameRate);
  const beatFrames = scene.beats.map((beat) => ({
    frame: startFrame + Math.round(beat.at * scene.frameRate),
    action: beat.action,
    target: beat.target,
    ...(beat.to === undefined ? {} : { to: beat.to })
  })).sort((a, b) => a.frame - b.frame);
  return { ...scene, startFrame, frameCount, beatFrames };
});
export type TimedScene = z.infer<typeof TimedScene>;

export const ArtifactRef = z.object({
  id,
  kind: z.enum(["audio", "scene-video", "master-audio", "video", "captions", "chapters", "thumbnail", "manifest", "description", "citations"]),
  path: z.string().min(1).max(4096),
  sha256: hash,
  bytes: z.number().int().nonnegative(),
  toolchainHash: hash
});
export type ArtifactRef = z.infer<typeof ArtifactRef>;

export const JobBrief = z.object({
  topic: z.string().min(3).max(300),
  category: z.enum(["technology", "economics", "studying", "informative", "science"]),
  audience: z.string().min(3).max(300),
  targetSeconds: z.number().int().min(60).max(2400),
  modelId: z.string().min(1).max(200),
  voice: z.string().regex(/^[ab][fm]_[a-z0-9_]{1,40}$/)
});
export type JobBrief = z.infer<typeof JobBrief>;
