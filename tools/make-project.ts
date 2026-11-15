import { readFile, writeFile } from "node:fs/promises";
import { ProjectSchema } from "../src/cli.ts";
import { ScriptSchema, type DraftScript } from "../src/writer.ts";
import { JobBrief, Source } from "../src/contracts.ts";

type ReviewRecord = { reviewer: string; reviewedAt: string; note?: string };

export type BuildInput = {
  job: JobBrief;
  sources: Source[];
  script: DraftScript;
  reviews: Record<string, ReviewRecord>;
  licenses: unknown[];
  voice: string;
  speed: number;
};

/** Turns an accepted draft into a renderable package, refusing to invent any reviewer decision. */
export function buildProjectPackage(input: BuildInput): unknown {
  const claimIds = new Set(input.script.claims.map((claim) => claim.id));
  const problems: string[] = [];
  for (const id of claimIds) {
    const record = input.reviews[id];
    if (!record) problems.push(`claim ${id} has no review record`);
    else if (!record.reviewer.trim()) problems.push(`claim ${id} has no named reviewer`);
  }
  for (const id of Object.keys(input.reviews)) {
    if (!claimIds.has(id)) problems.push(`review record for ${id} matches no claim in the script`);
  }
  if (input.licenses.length === 0) problems.push("a package with no license entries cannot pass the rights gate");
  if (problems.length > 0) throw new Error(`refused to build the package:\n- ${problems.join("\n- ")}`);

  const reviews: Record<string, { reviewer: string; reviewedAt: string }> = {};
  for (const [id, record] of Object.entries(input.reviews)) {
    reviews[id] = { reviewer: record.reviewer, reviewedAt: record.reviewedAt };
  }
  return {
    job: input.job,
    narration: { voice: input.voice, speed: input.speed },
    sources: input.sources,
    licenses: input.licenses,
    reviews,
    script: input.script
  };
}

async function readJson(path: string): Promise<unknown> {
  return JSON.parse(await readFile(path, "utf8"));
}

async function main(argv: string[]): Promise<void> {
  const [packetPath, draftPath, reviewsPath, licensesFrom, outPath] = argv;
  if (!packetPath || !draftPath || !reviewsPath || !licensesFrom || !outPath) {
    throw new Error("usage: node tools/make-project.ts <packet.json> <draft.json> <reviews.json> --licenses-from <project.json> <out.project.json>");
  }
  const packet = readJson(packetPath) as Promise<{ job: JobBrief; sources: Source[] }>;
  const draft = (await readJson(draftPath)) as { ok: boolean; problems: unknown[]; script: DraftScript };
  if (!draft.ok) throw new Error(`the draft is not accepted: ${JSON.stringify(draft.problems).slice(0, 600)}`);
  const reviews = (await readJson(reviewsPath)) as Record<string, ReviewRecord>;
  const template = await readJson(licensesFrom);
  const licenses = (template as { licenses: unknown[] }).licenses;
  const built = await packet;
  const package_ = buildProjectPackage({ ...built, script: draft.script, reviews, licenses, voice: built.job.voice, speed: 1 });
  const parsed = ProjectSchema.parse(package_);
  await writeFile(outPath, `${JSON.stringify(parsed, null, 2)}\n`, "utf8");
  console.log(outPath);
}

if (import.meta.main) {
  const argv = process.argv.slice(2);
  try {
    await main(argv);
  } catch (error) {
    console.error(`make-project failed: ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  }
}
