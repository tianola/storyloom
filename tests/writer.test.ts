import assert from "node:assert/strict";
import { test } from "node:test";
import { z } from "zod";
import { BarChartScene, Beat, ComparisonScene, ProcessScene } from "../src/contracts.ts";
import {
  assembleDraft,
  buildChapterPrompt,
  buildOutlinePrompt,
  chapterNumPredict,
  estimatePromptTokens,
  estimateSpokenSeconds,
  MAX_MODEL_CTX,
  MAX_UTTERANCES_PER_CALL,
  MAX_UTTERANCE_SECONDS,
  outlineNumPredict,
  parseChapter,
  parseDraft,
  MEASURED_WORDS_PER_UTTERANCE,
  plannedClaimCount,
  sizedNumCtx,
  utterancesForSeconds,
  planSegments,
  plannedUtteranceCount,
  ScriptSchema,
  validateScript,
  wordsPerSecond,
  OutlineSchema,
  type DraftScript,
  type Utterance,
  type UtteranceGroup
} from "../src/writer.ts";
import type { Source } from "../src/contracts.ts";

const sources: Source[] = [
  {
    id: "src1",
    url: "https://data.worldbank.org/indicator/FP.CPI.TOTL.ZG",
    title: "Inflation, consumer prices (annual %)",
    publisher: "World Bank",
    retrievedAt: "2026-11-05T20:00:00.000Z",
    excerpt: "Worldwide inflation fell from 8.1% in 2022 to 5.1% in 2024.",
    locator: "series 2022-2024",
    snapshotHash: "a".repeat(64)
  },
  {
    id: "src2",
    url: "https://www.federalreserve.gov/aboutthefed/fedexplained/monetary-policy.htm",
    title: "Monetary policy",
    publisher: "Federal Reserve",
    retrievedAt: "2026-11-05T20:00:00.000Z",
    excerpt: "The policy rate influences borrowing costs and prices over time.",
    locator: "section: tools",
    snapshotHash: "b".repeat(64)
  }
];

const brief = {
  topic: "Why inflation fell",
  category: "economics" as const,
  audience: "curious general viewer",
  targetSeconds: 60,
  modelId: "qwen3.5:4b",
  voice: "af_heart" as const
};

const script: DraftScript = ScriptSchema.parse({
  schemaVersion: 1,
  title: "Why inflation fell",
  language: "en",
  claims: [
    { id: "c1", text: "Worldwide inflation fell from 8.1% in 2022 to 5.1% in 2024.", evidence: [{ sourceId: "src1", locator: "series 2022-2024" }], material: true, review: "unreviewed" },
    { id: "c2", text: "Higher policy rates raise borrowing costs.", evidence: [{ sourceId: "src2", locator: "section: tools" }], material: true, review: "unreviewed" }
  ],
  chapters: [
    {
      id: "ch1",
      heading: "The numbers",
      summary: "What actually happened to prices.",
      utterances: [
        {
          id: "u001",
          spokenText: "Between 2022 and 2024, worldwide inflation fell from about eight percent to about five percent.",
          captionText: "Worldwide inflation: 8.1% (2022) to 5.1% (2024)",
          claimIds: ["c1"],
          scene: {
            schemaVersion: 1, id: "s01", kind: "bar-chart", utteranceIds: ["u001"], claimIds: ["c1"], assetIds: [],
            beats: [{ at: 0, action: "reveal", target: "title" }, { at: 1, action: "grow", target: "bar-0" }],
            props: { title: "Worldwide inflation", unit: "% per year", series: [{ label: "2022", value: 8.1 }, { label: "2024", value: 5.1 }], axis: "year" }
          }
        },
        {
          id: "u002",
          spokenText: "That drop did not happen by accident: borrowing became more expensive.",
          captionText: "Costlier borrowing followed",
          claimIds: ["c2"],
          scene: {
            schemaVersion: 1, id: "s02", kind: "process", utteranceIds: ["u002"], claimIds: ["c2"], assetIds: [],
            beats: [{ at: 0, action: "reveal", target: "title" }, { at: 0.5, action: "move", target: "packet", to: "node-1" }],
            props: { title: "From policy rate to prices", steps: ["Policy rate", "Borrowing", "Demand", "Prices"], flowDirection: "left-right" }
          }
        }
      ]
    }
  ]
});

