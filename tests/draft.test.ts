import assert from "node:assert/strict";
import { createServer } from "node:http";
import { test } from "node:test";
import type { AddressInfo } from "node:net";
import { draftEpisode } from "../src/draft.ts";
import type { JobBrief, Source } from "../src/contracts.ts";

const sources: Source[] = [
  {
    id: "src1",
    url: "https://www.nih.gov/news-events/nih-research-matters/how-people-see-color",
    title: "How people see color",
    publisher: "NIH",
    retrievedAt: "2026-11-05T20:00:00.000Z",
    excerpt: "Cones come in three types, each tuned to a different band of wavelengths.",
    locator: "section: cones",
    snapshotHash: "a".repeat(64)
  }
];

const job: JobBrief = {
  topic: "Why people see colour differently",
  category: "science",
  audience: "curious general viewer",
  targetSeconds: 240,
  modelId: "qwen3.5:4b",
  voice: "af_heart"
};

function spoken(wordCount: number, seed: string): string {
  // one distinct namespace per utterance: the duplicate gate would otherwise read the stub as the same sentence
  return Array.from({ length: wordCount }, (_, index) => `${seed}word${index}`).join(" ");
}

let stubSerial = 0;

/** The claim ids the prompt assigned to this segment; a stub that ignored them would pad one claim across the script,
 * which is the pattern the claim-overcovered gate now refuses. */
function claimsFrom(prompt: string): string[] {
  const list = prompt.match(/Cover exactly these claims in this segment and nothing else: ([^\n]*)/u)?.[1] ?? "";
  return list.replace(/\.$/u, "").split(", ").filter((claimId) => claimId !== "");
}

function chapterReply(prefix: string, count: number, claimIds: string[]): string {
  const utterances = Array.from({ length: count }, (_, index) => {
    const id = `${prefix}${index + 1}`;
    const cited = [claimIds[index % Math.max(1, claimIds.length)] ?? "c1"];
    return {
      id,
      spokenText: spoken(26, `x${stubSerial++}`),
      captionText: `Caption ${id}`,
      claimIds: cited,
      scene: {
        schemaVersion: 1,
        id: `s-${id}`,
        kind: "bar-chart",
        utteranceIds: [id],
        claimIds: cited,
        assetIds: [],
        beats: [{ at: 0, action: "reveal", target: "title" }],
        props: { title: `Scene ${id}`, unit: "nm", series: [{ label: "2022", value: 420 }, { label: "2024", value: 560 }], axis: "year" }
      }
    };
  });
  return JSON.stringify({ utterances });
}

const claimLedger = (count: number) =>
  Array.from({ length: count }, (_, index) => ({
    id: `c${index + 1}`,
    text: "Human retinas carry three cone types tuned to different wavelength bands.",
    evidence: [{ sourceId: "src1", locator: "section: cones" }],
    material: true,
    review: "unreviewed"
  }));

const outlineReply = JSON.stringify({
  schemaVersion: 1,
  title: "Why people see colour differently",
  language: "en",
  claims: claimLedger(24),
  chapters: [
    { id: "ch1", heading: "Three cones", summary: "What the retina actually holds.", seconds: 120 },
    { id: "ch2", heading: "Different wiring", summary: "How the counts differ between people.", seconds: 60 },
    { id: "ch3", heading: "Same apple, different red", summary: "What that means for one object.", seconds: 60 }
  ]
});

type Recorded = { system: string; prompt: string; think?: boolean };
type Reply = string | ((call: Recorded) => string) | { text: string; doneReason?: string; thinking?: string };

