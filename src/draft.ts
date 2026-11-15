import type { JobBrief, Source } from "./contracts.ts";
import { generateJson, type GenerateResult } from "./ollama.ts";
import {
  assembleDraft,
  buildChapterPrompt,
  buildOutlinePrompt,
  chapterNumPredict,
  estimateSpokenSeconds,
  outlineNumPredict,
  parseChapter,
  parseOutline,
  planSegments,
  plannedClaimCount,
  plannedUtteranceCount,
  sizedNumCtx,
  validateScript,
  type DraftOutline,
  type DraftScript,
  type Utterance,
  type UtteranceGroup,
  type WriterProblem
} from "./writer.ts";

export type DraftCall = {
  stage: "outline" | "chapter";
  chapterId: string | undefined;
  index: number | undefined;
  of: number | undefined;
  plannedUtterances: number | undefined;
  seconds: number;
  promptTokens: number;
  completionTokens: number;
  tokensPerSecond: number;
  thinkingChars: number;
  attempts: number;
  truncated: boolean;
  rawSample: string;
  problems: WriterProblem[];
};

export type DraftRunResult = {
  ok: boolean;
  outline: DraftOutline | null;
  script: DraftScript | null;
  problems: WriterProblem[];
  calls: DraftCall[];
  totals: {
    seconds: number;
    promptTokens: number;
    completionTokens: number;
    plannedUtterances: number;
    producedUtterances: number;
    estimatedSpokenSeconds: number;
  };
};

export const MAX_SEGMENT_ATTEMPTS = 2;

export function chapterCountFor(targetSeconds: number): number {
  return Math.min(6, Math.max(2, Math.round(targetSeconds / 90)));
}

function record(
  generation: GenerateResult,
  stage: DraftCall["stage"],
  detail: { chapterId?: string; index?: number; of?: number; plannedUtterances?: number },
  problems: WriterProblem[]
): DraftCall {
  return {
    stage,
    chapterId: detail.chapterId,
    index: detail.index,
    of: detail.of,
    plannedUtterances: detail.plannedUtterances,
    seconds: generation.seconds,
    promptTokens: generation.promptTokens,
    completionTokens: generation.completionTokens,
    tokensPerSecond: generation.tokensPerSecond,
    thinkingChars: generation.thinkingChars,
    attempts: generation.attempts,
    truncated: generation.truncated,
    rawSample: generation.text.slice(0, 1200),
    problems
  };
}

/** A model that spends the whole budget on reasoning leaves no answer to parse. */
export function replyProblems(generation: GenerateResult, parsed: WriterProblem[], planned: string): WriterProblem[] {
  if (generation.text.trim() === "") {
    return [
      {
        code: "empty-reply",
        message: `the model produced no answer for ${planned}${generation.thinkingChars > 0 ? ` and spent ${generation.thinkingChars} characters on reasoning` : ""}${generation.truncated ? " before hitting num_predict" : ""}`
      }
    ];
  }
  const problems = [...parsed];
  if (generation.truncated) problems.push({ code: "truncated-reply", message: `${planned} hit num_predict before it finished` });
  return problems;
}

export type GenerateRequest = {
  host: string;
  model: string;
  system: string;
  prompt: string;
  think: false;
  seed: number;
  numCtx: number;
  numPredict: number;
};
export type GenerateFn = (request: GenerateRequest) => Promise<GenerateResult>;