test("the outline prompt limits the writer to the packet's own source ids", () => {
  const built = buildOutlinePrompt(brief, sources, { chapterCount: 4 });
  assert.ok(built.system.includes("src1") && built.system.includes("src2"));
  assert.match(built.system, /never invent urls/i);
  assert.match(built.system, /target runtime 60 seconds/i);
  assert.ok(built.user.includes("8.1% in 2022"));
  assert.deepEqual(built.jsonSchema.required, ["schemaVersion", "title", "claims", "chapters"]);
  assert.ok(!JSON.stringify(built.jsonSchema).includes("utterances"), "the outline must not ask for utterances");
});

test("the outline prompt states how many claims the runtime needs", () => {
  const built = buildOutlinePrompt(brief, sources, { chapterCount: 4 });
  assert.match(built.system, /about 3 claims/, "a 60 s budget needs three claims");
  assert.match(built.system, /one claim per two utterances/i);
  assert.equal(plannedClaimCount(480), 24);
  assert.equal(plannedClaimCount(60), 3);
});

test("the chapter prompt asks for exactly the planned utterances of one segment", () => {
  const outline = OutlineSchema.parse({
    schemaVersion: 1,
    title: "Why inflation fell",
    language: "en",
    claims: [{ id: "c1", text: "Worldwide inflation fell from 8.1% in 2022 to 5.1% in 2024.", evidence: [{ sourceId: "src1", locator: "series" }], material: true, review: "unreviewed" }],
    chapters: [
      { id: "ch1", heading: "The spike", summary: "Prices ran hot.", seconds: 90 },
      { id: "ch2", heading: "The cooling", summary: "Then it fell.", seconds: 30 }
    ]
  });
  const segments = planSegments(outline);
  assert.deepEqual(segments.map((segment) => [segment.chapterId, segment.index, segment.of, segment.plannedUtterances]), [
    ["ch1", 1, 3, 4],
    ["ch1", 2, 3, 4],
    ["ch1", 3, 3, 1],
    ["ch2", 1, 1, 3]
  ]);
  assert.equal(segments[0]?.plannedSeconds, 40);
  assert.equal(segments[2]?.plannedSeconds, 10);
  assert.equal(segments[3]?.plannedSeconds, 30);

  const built = buildChapterPrompt(brief, sources, outline, segments[1]!);
  assert.ok(built.system.includes("The spike") && built.system.includes("segment 2 of 3"));
  assert.match(built.system, /exactly 4 utterances totalling about 40 seconds/i);
  assert.ok(built.system.includes("c1"), "the chapter call must see the claim ledger ids");
  assert.ok(built.user.includes("src1"), "the chapter call repeats the evidence it may cite");
  assert.ok(!built.system.includes("The previous segment ended with"), "the first segment has nothing to continue from");
  assert.deepEqual(built.jsonSchema.required, ["utterances"]);

  const follow = buildChapterPrompt(brief, sources, outline, segments[0]!, { continueAfter: "Borrowing got expensive fast." });
  assert.ok(follow.system.includes("The previous segment ended with") && follow.system.includes("Borrowing got expensive fast."));
});