/** Runs the draft against a scripted model server and returns the replies it consumed. */
async function withDraft(replies: Reply[], options?: { job?: JobBrief; onProgress?: (line: string) => void }) {
  const useJob = options?.job ?? job;
  const calls: Recorded[] = [];
  let queue = 0;
  const server = createServer((req, res) => {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      const call = JSON.parse(body) as Recorded;
      calls.push(call);
      const next = replies[queue];
      queue += 1;
      const spec: { text: string; doneReason: string; thinking: string } =
        next === undefined
          ? { text: "", doneReason: "stop", thinking: "" }
          : typeof next === "string"
            ? { text: next, doneReason: "stop", thinking: "" }
            : typeof next === "function"
              ? { text: next(call), doneReason: "stop", thinking: "" }
              : { text: next.text, doneReason: next.doneReason ?? "stop", thinking: next.thinking ?? "" };
      res.writeHead(200, { "content-type": "application/x-ndjson" });
      res.end(
        `${JSON.stringify({ thinking: spec.thinking, response: spec.text, done: true, done_reason: spec.doneReason, eval_count: 1200, prompt_eval_count: 900, eval_duration: 95_000_000_000, prompt_eval_duration: 14_000_000_000 })}\n`
      );
    });
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const host = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  try {
    const result = await draftEpisode({
      job: useJob,
      sources,
      host,
      modelId: useJob.modelId,
      ...(options?.onProgress ? { onProgress: options.onProgress } : {})
    });
    return { result, calls };
  } finally {
    server.close();
  }
}

test("a long script is drafted one outline call plus one call per segment", async () => {
  const progress: string[] = [];
  let serial = 0;
  const chaptersFromPrompt = (call: Recorded): string => {
    const planned = Number(/Return exactly (\d+) utterance/.exec(call.system)?.[1] ?? "0");
    assert.ok(planned > 0 && planned <= 4, `unexpected plan in the chapter prompt: ${call.system.slice(0, 200)}`);
    serial += 1;
    return chapterReply(`g${serial}-`, planned, claimsFrom(call.system));
  };
  const { result, calls } = await withDraft([outlineReply, chaptersFromPrompt, chaptersFromPrompt, chaptersFromPrompt, chaptersFromPrompt, chaptersFromPrompt, chaptersFromPrompt, chaptersFromPrompt], { onProgress: (line) => progress.push(line) });
  assert.equal(result.ok, true, JSON.stringify(result.problems));
  assert.equal(result.outline?.chapters.length, 3);
  // the plan, not a hard-coded count: 120 s -> 12 utterances in 3 segments, 60 s -> 6 in 2 each
  assert.deepEqual(
    result.script?.chapters.map((chapter) => chapter.utterances.length),
    [12, 6, 6]
  );
  assert.equal(calls.length, 1 + 7, "one outline call plus every segment call the plan asks for");
  assert.equal(result.totals.plannedUtterances, 24);
  assert.equal(result.totals.producedUtterances, 24);
  assert.deepEqual(
    result.script?.chapters[0]?.utterances.map((utterance) => utterance.id).slice(0, 3),
    ["u001", "u002", "u003"],
    "assembly owns the global ids"
  );
  assert.ok(Math.abs(result.totals.estimatedSpokenSeconds - 240) <= 3, `estimated ${result.totals.estimatedSpokenSeconds}s`);
  assert.equal(result.totals.completionTokens, 1200 * 8);
  assert.ok(progress.some((line) => line.startsWith("outline")), progress.join(" | "));
  assert.ok(progress.some((line) => line.includes("chapter ch1 segment 1/3")), progress.join(" | "));
});

test("a later segment of the same chapter is told how the previous one ended", async () => {
  const replies: string[] = [];
  const record = (call: Recorded): string => {
    const planned = Number(/Return exactly (\d+) utterance/.exec(call.system)?.[1] ?? "0");
    const reply = chapterReply(`g${replies.length + 1}-`, planned, claimsFrom(call.system));
    replies.push(reply);
    return reply;
  };
  const { calls } = await withDraft([outlineReply, record, record, record, record, record, record, record]);
  assert.ok(calls.length >= 4, `expected several segment calls, got ${calls.length}`);
  const firstTail = JSON.parse(replies[0]!).utterances.at(-1)!.spokenText as string;
  assert.ok(calls[2]!.system.includes(firstTail.slice(-40)), "the second segment continues from the first");
  const secondTail = JSON.parse(replies[1]!).utterances.at(-1)!.spokenText as string;
  assert.ok(calls[3]!.system.includes(secondTail.slice(-40)), "the third segment continues from the second");
  // ch2 starts fresh: its prompt may carry ch1's last tail, but never as its own lead-in
  assert.ok(!calls[4]!.system.includes(firstTail.slice(-40)) || calls[4]!.system.includes("Chapter \"Different wiring"), "a new chapter does not resume mid-thought from the previous one");
});

