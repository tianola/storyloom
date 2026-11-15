import { readFile } from "node:fs/promises";

const [draftPath, packetPath] = process.argv.slice(2);
if (!draftPath || !packetPath) throw new Error("usage: node tools/review-draft.ts <draft.json> <packet.json>");

const draft = JSON.parse(await readFile(draftPath, "utf8")) as {
  ok: boolean;
  problems: unknown[];
  totals: Record<string, number>;
  outline: { claims: { id: string; text: string; evidence: { sourceId: string; locator: string }[] }[]; chapters: { id: string; heading: string; seconds: number }[] } | null;
  script: { chapters: { id: string; heading: string; utterances: { id: string; spokenText: string; claimIds: string[] }[] }[] } | null;
};
const packet = JSON.parse(await readFile(packetPath, "utf8")) as { sources: { id: string; title: string; publisher: string; excerpt: string }[] };

if (!draft.ok || !draft.outline || !draft.script) {
  console.log(JSON.stringify({ ok: draft.ok, problems: draft.problems, totals: draft.totals }, null, 1));
  process.exit(1);
}

const words = draft.script.chapters.reduce((total, chapter) => total + chapter.utterances.reduce((sum, item) => sum + item.spokenText.split(/\s+/).filter(Boolean).length, 0), 0);
console.log(JSON.stringify({ ok: draft.ok, totals: draft.totals, claims: draft.outline.claims.length, chapters: draft.outline.chapters.length, spokenWords: words }));
console.log("\nchapters:", draft.outline.chapters.map((chapter) => `${chapter.id} ${chapter.seconds}s`).join(", "));

const cited = new Map<string, Set<string>>();
for (const claim of draft.outline.claims) {
  for (const evidence of claim.evidence) {
    if (!cited.has(evidence.sourceId)) cited.set(evidence.sourceId, new Set());
    cited.get(evidence.sourceId)!.add(claim.id);
  }
}

for (const source of packet.sources) {
  const users = cited.get(source.id);
  console.log(`\n=== ${source.id} ${source.publisher} — ${source.title} | claims: ${users ? [...users].join(", ") : "NONE CITED"}`);
  console.log(source.excerpt.slice(0, 900).replace(/\s+/g, " "));
}

console.log("\n=== claims to verify");
const STOP = new Set(["the", "a", "an", "of", "in", "on", "to", "and", "or", "is", "are", "was", "were", "that", "this", "it", "as", "by", "with", "from", "for", "not", "but", "their", "its", "which", "what", "how", "why", "when", "than", "then", "so", "such", "can", "will", "has", "have", "more", "most", "much", "very", "because", "while", "they", "them", "these", "those", "each", "some", "any", "all", "into", "about", "other", "same", "between", "during", "after", "before"]);
const contentWords = (text: string) => new Set(text.toLowerCase().split(/[^a-z0-9]+/).filter((word) => word.length > 3 && !STOP.has(word)));
const excerpts = new Map(packet.sources.map((source) => [source.id, source.excerpt.toLowerCase()]));

const scored = draft.outline.claims.map((claim) => {
  const words = [...contentWords(claim.text)];
  const pool = claim.evidence.map((e) => excerpts.get(e.sourceId) ?? "").join(" ");
  const hit = words.filter((word) => pool.includes(word)).length;
  return { id: claim.id, sources: claim.evidence.map((e) => e.sourceId).join(","), ratio: words.length ? hit / words.length : 0, text: claim.text };
});
scored.sort((a, b) => a.ratio - b.ratio);
console.log("\n=== grounding heuristic, weakest first (word overlap only — read every claim anyway)");
for (const claim of scored) {
  console.log(`${claim.id} [${claim.sources}] ${Math.round(claim.ratio * 100)}% ${claim.text}`);
}

const orphaned = [...new Set(draft.script.chapters.flatMap((chapter) => chapter.utterances.flatMap((utterance) => utterance.claimIds)))];
console.log("\nutterances:", draft.script.chapters.reduce((total, chapter) => total + chapter.utterances.length, 0), "citing", orphaned.length, "distinct claims");