test("each segment owns claims, so a call cannot re-cover what an earlier call said", () => {
  const outline = OutlineSchema.parse({
    schemaVersion: 1,
    title: "Why people see colour differently",
    language: "en",
    claims: Array.from({ length: 6 }, (_, index) => ({
      id: `claim_${String(index + 1).padStart(2, "0")}`,
      text: `Statement number ${index + 1} about cones and wavelengths.`,
      evidence: [{ sourceId: "src1", locator: "types" }],
      material: true,
      review: "unreviewed"
    })),
    chapters: [
      { id: "ch1", heading: "Light", summary: "Waves and scattering.", seconds: 120 },
      { id: "ch2", heading: "Eyes", summary: "Cones and confusion.", seconds: 120 }
    ]
  });
  const segments = planSegments(outline);
  const owned = segments.flatMap((segment) => segment.claimIds);
  assert.deepEqual(owned, outline.claims.map((claim) => claim.id), "every claim owned once, in ledger order");
  assert.equal(new Set(owned).size, owned.length, "no claim is assigned to two segments");
  assert.ok(segments.every((segment) => segment.claimIds.length > 0), "a segment with no claim has nothing to write");

  // draft 9 copied the "already spoken" sentences verbatim, so the prompt must name claims, not prose
  const built = buildChapterPrompt(brief, sources, outline, segments[2]!);
  assert.ok(built.system.includes("Cover exactly these claims"), built.system.slice(0, 500));
  for (const claimId of segments[2]!.claimIds) assert.ok(built.system.includes(claimId));
  assert.ok(!built.system.includes("already spoken in this chapter"), "no spoken sentences may be pasted into the prompt");
});

test("assembly normalizes zero-padding slips without inventing citations", () => {
  const outline = OutlineSchema.parse({
    schemaVersion: 1,
    title: "Why inflation fell",
    language: "en",
    claims: [{ id: "claim_09", text: "Worldwide inflation fell from 8.1% in 2022 to 5.1% in 2024.", evidence: [{ sourceId: "src1", locator: "series" }], material: true, review: "unreviewed" }],
    chapters: [{ id: "ch1", heading: "The spike", summary: "Prices ran hot.", seconds: 20 }]
  });
  const utterance = (id: string, claimIds: string[]): Utterance => ({
    id,
    spokenText: "Consumer prices climbed fast through most of that difficult year, and wages lagged behind.",
    captionText: `Caption ${id}`,
    claimIds,
    scene: {
      schemaVersion: 1, id: `s-${id}`, kind: "bar-chart", utteranceIds: [id], claimIds, assetIds: [],
      beats: [{ at: 0, action: "reveal", target: "title" }],
      props: { title: `Scene ${id}`, unit: "%", series: [{ label: "2022", value: 8.1 }, { label: "2024", value: 5.1 }], axis: "year" }
    }
  });
  // draft 9 wrote claim_9 where the ledger says claim_09; the number is the same citation, not a new one
  const assembled = assembleDraft(outline, [{ chapterId: "ch1", utterances: [utterance("u1", ["claim_9"]), utterance("u2", ["claim_42"])] }]);
  assert.deepEqual(assembled.chapters[0]?.utterances.map((item) => item.claimIds), [["claim_09"], ["claim_42"]]);
  assert.deepEqual(assembled.chapters[0]?.utterances.map((item) => item.scene.claimIds), [["claim_09"], ["claim_42"]]);
  const checked = validateScript(assembled, { sources, targetSeconds: 480 });
  assert.deepEqual(checked.filter((problem) => problem.code === "unknown-claim").map((problem) => problem.message), ["claim_42", "claim_42"]);
});