export async function draftEpisode(input: {
  job: JobBrief;
  sources: Source[];
  host: string;
  modelId: string;
  seed?: number;
  numCtx?: number;
  generate?: GenerateFn;
  segmentAttempts?: number;
  onProgress?: (line: string) => void;
}): Promise<DraftRunResult> {
  const { job, sources } = input;
  const seed = input.seed ?? 7;
  const generate: GenerateFn = input.generate ?? generateJson;
  const calls: DraftCall[] = [];
  const say = (line: string) => input.onProgress?.(line);

  const chapterCount = chapterCountFor(job.targetSeconds);
  const outlinePrompt = buildOutlinePrompt(job, sources, { chapterCount });
  const outlinePredict = outlineNumPredict(job.targetSeconds, chapterCount);
  const outlineCtx = sizedNumCtx({ promptChars: outlinePrompt.system.length + outlinePrompt.user.length, numPredict: outlinePredict, ...(input.numCtx === undefined ? {} : { floor: input.numCtx }) });
  say(`outline: ${chapterCount} chapters, ${plannedClaimCount(job.targetSeconds)} claims, ${outlinePredict} tokens at ctx ${outlineCtx}`);
  const outlineCall = await generate({
    host: input.host,
    model: input.modelId,
    system: outlinePrompt.system,
    prompt: outlinePrompt.user,
    think: false,
    seed,
    numCtx: outlineCtx,
    numPredict: outlinePredict
  });
  const parsedOutline = parseOutline(outlineCall.text);
  const outlineProblems: WriterProblem[] = replyProblems(outlineCall, parsedOutline.problems, "the outline");
  for (const claim of parsedOutline.outline?.claims ?? []) {
    for (const evidence of claim.evidence) {
      if (!sources.some((source) => source.id === evidence.sourceId)) {
        outlineProblems.push({ code: "unknown-source", id: claim.id, message: evidence.sourceId });
      }
    }
  }
  calls.push(record(outlineCall, "outline", { plannedUtterances: plannedUtteranceCount(job.targetSeconds) }, outlineProblems));
  if (outlineProblems.length > 0 || !parsedOutline.outline) {
    return { ok: false, outline: parsedOutline.outline, script: null, problems: outlineProblems, calls, totals: totals({}, calls) };
  }
  const outline = parsedOutline.outline;
  say(`outline: ${outline.chapters.length} chapters, ${outline.claims.length} claims in ${outlineCall.seconds.toFixed(0)}s`);

  const segments = planSegments(outline);
  const groups: UtteranceGroup[] = [];
  const lastOfChapter = new Map<string, string>();
  for (const segment of segments) {
    const continueAfter = lastOfChapter.get(segment.chapterId);
    let problems: WriterProblem[] = [];
    let utterances: Utterance[] = [];
    for (let attempt = 1; attempt <= (input.segmentAttempts ?? MAX_SEGMENT_ATTEMPTS); attempt += 1) {
      const corrections = attempt > 1 ? problems.map((problem) => problem.message ?? problem.code) : undefined;
      const prompt = buildChapterPrompt(job, sources, outline, segment, {
        ...(continueAfter ? { continueAfter } : {}),
        ...(corrections ? { corrections } : {})
      });
      const numPredict = chapterNumPredict(segment.plannedUtterances);
      const ctx = sizedNumCtx({
        promptChars: prompt.system.length + prompt.user.length,
        numPredict,
        ...(input.numCtx === undefined ? {} : { floor: input.numCtx })
      });
      say(
        corrections
          ? `chapter ${segment.chapterId} segment ${segment.index}/${segment.of} retry: ${corrections.length} contract violation(s), first was ${corrections[0]}`
          : `chapter ${segment.chapterId} segment ${segment.index}/${segment.of}: ${segment.plannedUtterances} utterances, ctx ${ctx}`
      );
      const generation = await generate({
        host: input.host,
        model: input.modelId,
        system: prompt.system,
        prompt: prompt.user,
        think: false,
        seed: seed + calls.length,
        numCtx: ctx,
        numPredict
      });
      const parsed = parseChapter(generation.text);
      problems = replyProblems(generation, parsed.problems, `chapter ${segment.chapterId} segment ${segment.index}`);
      calls.push(record(generation, "chapter", { chapterId: segment.chapterId, index: segment.index, of: segment.of, plannedUtterances: segment.plannedUtterances }, problems));
      if (problems.length === 0 && parsed.ok) {
        utterances = parsed.utterances;
        break;
      }
    }
    if (problems.length > 0 || utterances.length === 0) {
      say(`stopped: ${problems.map((problem) => problem.code).join(", ") || "an unusable reply"}`);
      return {
        ok: false,
        outline,
        script: null,
        problems,
        calls,
        totals: totals({ plannedUtterances: segments.reduce((sum, item) => sum + item.plannedUtterances, 0) }, calls)
      };
    }
    groups.push({ chapterId: segment.chapterId, utterances });
    const tail = utterances.at(-1);
    if (tail) lastOfChapter.set(segment.chapterId, tail.spokenText.slice(-160));
    say(`${utterances.length} utterances in ${calls.at(-1)!.seconds.toFixed(0)}s (${calls.at(-1)!.tokensPerSecond} tok/s)`);
  }

  const script = assembleDraft(outline, groups);
  const validation = validateScript(script, { sources, targetSeconds: job.targetSeconds });
  return {
    ok: validation.length === 0,
    outline,
    script,
    problems: validation,
    calls,
    totals: totals({ plannedUtterances: segments.reduce((sum, segment) => sum + segment.plannedUtterances, 0), producedUtterances: groups.reduce((sum, group) => sum + group.utterances.length, 0), estimatedSpokenSeconds: estimateSpokenSeconds(script) }, calls)
  };
}

function totals(partial: { plannedUtterances?: number; producedUtterances?: number; estimatedSpokenSeconds?: number }, calls: DraftCall[]): DraftRunResult["totals"] {
  return {
    seconds: Math.round(calls.reduce((sum, call) => sum + call.seconds, 0) * 10) / 10,
    promptTokens: calls.reduce((sum, call) => sum + call.promptTokens, 0),
    completionTokens: calls.reduce((sum, call) => sum + call.completionTokens, 0),
    plannedUtterances: partial.plannedUtterances ?? 0,
    producedUtterances: partial.producedUtterances ?? 0,
    estimatedSpokenSeconds: partial.estimatedSpokenSeconds ?? 0
  };
}
