import { z } from "zod";
import { BarChartScene, ComparisonScene, ProcessScene, SceneSpec, type JobBrief, type Source } from "./contracts.ts";

export const wordsPerSecond = 2.6;
const DURATION_TOLERANCE = 0.4;
/** Calibrated on draft 8: the repeats a viewer notices measured 0.67 to 0.81 here, unrelated sentences 0.11. */
const DUPLICATE_SIMILARITY = 0.65;
const DUPLICATE_MIN_TOKENS = 8;
/** Measured on the accepted colour draft: 18 claims sit at 1–2 utterances and one at 3, while the three the reviewer
 * called padding (c19, c22, c23) all sit at 4 — c19's fourth sentence even asserts a sex difference the claim never states.
 * The ledger already plans one claim per two utterances, so three is slack rather than a new demand. */
const MAX_UTTERANCES_PER_CLAIM = 3;

function wordTokens(text: string): Set<string> {
  return new Set(text.toLowerCase().match(/[a-z0-9']+/g) ?? []);
}

function overlap(a: Set<string>, b: Set<string>): number {
  let shared = 0;
  for (const token of a) if (b.has(token)) shared += 1;
  return shared / Math.max(1, a.size + b.size - shared);
}


/** One spoken beat, and the ceiling a single model call is held to. */
export const MAX_UTTERANCE_SECONDS = 22;
export const MAX_UTTERANCES_PER_CALL = 4;
/** Draft 7 measured: however the prompt asks, this model returns ~27 spoken words per utterance. */
export const MEASURED_WORDS_PER_UTTERANCE = 27;
/** Completion tokens measured per utterance reply with qwen3.5:4b on this machine, scene object included. */
export const COMPLETION_TOKENS_PER_UTTERANCE = 350;
export const COMPLETION_TOKENS_PER_CLAIM = 150;
export const COMPLETION_TOKENS_PER_CHAPTER_PLAN = 45;
export const COMPLETION_TOKENS_PER_REPLY_FRAME = 400;

const safeId = z.string().regex(/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/);

const ClaimDraft = z.object({
  id: safeId,
  text: z.string().min(12).max(1200),
  evidence: z.array(z.object({ sourceId: safeId, locator: z.string().min(1).max(300) })).min(1).max(6),
  material: z.boolean(),
  review: z.enum(["unreviewed", "approved", "rejected"])
});

const UtteranceDraft = z.object({
  id: safeId,
  spokenText: z.string().min(12).max(1200),
  captionText: z.string().min(4).max(240),
  claimIds: z.array(safeId).min(1).max(6),
  scene: SceneSpec
});
export type Utterance = z.infer<typeof UtteranceDraft>;

const UtterancesReply = z.object({ utterances: z.array(UtteranceDraft).min(1).max(MAX_UTTERANCES_PER_CALL) });

const OutlineChapter = z.object({
  id: safeId,
  heading: z.string().min(3).max(200),
  summary: z.string().min(10).max(400),
  seconds: z.number().int().min(15).max(900)
});

export const OutlineSchema = z.object({
  schemaVersion: z.literal(1),
  title: z.string().min(3).max(200),
  language: z.literal("en"),
  claims: z.array(ClaimDraft).min(1).max(300),
  chapters: z.array(OutlineChapter).min(1).max(40)
});
export type DraftOutline = z.infer<typeof OutlineSchema>;
export type OutlineChapterPlan = z.infer<typeof OutlineChapter>;

const ChapterDraft = z.object({
  id: safeId,
  heading: z.string().min(3).max(200),
  summary: z.string().min(10).max(400),
  utterances: z.array(UtteranceDraft).min(1).max(400)
});

export const ScriptSchema = z.object({
  schemaVersion: z.literal(1),
  title: z.string().min(3).max(200),
  language: z.literal("en"),
  claims: z.array(ClaimDraft).min(1).max(300),
  chapters: z.array(ChapterDraft).min(1).max(40)
});
export type DraftScript = z.infer<typeof ScriptSchema>;

export type WriterProblem = { code: string; message?: string; id?: string };

const outlineJsonSchema = {
  type: "object",
  required: ["schemaVersion", "title", "claims", "chapters"],
  properties: {
    schemaVersion: { type: "integer", enum: [1] },
    title: { type: "string" },
    language: { type: "string", enum: ["en"] },
    claims: {
      type: "array",
      items: {
        type: "object",
        required: ["id", "text", "evidence", "material", "review"],
        properties: {
          id: { type: "string" },
          text: { type: "string" },
          evidence: { type: "array", items: { type: "object", required: ["sourceId", "locator"] } },
          material: { type: "boolean" },
          review: { type: "string", enum: ["unreviewed"] }
        }
      }
    },
    chapters: {
      type: "array",
      items: {
        type: "object",
        required: ["id", "heading", "summary", "seconds"],
        properties: {
          id: { type: "string" },
          heading: { type: "string" },
          summary: { type: "string" },
          seconds: { type: "integer" }
        }
      }
    }
  }
};

/**
 * The scene schema is generated from the renderer's own contracts instead of being typed out by hand,
 * because a 4B model writing a black-box `scene: object` reliably omits required fields and quotes
 * numbers. If the contract changes, the prompt changes with it.
 */
function jsonShapeOf(field: z.ZodType, omit: string[] = []): Record<string, unknown> {
  if (field instanceof z.ZodOptional) return jsonShapeOf(field.unwrap() as z.ZodType, omit);
  if (field instanceof z.ZodDefault) return jsonShapeOf(field.removeDefault() as z.ZodType, omit);
  if (field instanceof z.ZodNumber) return { type: "number" };
  if (field instanceof z.ZodBoolean) return { type: "boolean" };
  if (field instanceof z.ZodLiteral) return { type: typeof field.value, enum: [field.value] };
  if (field instanceof z.ZodEnum) return { type: "string", enum: field.options };
  if (field instanceof z.ZodString) {
    const checks = (field._def as unknown as Record<string, unknown>).checks as Array<Record<string, unknown>> | undefined;
    const regexCheck = checks?.find((check) => {
      const zd = check._zod as Record<string, Record<string, unknown>> | undefined;
      return zd?.def?.format === "regex";
    });
    const zd = regexCheck?._zod as Record<string, Record<string, unknown>> | undefined;
    const pattern = zd?.def?.pattern as RegExp | undefined;
    return pattern ? { type: "string", pattern: pattern.source } : { type: "string" };
  }
  if (field instanceof z.ZodArray) {
    const checks = (field._def as unknown as Record<string, unknown>).checks as Array<Record<string, unknown>> | undefined;
    const minCheck = checks?.find((c) => {
      const zd = c._zod as Record<string, Record<string, unknown>> | undefined;
      return zd?.def?.check === "min_length";
    });
    const maxCheck = checks?.find((c) => {
      const zd = c._zod as Record<string, Record<string, unknown>> | undefined;
      return zd?.def?.check === "max_length";
    });
    const minDef = (minCheck?._zod as Record<string, Record<string, unknown>> | undefined)?.def;
    const maxDef = (maxCheck?._zod as Record<string, Record<string, unknown>> | undefined)?.def;
    return {
      type: "array",
      minItems: (minDef?.minimum as number | undefined) ?? 0,
      maxItems: (maxDef?.maximum as number | undefined) ?? Infinity,
      items: jsonShapeOf(field.element as z.ZodTypeAny, omit)
    };
  }
  if (field instanceof z.ZodObject) {
    const shape = field.shape as Record<string, z.ZodTypeAny>;
    const keys = Object.keys(shape).filter((key) => !omit.includes(key));
    return {
      type: "object",
      required: keys.filter((key) => !shape[key]!.isOptional()),
      properties: Object.fromEntries(keys.map((key) => [key, jsonShapeOf(shape[key]!, omit)])),
      additionalProperties: false
    };
  }
  if (field instanceof z.ZodUnion) {
    return { anyOf: (field.options as z.ZodTypeAny[]).map((option) => jsonShapeOf(option, omit)) };
  }
  return { type: "string" };
}

/** Colours are chosen by the reviewer when the package is built, so the model is never asked to guess them. */
const REPLY_OMIT = ["color"];

function withBeatUnits(schema: Record<string, unknown>): Record<string, unknown> {
  const props = schema.properties as { beats?: { items?: { properties?: Record<string, Record<string, unknown>> } } } | undefined;
  const at = props?.beats?.items?.properties?.at;
  if (at) at.description = "seconds from the start of this utterance, a JSON number like 0 or 1.5, never a string";
  return schema;
}

function sceneReplySchema(): Record<string, unknown> {
  const kinds = [ProcessScene, ComparisonScene, BarChartScene].map((scene) => withBeatUnits(jsonShapeOf(scene, REPLY_OMIT)));
  return {
    type: "object",
    required: ["id", "spokenText", "captionText", "claimIds", "scene"],
    properties: {
      id: { type: "string" },
      spokenText: { type: "string", description: "read aloud, about 40-60 words" },
      captionText: { type: "string", description: "the short on-screen form, never the same words" },
      claimIds: { type: "array", items: { type: "string" }, minItems: 1 },
      scene: {
        ...kinds[0]!,
        properties: { ...(kinds[0]!.properties ?? {}), kind: { type: "string", enum: ["process", "comparison", "bar-chart"] } },
        anyOf: kinds,
        description: "exactly one of the three kinds; its props object must match that kind and no other keys are allowed"
      }
    }
  };
}

const chapterJsonSchema = {
  type: "object",
  required: ["utterances"],
  properties: {
    utterances: {
      type: "array",
      minItems: 1,
      maxItems: MAX_UTTERANCES_PER_CALL,
      items: sceneReplySchema()
    }
  }
};

function sourceList(sources: Source[]): string {
  return sources
    .map((source) => {
      const excerpt = source.excerpt.slice(0, 700);
      return `- id ${source.id} | ${source.publisher} | ${source.title} | locator ${source.locator} | ${excerpt}`;
    })
    .join("\n");
}

const VOICE_RULES = [
  "One idea per utterance, about 55 words of spoken text.",
  "spokenText is read aloud; captionText is the short on-screen form. They must differ.",
  "Scenes are data only: kind is process, comparison or bar-chart; beats use the verbs reveal, hide, move, draw, grow, count, highlight, emphasize, transform with an existing element target.",
  "Allowed element targets: title, left, right, left-bar, right-bar, left-value, right-value, unit, axis, node-<index>, link-<index>, packet, bar-<index>, label-<index>, value-<index>.",
  "A scene lists the utterance ids it plays under, so scene.utteranceIds must contain this utterance's own id.",
  "Every scene carries schemaVersion 1, an id, assetIds (empty unless the packet lists assets) and beats with at, action and target.",
  "Ids are short and plain: letters, digits, dash and underscore only, no spaces, dots or colons.",
  "Do not choose colours: the palette is assigned by the renderer and reviewed when the package is built.",
  "Never emit code, html, css or script tags, and never invent urls, sources or statistics."
].join(" ");

/** Measured on this machine: 7,813 prompt chars evaluated as 1,879 tokens, and 2,605 completion tokens as 8,792 chars. */
export const PROMPT_CHARS_PER_TOKEN = 4;
export const MAX_MODEL_CTX = 16_384;

export function estimatePromptTokens(chars: number): number {
  return Math.ceil(chars / PROMPT_CHARS_PER_TOKEN);
}

/** The context is sized to the work instead of squeezing the work into a fixed window. */
export function sizedNumCtx(input: { promptChars: number; numPredict: number; floor?: number }): number {
  const wanted = estimatePromptTokens(input.promptChars) + input.numPredict + 512;
  return Math.min(MAX_MODEL_CTX, Math.max(input.floor ?? 8_192, wanted));
}

export function utterancesForSeconds(seconds: number): number {
  return Math.max(1, Math.ceil((seconds * wordsPerSecond) / MEASURED_WORDS_PER_UTTERANCE));
}

export function plannedUtteranceCount(targetSeconds: number): number {
  return utterancesForSeconds(targetSeconds);
}

/** A claim is a checkable statement, and narration elaborates: one per two utterances is the verified ratio. */
export function plannedClaimCount(targetSeconds: number): number {
  return Math.max(1, Math.ceil(plannedUtteranceCount(targetSeconds) / 2));
}

export function chapterNumPredict(utterances: number): number {
  return utterances * COMPLETION_TOKENS_PER_UTTERANCE + COMPLETION_TOKENS_PER_REPLY_FRAME;
}

export function outlineNumPredict(targetSeconds: number, chapterCount: number): number {
  return plannedClaimCount(targetSeconds) * COMPLETION_TOKENS_PER_CLAIM + chapterCount * COMPLETION_TOKENS_PER_CHAPTER_PLAN + COMPLETION_TOKENS_PER_REPLY_FRAME;
}

export type DraftSegment = {
  chapterId: string;
  chapter: OutlineChapterPlan;
  index: number;
  of: number;
  plannedUtterances: number;
  plannedSeconds: number;
  claimIds: string[];
};

export function planSegments(outline: DraftOutline): DraftSegment[] {
  const segments: DraftSegment[] = [];
  for (const chapter of outline.chapters) {
    const total = utterancesForSeconds(chapter.seconds);
    const of = Math.ceil(total / MAX_UTTERANCES_PER_CALL);
    let left = total;
    for (let index = 1; index <= of; index += 1) {
      const plannedUtterances = Math.min(MAX_UTTERANCES_PER_CALL, left);
      left -= plannedUtterances;
      segments.push({
        chapterId: chapter.id,
        chapter,
        index,
        of,
        plannedUtterances,
        plannedSeconds: Math.round((chapter.seconds * plannedUtterances) / total),
        claimIds: []
      });
    }
  }
  // Contiguous blocks in ledger order: a call that owns claims cannot re-cover an earlier call's ground, and the
  // prompt never shows prose from another call — draft 9 copied an "already spoken" list verbatim.
  const per = Math.floor(outline.claims.length / segments.length);
  const extra = outline.claims.length % segments.length;
  let cursor = 0;
  segments.forEach((segment, index) => {
    const size = per + (index < extra ? 1 : 0);
    segment.claimIds = outline.claims.slice(cursor, cursor + size).map((claim) => claim.id);
    cursor += size;
  });
  return segments;
}

export function buildOutlinePrompt(
  brief: JobBrief,
  sources: Source[],
  options: { chapterCount: number }
): { system: string; user: string; jsonSchema: typeof outlineJsonSchema } {
  const system = [
    "You are the script planner for an English narrated explainer video.",
    `Topic: ${brief.topic}`,
    `Category: ${brief.category}`,
    `Audience: ${brief.audience}`,
    `The narration budget is target runtime ${brief.targetSeconds} seconds at about ${wordsPerSecond} words per second, which is roughly ${plannedUtteranceCount(brief.targetSeconds)} spoken utterances.`,
    `Plan ${options.chapterCount} chapters whose seconds add up to the target runtime.`,
    `Write about ${plannedClaimCount(brief.targetSeconds)} claims: one claim per two utterances at minimum, each a single checkable statement rather than a paragraph.`,
    "Explain mechanisms, comparisons and change over time.",
    "Every factual claim must cite one of the source ids listed below, with the locator of the passage that supports it. never invent urls, sources or statistics.",
    "Do not write utterances or scenes in this reply. The chapter text is written one call at a time after this plan.",
    `Sources:\n${sourceList(sources)}`,
    `Return only JSON matching this schema:\n${JSON.stringify(outlineJsonSchema)}`
  ].join("\n\n");

  const user = [`Plan the script for: ${brief.topic}`, `Evidence excerpts:\n${sourceList(sources)}`, "Give the claim ledger first, then the chapter plan."].join("\n\n");

  return { system, user, jsonSchema: outlineJsonSchema };
}

export function buildChapterPrompt(
  brief: JobBrief,
  sources: Source[],
  outline: DraftOutline,
  segment: DraftSegment,
  context?: { continueAfter?: string; corrections?: string[] }
): { system: string; user: string; jsonSchema: typeof chapterJsonSchema } {
  const ledger = outline.claims.map((claim) => `- ${claim.id}: ${claim.text}`).join("\n");
  const system = [
    "You are writing one part of the script for an English narrated explainer video.",
    `Topic: ${brief.topic} | Category: ${brief.category} | Audience: ${brief.audience}`,
    `Chapter "${segment.chapter.heading}" — ${segment.chapter.summary}`,
    `This is segment ${segment.index} of ${segment.of} in the chapter.`,
    segment.claimIds.length > 0 ? `Cover exactly these claims in this segment and nothing else: ${segment.claimIds.join(", ")}.` : "",
    `Return exactly ${segment.plannedUtterances} ${segment.plannedUtterances === 1 ? "utterance" : "utterances"} totalling about ${segment.plannedSeconds} seconds of speech, so roughly ${segment.plannedUtterances * MEASURED_WORDS_PER_UTTERANCE} spoken words: two or three sentences each, no longer.`,
    context?.continueAfter ? `The previous segment ended with: "${context.continueAfter}" — continue from there, do not repeat it.` : "",
    context?.corrections?.length
      ? `Your previous reply was rejected by the renderer's schema. fix these and return the whole segment again:\n${context.corrections.map((line) => `- ${line}`).join("\n")}`
      : "",
    "The claim ledger below is fixed for the whole script. Every utterance cites one of the claim ids assigned to this segment, and each scene cites the same ids or a subset.",
    `Say each claim once, or twice at most: a claim cited by more than ${MAX_UTTERANCES_PER_CLAIM} utterances is rejected as padding, and a sentence that adds a fact the claim does not state is rejected as ungrounded.`,
    ledger,
    VOICE_RULES,
    `Return only JSON matching this schema:\n${JSON.stringify(chapterJsonSchema)}`
  ]
    .filter((line) => line !== "")
    .join("\n\n");

  const user = [`Write the utterances of chapter "${segment.chapter.heading}".`, `Evidence excerpts:\n${sourceList(sources)}`].join("\n\n");
  return { system, user, jsonSchema: chapterJsonSchema };
}

export type UtteranceGroup = { chapterId: string; utterances: Utterance[] };

/**
 * Each segment comes back from the model with its own local ids, so `u1` appears once per call. The pipeline owns the
 * global numbering: utterances and scenes are renumbered in reading order and each scene's references follow, which
 * removes the collision class instead of asking a 4B model to remember what it said four calls ago.
 */
export function assembleDraft(outline: DraftOutline, groups: UtteranceGroup[]): DraftScript {
  let serial = 0;
  const ledger = new Set(outline.claims.map((claim) => claim.id));
  // draft 9 cited `claim_9` where the ledger says `claim_9` → `claim_09`; the number is the same citation, so the
  // padding slip is repaired here and a genuinely invented id still reaches the validator as unknown-claim.
  const cite = (id: string): string => {
    if (ledger.has(id)) return id;
    const padded = id.replace(/^(\D*?)(\d+)$/, (_match, prefix: string, digits: string) => `${prefix}${digits.padStart(2, "0")}`);
    return ledger.has(padded) ? padded : id;
  };
  const chapters = outline.chapters.map((chapter) => ({
    id: chapter.id,
    heading: chapter.heading,
    summary: chapter.summary,
    utterances: groups
      .filter((group) => group.chapterId === chapter.id)
      .flatMap((group) => group.utterances)
      .map((utterance) => {
        serial += 1;
        const id = `u${String(serial).padStart(3, "0")}`;
        const claimIds = utterance.claimIds.map(cite);
        const scene = { ...utterance.scene, id: `s${String(serial).padStart(3, "0")}`, utteranceIds: [id], claimIds: utterance.scene.claimIds.map(cite) };
        return { ...utterance, id, claimIds, scene };
      })
  }));
  return { schemaVersion: 1, title: outline.title, language: "en", claims: outline.claims, chapters };
}

function decodeReply<T>(schema: z.ZodType<T>, raw: string, code: string): { ok: boolean; value: T | null; problems: WriterProblem[] } {
  let parsedJson: unknown;
  try {
    parsedJson = JSON.parse(raw);
  } catch (error) {
    return { ok: false, value: null, problems: [{ code: "invalid-json", message: String(error) }] };
  }
  const result = schema.safeParse(parsedJson);
  if (!result.success) {
    return {
      ok: false,
      value: null,
      problems: result.error.issues.slice(0, 12).map((issue) => ({ code, message: `${issue.path.join(".")}: ${issue.message}` }))
    };
  }
  return { ok: true, value: result.data, problems: [] };
}

export function parseOutline(raw: string): { ok: boolean; outline: DraftOutline | null; problems: WriterProblem[] } {
  const result = decodeReply(OutlineSchema, raw, "invalid-outline");
  return { ok: result.ok, outline: result.value, problems: result.problems };
}

export function parseChapter(raw: string): { ok: boolean; utterances: Utterance[]; problems: WriterProblem[] } {
  const result = decodeReply(UtterancesReply, raw, "invalid-chapter");
  return { ok: result.ok, utterances: result.value?.utterances ?? [], problems: result.problems };
}

export function estimateSpokenSeconds(script: DraftScript): number {
  let words = 0;
  for (const chapter of script.chapters) {
    for (const utterance of chapter.utterances) words += utterance.spokenText.split(/\s+/).filter(Boolean).length;
  }
  return Math.round(words / wordsPerSecond);
}

function textFields(script: DraftScript): { where: string; value: string }[] {
  const found: { where: string; value: string }[] = [{ where: "title", value: script.title }];
  for (const claim of script.claims) {
    found.push({ where: `claim:${claim.id}`, value: claim.text });
    for (const evidence of claim.evidence) found.push({ where: `claim:${claim.id}`, value: evidence.locator });
  }
  for (const chapter of script.chapters) {
    found.push({ where: `chapter:${chapter.id}`, value: chapter.heading }, { where: `chapter:${chapter.id}`, value: chapter.summary });
    for (const utterance of chapter.utterances) {
      found.push({ where: `utterance:${utterance.id}`, value: utterance.spokenText }, { where: `utterance:${utterance.id}`, value: utterance.captionText });
      const props = utterance.scene.props as Record<string, unknown>;
      for (const [, value] of Object.entries(props)) {
        if (typeof value === "string") found.push({ where: `scene:${utterance.scene.id}`, value });
        if (Array.isArray(value)) {
          for (const item of value) {
            if (typeof item === "string") found.push({ where: `scene:${utterance.scene.id}`, value: item });
            else if (item && typeof item === "object" && "label" in item) found.push({ where: `scene:${utterance.scene.id}`, value: String((item as { label: unknown }).label) });
          }
        }
      }
    }
  }
  return found;
}

export function validateScript(script: DraftScript, context: { sources: Source[]; targetSeconds: number }): WriterProblem[] {
  const problems: WriterProblem[] = [];
  const knownSources = new Set(context.sources.map((source) => source.id));
  const knownHosts = new Set(
    context.sources.map((source) => {
      try {
        return source.url ? new URL(source.url).hostname : null;
      } catch {
        return null;
      }
    })
  );
  const claimIds = new Set<string>();
  const utteranceIds = new Set<string>();
  const said: { id: string; tokens: Set<string> }[] = [];

  for (const claim of script.claims) {
    if (claimIds.has(claim.id)) problems.push({ code: "duplicate-id", id: claim.id });
    claimIds.add(claim.id);
    for (const evidence of claim.evidence) {
      if (!knownSources.has(evidence.sourceId)) problems.push({ code: "unknown-source", id: claim.id, message: evidence.sourceId });
    }
  }

  for (const chapter of script.chapters) {
    for (const utterance of chapter.utterances) {
      if (utteranceIds.has(utterance.id)) problems.push({ code: "duplicate-id", id: utterance.id });
      utteranceIds.add(utterance.id);
      for (const claimId of utterance.claimIds) {
        if (!claimIds.has(claimId)) problems.push({ code: "unknown-claim", id: utterance.id, message: claimId });
      }
      if (!utterance.scene.utteranceIds.includes(utterance.id)) {
        problems.push({ code: "scene-utterance-mismatch", id: utterance.scene.id, message: utterance.id });
      }
      for (const sceneClaim of utterance.scene.claimIds) {
        if (!claimIds.has(sceneClaim)) problems.push({ code: "unknown-claim", id: utterance.scene.id, message: sceneClaim });
      }
      const tokens = wordTokens(utterance.spokenText);
      if (tokens.size >= DUPLICATE_MIN_TOKENS) {
        // one problem per utterance, naming the earliest sentence it echoes: a 44-utterance repeat list would otherwise bury every other problem
        for (const earlier of said) {
          const score = overlap(tokens, earlier.tokens);
          if (score >= DUPLICATE_SIMILARITY) {
            problems.push({
              code: "duplicate-content",
              id: utterance.id,
              message: `${utterance.id} repeats ${earlier.id} at ${Math.round(score * 100)}% of its words`
            });
            break;
          }
        }
        said.push({ id: utterance.id, tokens });
      }
    }
  }

  const coverage = new Map<string, string[]>();
  for (const chapter of script.chapters) {
    for (const utterance of chapter.utterances) {
      for (const claimId of utterance.claimIds) coverage.set(claimId, [...(coverage.get(claimId) ?? []), utterance.id]);
    }
  }
  for (const [claimId, speakers] of coverage) {
    if (speakers.length > MAX_UTTERANCES_PER_CLAIM) {
      problems.push({
        code: "claim-overcovered",
        id: claimId,
        message: `${claimId} is cited by ${speakers.length} utterances (${speakers.join(", ")})`
      });
    }
  }

  for (const field of textFields(script)) {
    if (/<\s*script|javascript:|eval\s*\(|\bfunction\s*\(|=>|onload\s*=|onclick\s*=/i.test(field.value)) {
      problems.push({ code: "executable-content", id: field.where });
    }
    for (const match of field.value.matchAll(/https?:\/\/([^\s/"'?#]+)/gi)) {
      const host = match[1]?.toLowerCase();
      if (host && !knownHosts.has(host)) problems.push({ code: "invented-url", id: field.where, message: host });
    }
  }

  const estimated = estimateSpokenSeconds(script);
  const drift = Math.abs(estimated - context.targetSeconds) / context.targetSeconds;
  if (drift > DURATION_TOLERANCE) {
    problems.push({ code: "duration-mismatch", message: `estimated ${estimated}s against ${context.targetSeconds}s requested` });
  }

  return [...new Map(problems.map((problem) => [`${problem.code}|${problem.id ?? ""}|${problem.message ?? ""}`, problem])).values()];
}

export function parseDraft(raw: string, context: { sources: Source[]; targetSeconds: number }): {
  ok: boolean;
  script: DraftScript | null;
  problems: WriterProblem[];
} {
  const result = decodeReply(ScriptSchema, raw, "invalid-script");
  if (!result.ok || !result.value) return { ok: false, script: null, problems: result.problems };
  const problems = validateScript(result.value, context);
  return { ok: problems.length === 0, script: result.value, problems };
}