test("segment assembly keeps chapter order and the outline claim ledger", () => {
  const outline = OutlineSchema.parse({
    schemaVersion: 1,
    title: "Why inflation fell",
    language: "en",
    claims: [{ id: "c1", text: "Worldwide inflation fell from 8.1% in 2022 to 5.1% in 2024.", evidence: [{ sourceId: "src1", locator: "series" }], material: true, review: "unreviewed" }],
    chapters: [{ id: "ch1", heading: "The spike", summary: "Prices ran hot.", seconds: 60 }]
  });
  const utterance = (id: string): Utterance => ({
    id,
    spokenText: `Spoken text for ${id} about inflation and the price level.`,
    captionText: `Caption ${id}`,
    claimIds: ["c1"],
    scene: {
      schemaVersion: 1, id: `s-${id}`, kind: "bar-chart", utteranceIds: [id], claimIds: ["c1"], assetIds: [],
      beats: [{ at: 0, action: "reveal", target: "title" }, { at: 1, action: "grow", target: "bar-0" }],
      props: { title: `Scene ${id}`, unit: "%", series: [{ label: "2022", value: 8.1 }], axis: "year" }
    }
  });
  const assembled = assembleDraft(outline, [
    { chapterId: "ch1", utterances: [utterance("u1")] },
    { chapterId: "ch1", utterances: [utterance("u2")] }
  ]);
  assert.equal(assembled?.chapters[0]?.utterances.length, 2);
  assert.deepEqual(assembled?.chapters[0]?.utterances.map((item) => item.id), ["u001", "u002"]);
  assert.deepEqual(assembled?.claims.map((claim) => claim.id), ["c1"]);
});

test("a chapter reply that is not an utterance array is reported, not swallowed", () => {
  const bad = parseChapter('{"utterances":[]}');
  assert.equal(bad.ok, false);
  assert.ok(bad.problems.some((problem) => problem.code === "invalid-chapter"));
  const truncated = parseChapter('{"utterances": [{"id": "u1"');
  assert.ok(truncated.problems.some((problem) => problem.code === "invalid-json"));
});

test("the chapter prompt states the scene contract, field for field", () => {
  const outline = OutlineSchema.parse({
    schemaVersion: 1,
    title: "Why inflation fell",
    language: "en",
    claims: [{ id: "c1", text: "Worldwide inflation fell from 8.1% in 2022 to 5.1% in 2024.", evidence: [{ sourceId: "src1", locator: "series" }], material: true, review: "unreviewed" }],
    chapters: [{ id: "ch1", heading: "The spike", summary: "Prices ran hot.", seconds: 30 }]
  });
  const built = buildChapterPrompt(brief, sources, outline, planSegments(outline)[0]!);
  const stated = JSON.stringify(built.jsonSchema);

  for (const scene of [ProcessScene, ComparisonScene, BarChartScene]) {
    for (const key of Object.keys(scene.shape)) {
      assert.ok(stated.includes(`"${key}"`), `the prompt omits scene field ${key}`);
    }
    const props = scene.shape.props as z.ZodObject<Record<string, z.ZodTypeAny>>;
    for (const key of Object.keys(props.shape)) {
      assert.ok(stated.includes(`"${key}"`), `the prompt omits props field ${key}`);
    }
  }

  const actions = (Beat.shape.action as z.ZodEnum<[string, ...string[]]>).options;
  for (const action of actions) assert.ok(stated.includes(`"${action}"`), `the prompt omits beat action ${action}`);
  assert.match(stated, /seconds/i, "beat.at must be described as seconds, the field the model got wrong");
  assert.ok(/additionalProperties: false|"additionalProperties":false/.test(stated) || stated.includes("no other keys"), "strict props must be stated");

  // patterns must be bare JSON-Schema sources; "/^.../$/" is not a pattern and cost two whole segments
  assert.ok(!stated.includes('"/'), `patterns must not be wrapped in regex slashes: ${stated.slice(0, 200)}`);
  assert.ok(stated.includes("[A-Za-z0-9][A-Za-z0-9_-]"), "id shape must be stated as a pattern");

  // colour is the renderer's and the reviewer's decision, never the model's
  assert.ok(!stated.includes('"color"'), "the reply schema must not invite the model to choose colours");
  assert.match(built.system, /do not choose colours/i);
});