test("a malformed chapter reply is retried once, then the run stops with the problem recorded", async () => {
  const broken = '{"utterances": [{"id": "u1"';
  const { result, calls } = await withDraft([outlineReply, broken, broken]);
  assert.ok(result.calls[1]?.problems.some((problem) => problem.code === "invalid-json"), JSON.stringify(result.calls[1]?.problems));
  assert.equal(calls.length, 3, "one attempt plus one retry, then stop");
  assert.equal(result.script, null);
  assert.ok(result.outline, "the outline that did succeed is still returned");
});

test("a reply that is only reasoning stops with empty-reply, not a confusing json error", async () => {
  const onlyThinking = { text: "", doneReason: "length", thinking: "a very long chain of thought" };
  const { result, calls } = await withDraft([outlineReply, onlyThinking, onlyThinking]);
  assert.equal(result.ok, false);
  assert.deepEqual(result.calls[1]?.problems.map((problem) => problem.code), ["empty-reply"]);
  assert.equal(calls.length, 3);
  assert.ok(calls.every((call) => call.think === false), "drafting must not pay for reasoning tokens it cannot use");
});

test("an outline citing a source the packet does not have is refused before drafting", async () => {
  const ghost = JSON.parse(outlineReply);
  ghost.claims[0].evidence[0].sourceId = "src9";
  const { result, calls } = await withDraft([JSON.stringify(ghost)]);
  assert.equal(result.ok, false);
  assert.deepEqual(result.problems.map((problem) => problem.code), ["unknown-source"]);
  assert.equal(calls.length, 1, "no chapter call is paid for after a bad outline");
});

test("a segment whose reply breaks the contract is retried once with the violations fed back", async () => {
  const shortJob: JobBrief = { ...job, targetSeconds: 40 };
  const oneChapterOutline = JSON.stringify({
    schemaVersion: 1,
    title: "Why people see colour differently",
    language: "en",
    claims: claimLedger(4),
    chapters: [{ id: "ch1", heading: "Three cones", summary: "What the retina actually holds.", seconds: 40 }]
  });
  const broken = chapterReply("x", 4, ["c1", "c2", "c3", "c4"]).replace('"props":{"title":"Scene x1"', '"props":{"title":"Scene x1","bad":1');
  const fixed = chapterReply("y", 4, ["c1", "c2", "c3", "c4"]);
  const { result, calls } = await withDraft([oneChapterOutline, broken, fixed], { job: shortJob });
  assert.equal(result.ok, true, JSON.stringify(result.problems));
  assert.equal(calls.length, 3, "outline, the rejected reply, then the retry");
  assert.equal(result.calls[1]?.problems[0]?.code, "invalid-chapter");
  assert.ok(calls[2]!.system.includes("fix these"), "the retry must be told what was wrong");
  assert.equal(result.script?.chapters[0]?.utterances.length, 4);
  assert.equal(result.totals.producedUtterances, 4);
});

test("a second bad reply in the same segment stops instead of looping", async () => {
  const shortJob: JobBrief = { ...job, targetSeconds: 40 };
  const oneChapterOutline = JSON.stringify({
    schemaVersion: 1,
    title: "Why people see colour differently",
    language: "en",
    claims: claimLedger(4),
    chapters: [{ id: "ch1", heading: "Three cones", summary: "What the retina actually holds.", seconds: 40 }]
  });
  const broken = chapterReply("z", 4, ["c1", "c2", "c3", "c4"]).replace('"axis":"year"', '"axis":"wavelength"');
  const { result, calls } = await withDraft([oneChapterOutline, broken, broken], { job: shortJob });
  assert.equal(result.ok, false);
  assert.equal(calls.length, 3, "one retry only");
  assert.ok(result.problems.some((problem) => problem.code === "invalid-chapter"));
});

test("a completion truncated by the context window is reported as truncated", async () => {
  const { result } = await withDraft([outlineReply, { text: '{"utterances": [{"id": "u1"', doneReason: "length" }]);
  assert.equal(result.ok, false);
  assert.equal(result.calls[0]?.truncated, false);
  assert.equal(result.calls[1]?.truncated, true, "the caller must see that the context window cut the reply");
  assert.equal(result.calls[1]?.completionTokens, 1200);
});