test("a retry prompt carries the exact contract violations back to the model", () => {
  const outline = OutlineSchema.parse({
    schemaVersion: 1,
    title: "Why inflation fell",
    language: "en",
    claims: [{ id: "c1", text: "Worldwide inflation fell from 8.1% in 2022 to 5.1% in 2024.", evidence: [{ sourceId: "src1", locator: "series" }], material: true, review: "unreviewed" }],
    chapters: [{ id: "ch1", heading: "The spike", summary: "Prices ran hot.", seconds: 30 }]
  });
  const built = buildChapterPrompt(brief, sources, outline, planSegments(outline)[0]!, {
    corrections: ['utterances.3.scene.props.values.0.color: Expected a string matching "#rrggbb"']
  });
  assert.ok(built.system.includes("fix these"), built.system.slice(0, 300));
  assert.ok(built.system.includes("utterances.3.scene.props.values.0.color"));
});

test("drafting budgets stay inside the measured context window", () => {
  assert.equal(MAX_UTTERANCE_SECONDS, 22);
  assert.equal(MAX_UTTERANCES_PER_CALL, 4);
  assert.equal(plannedUtteranceCount(480), 47);
  assert.equal(chapterNumPredict(4), 1_800);
  assert.equal(outlineNumPredict(480, 6), 4_270);
  // prompt evidence + schema text is measured at roughly 2k tokens on this packet
  assert.ok(chapterNumPredict(MAX_UTTERANCES_PER_CALL) + estimatePromptTokens(8_000) + 512 <= 8_192);
  assert.ok(outlineNumPredict(1_200, 8) + estimatePromptTokens(8_000) + 512 <= MAX_MODEL_CTX, "a 20 min episode must fit the grown window");
});

test("assembling renumbers utterance and scene ids so segments cannot collide", () => {
  const outline = OutlineSchema.parse({
    schemaVersion: 1,
    title: "Why inflation fell",
    language: "en",
    claims: [
      { id: "c1", text: "Worldwide inflation fell from 8.1% in 2022 to 5.1% in 2024.", evidence: [{ sourceId: "src1", locator: "series" }], material: true, review: "unreviewed" },
      { id: "c2", text: "Energy costs explained most of the early rise in consumer prices.", evidence: [{ sourceId: "src1", locator: "series" }], material: true, review: "unreviewed" },
      { id: "c3", text: "Wage growth stayed below the headline inflation rate.", evidence: [{ sourceId: "src1", locator: "series" }], material: true, review: "unreviewed" },
      { id: "c4", text: "Core inflation eased once supply chains recovered.", evidence: [{ sourceId: "src1", locator: "series" }], material: true, review: "unreviewed" }
    ],
    chapters: [{ id: "ch1", heading: "The spike", summary: "Prices ran hot.", seconds: 60 }]
  });
  const SENTENCES = [
    "Consumer prices climbed fast through most of that difficult year.",
    "Wage growth stayed well below the headline number for workers.",
    "Energy costs explained nearly half of the early jump overall.",
    "Core inflation eased only after the supply chains finally recovered.",
    "Interest rates rose twice while the committee reacted quite slowly.",
    "Household savings cushioned part of the first sharp price shock.",
    "Food prices kept rising while goods prices finally fell back down.",
    "Unemployment drifted lower even as real pay barely grew at all."
  ];
  // every segment comes back from the model with the same local ids, which is what draft 7 did
  const group = (count: number, offset: number): UtteranceGroup => ({
    chapterId: "ch1",
    utterances: Array.from({ length: count }, (_, index) => {
      const id = `u${index + 1}`;
      return {
        id,
        spokenText: SENTENCES[(offset + index) % SENTENCES.length]!,
        captionText: `Caption ${index + 1}`,
        claimIds: [`c${(offset + index) % 4 + 1}`],
        scene: {
          schemaVersion: 1, id: "s1", kind: "bar-chart", utteranceIds: [id], claimIds: [`c${(offset + index) % 4 + 1}`], assetIds: [],
          beats: [{ at: 0, action: "reveal", target: "title" }],
          props: { title: "Scene", unit: "%", series: [{ label: "2022", value: 8.1 }, { label: "2024", value: 5.1 }], axis: "year" }
        }
      };
    })
  });
  const assembled = assembleDraft(outline, [group(2, 0), group(2, 2)]);
  const utterances = assembled.chapters[0]!.utterances;
  assert.deepEqual(utterances.map((item) => item.id), ["u001", "u002", "u003", "u004"]);
  assert.deepEqual(utterances.map((item) => item.scene.id), ["s001", "s002", "s003", "s004"]);
  assert.deepEqual(utterances.map((item) => item.scene.utteranceIds), [["u001"], ["u002"], ["u003"], ["u004"]]);
  assert.deepEqual(validateScript(structuredClone({ ...assembled, chapters: assembled.chapters.map((c) => ({ ...c, utterances: c.utterances.map((u) => ({ ...u, spokenText: `${u.spokenText} ${u.spokenText} ${u.spokenText}` })) })) }), { sources, targetSeconds: 60 }).map((problem) => problem.code), []);
});

test("near-duplicate utterances are caught instead of shipping the same sentence twice", () => {
  const outline = OutlineSchema.parse({
    schemaVersion: 1,
    title: "Why people see colour differently",
    language: "en",
    claims: [{ id: "c1", text: "Blue light is scattered more than red light.", evidence: [{ sourceId: "src1", locator: "why is the sky blue" }], material: true, review: "unreviewed" }],
    chapters: [{ id: "ch1", heading: "Light", summary: "Waves and scattering.", seconds: 60 }]
  });
  const group = (texts: string[]): UtteranceGroup => ({
    chapterId: "ch1",
    utterances: texts.map((text, index) => {
      const id = `u${index + 1}`;
      return {
        id,
        spokenText: text,
        captionText: `Caption ${index + 1}`,
        claimIds: ["c1"],
        scene: {
          schemaVersion: 1, id: "s1", kind: "bar-chart", utteranceIds: [id], claimIds: ["c1"], assetIds: [],
          beats: [{ at: 0, action: "reveal", target: "title" }],
          props: { title: "Scene", unit: "%", series: [{ label: "2022", value: 8.1 }, { label: "2024", value: 5.1 }], axis: "year" }
        }
      };
    })
  });
  // draft 8 wrote this sentence in six different segments; the gate must refuse it
  const repeated = assembleDraft(outline, [
    group([
      "Sunlight contains all the colors of the rainbow, but blue light travels as shorter, smaller waves than red light.",
      "Sunlight contains all the colors of the rainbow, but blue light travels as shorter waves than red.",
      "As the sun lowers, sunlight passing through more air scatters even more blue light away from the beam.",
      "Because blue scatters about five times more easily than red, the whole dome of sky fills with blue light."
    ])
  ]);
  const repeatedCodes = validateScript(repeated, { sources, targetSeconds: 60 }).map((problem) => problem.code);
  assert.ok(repeatedCodes.includes("duplicate-content"), JSON.stringify(repeatedCodes));

  const distinct = assembleDraft(outline, [
    group([
      "Worldwide inflation peaked at 8.1 percent in 2022, the highest run in two decades.",
      "Energy prices after the invasion of Ukraine drove most of that early rise.",
      "By 2024 the annual rate had eased to roughly 5.1 percent across advanced economies.",
      "Wage growth stayed below the headline number throughout the whole period."
    ])
  ]);
  assert.equal(
    validateScript(distinct, { sources, targetSeconds: 60 }).filter((problem) => problem.code === "duplicate-content").length,
    0,
    "distinct sentences must not trip the gate"
  );
});

test("the ledger asks for one claim per two utterances", () => {
  assert.equal(plannedClaimCount(480), Math.ceil(plannedUtteranceCount(480) / 2));
  assert.equal(plannedClaimCount(60), 3);
});

test("a claim padded across four utterances is refused as over-covered", () => {
  const outline = OutlineSchema.parse({
    schemaVersion: 1,
    title: "Why people see colour differently",
    language: "en",
    claims: [
      { id: "c1", text: "Color vision deficiency usually runs in families.", evidence: [{ sourceId: "src1", locator: "inheritance" }], material: true, review: "unreviewed" },
      { id: "c2", text: "Men are affected far more often than women.", evidence: [{ sourceId: "src1", locator: "inheritance" }], material: true, review: "unreviewed" }
    ],
    chapters: [{ id: "ch1", heading: "Inheritance", summary: "Why it runs in families.", seconds: 60 }]
  });
  const LINES = [
    "The condition passes from parents to children through inherited genes.",
    "It appears across several generations of the same family quite often.",
    "Most people are born with it rather than acquiring it later in life.",
    "Men carry the inherited form far more often than women do."
  ];
  const padded = (claimIds: string[]): UtteranceGroup => ({
    chapterId: "ch1",
    utterances: claimIds.map((claimId, index) => ({
      id: `u${index + 1}`,
      spokenText: LINES[index]!,
      captionText: `Caption ${index + 1}`,
      claimIds: [claimId],
      scene: {
        schemaVersion: 1, id: `s${index + 1}`, kind: "bar-chart", utteranceIds: [`u${index + 1}`], claimIds: [claimId], assetIds: [],
        beats: [{ at: 0, action: "reveal", target: "title" }],
        props: { title: "Inheritance", unit: "%", series: [{ label: "Men", value: 8 }, { label: "Women", value: 0.5 }], axis: "category" }
      }
    }))
  });
  const codes = (group: UtteranceGroup): string[] =>
    validateScript(assembleDraft(outline, [group]), { sources, targetSeconds: 60 }).map((problem) => problem.code);
  // four sentences on one claim is the c19/c22/c23 pattern the reviewer had to edit out by hand
  assert.ok(codes(padded(["c1", "c1", "c1", "c1"])).includes("claim-overcovered"), "four utterances on one claim must be refused");
  assert.ok(!codes(padded(["c1", "c1", "c2", "c2"])).includes("claim-overcovered"), "two on a claim is normal pacing");
});

test("utterance planning uses the measured words per utterance, not the aspiration", () => {
  assert.equal(MEASURED_WORDS_PER_UTTERANCE, 27);
  // draft 7: 24 utterances came back as 640 spoken words, so ~27 each however the prompt asks
  assert.equal(plannedUtteranceCount(480), Math.ceil((480 * wordsPerSecond) / MEASURED_WORDS_PER_UTTERANCE));
  assert.ok(plannedUtteranceCount(480) > 40, "a 480 s budget must plan for what the model really writes");
  assert.equal(utterancesForSeconds(120), Math.ceil((120 * wordsPerSecond) / MEASURED_WORDS_PER_UTTERANCE));
});

test("the context window is sized to the work instead of the work to the window", () => {
  assert.equal(estimatePromptTokens(7_813), 1_954);
  assert.equal(sizedNumCtx({ promptChars: 7_813, numPredict: 1_600 }), 8_192, "small calls keep the floor");
  const big = sizedNumCtx({ promptChars: 30_000, numPredict: 8_000 });
  assert.ok(big >= 8_000 && big <= MAX_MODEL_CTX, `${big}`);
  assert.ok(big >= 8_000 + 7_500 + 512 || big === MAX_MODEL_CTX, "prompt plus completion plus margin must fit");
  assert.equal(sizedNumCtx({ promptChars: 1_000, numPredict: 1_000, floor: 4_096 }), 4_096);
  // the truncation this fixes: the old 60-tokens-per-claim estimate did not match what the model really writes
  assert.equal(plannedClaimCount(480), 24);
  assert.equal(outlineNumPredict(480, 5), 24 * 150 + 5 * 45 + 400);
});

test("the validator is shared by single-reply and assembled drafts", () => {
  const outline = OutlineSchema.parse({
    schemaVersion: 1,
    title: "Why inflation fell",
    language: "en",
    claims: [{ id: "c1", text: "Worldwide inflation fell from 8.1% in 2022 to 5.1% in 2024.", evidence: [{ sourceId: "src1", locator: "series" }], material: true, review: "unreviewed" }],
    chapters: [{ id: "ch1", heading: "The spike", summary: "Prices ran hot.", seconds: 20 }]
  });
  const group = (id: string, spokenText: string): Utterance => ({
    id,
    spokenText,
    captionText: `Caption ${id}`,
    claimIds: ["c9"],
    scene: {
      schemaVersion: 1, id: `s-${id}`, kind: "bar-chart", utteranceIds: [id], claimIds: ["c1"], assetIds: [],
      beats: [{ at: 0, action: "reveal", target: "title" }],
      props: { title: `Scene ${id}`, unit: "%", series: [{ label: "2022", value: 8.1 }], axis: "year" }
    }
  });
  // both replies carry the same local id and the same scene id; only the sentences differ, so the duplicate gate stays quiet
  const assembled = assembleDraft(outline, [
    {
      chapterId: "ch1",
      utterances: [
        group("u1", "Consumer prices climbed fast through most of that difficult year."),
        group("u1", "Core inflation eased only after the supply chains finally recovered.")
      ]
    }
  ]);
  assert.ok(assembled);
  const checked = validateScript(assembled, { sources, targetSeconds: 480 });
  // the two replies carried the same local id; assembly renumbers them, so only the bad citation survives as a problem
  assert.deepEqual(checked.map((problem) => problem.code).filter((code) => code !== "duration-mismatch"), ["unknown-claim", "unknown-claim"]);
  assert.deepEqual(assembled.chapters[0]?.utterances.map((utterance) => utterance.id), ["u001", "u002"]);
});

test("a well-formed script parses and keeps spoken and display text separate", () => {
  const result = parseDraft(JSON.stringify(script), { sources, targetSeconds: 10 });
  assert.equal(result.ok, true, JSON.stringify(result.problems));
  const first = result.script?.chapters[0]?.utterances[0];
  assert.equal(first?.captionText, "Worldwide inflation: 8.1% (2022) to 5.1% (2024)");
  assert.ok(first!.spokenText.length > first!.captionText.length);
});

test("claims must cite packet sources and text must not smuggle new urls", () => {
  const inventedSource = structuredClone(script);
  inventedSource.chapters[0]!.utterances[0]!.claimIds = ["c3"];
  inventedSource.claims.push({ id: "c3", text: "Made up statistic.", evidence: [{ sourceId: "ghost", locator: "none" }], material: true, review: "unreviewed" });
  assert.deepEqual(
    parseDraft(JSON.stringify(inventedSource), { sources, targetSeconds: 10 }).problems.map((problem) => problem.code),
    ["unknown-source"]
  );

  const inventedUrl = structuredClone(script);
  inventedUrl.chapters[0]!.heading = "Source: https://blog.example.org/claim";
  assert.ok(parseDraft(JSON.stringify(inventedUrl), { sources, targetSeconds: 10 }).problems.some((problem) => problem.code === "invented-url"));
});

test("executable content and duplicate ids are rejected", () => {
  const executable = structuredClone(script);
  executable.chapters[0]!.utterances[0]!.captionText = "watch this <script>alert(1)</script>";
  assert.ok(parseDraft(JSON.stringify(executable), { sources, targetSeconds: 10 }).problems.some((problem) => problem.code === "executable-content"));

  const duplicate = structuredClone(script);
  duplicate.chapters[0]!.utterances[1]!.id = "u001";
  assert.ok(parseDraft(JSON.stringify(duplicate), { sources, targetSeconds: 10 }).problems.some((problem) => problem.code === "duplicate-id"));
});

test("a script far from the requested runtime is rejected", () => {
  assert.equal(wordsPerSecond, 2.6);
  assert.equal(estimateSpokenSeconds(script), 10);
  const tooShort = parseDraft(JSON.stringify(script), { sources, targetSeconds: 900 });
  assert.ok(tooShort.problems.some((problem) => problem.code === "duration-mismatch"));
});
