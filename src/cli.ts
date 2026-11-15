import { readFile, stat, writeFile, mkdir } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import { JobBrief, LicenseEntry, Source, TimedScene } from "./contracts.ts";
import { exportGate, validateClaims, validateEvidence, validateLicenses, verifySnapshots, withReviews } from "./evidence.ts";
import { captionsFor, type RenderedScene } from "./run.ts";
import { chaptersFromTimeline, narrationRequest, provenanceManifest, timelineFromManifest, type NarrationManifest } from "./pipeline.ts";
import { buildMasterAudio, digestFile, readRenderedScene, renderScene, synthesizeNarration, writeThumbnail } from "./run.ts";
import { muxExport, readJson, writeJson } from "./mux.ts";
import { draftEpisode, type GenerateFn } from "./draft.ts";
import { generateJsonChat, quotaWaitSeconds } from "./openai-compat.ts";
import { ScriptSchema, type DraftScript } from "./writer.ts";

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\//, "");
const RATES = { sampleRate: 48000, frameRate: 30 };
const STYLE = { width: 1920, height: 1080, sampleRate: 48000, frameRate: 30 };

export const ProjectSchema = z
  .object({
    job: JobBrief,
    narration: z.object({ voice: z.string().min(1).max(64), speed: z.number().finite().gte(0.5).lte(2) }),
    sources: z.array(Source).min(1),
    licenses: z.array(LicenseEntry).min(1),
    script: ScriptSchema,
    reviews: z.record(z.string(), z.object({ reviewer: z.string().min(1).max(120), reviewedAt: z.string() }))
  })
  .strict();
export type ProjectSpec = z.infer<typeof ProjectSchema>;

const DraftInputSchema = z.object({ job: JobBrief, sources: z.array(Source).min(1) });

function timestamp(seconds: number): string {
  const total = Math.floor(seconds);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(Math.floor(total / 3600))}:${pad(Math.floor(total / 60) % 60)}:${pad(total % 60)}`;
}

function arg(flags: string[], name: string): string | undefined {
  const index = flags.indexOf(`--${name}`);
  return index === -1 ? undefined : flags[index + 1];
}

export function checkScriptClaims(script: ReturnType<typeof ScriptSchema.parse>, claimIds: string[]): string[] {
  const known = new Set(claimIds);
  const problems: string[] = [];
  for (const chapter of script.chapters) {
    for (const utterance of chapter.utterances) {
      for (const claim of [...utterance.claimIds, ...utterance.scene.claimIds]) {
        if (!known.has(claim)) problems.push(`${utterance.id}/${utterance.scene.id} cites unknown claim ${claim}`);
      }
    }
  }
  return problems;
}

async function compileScenes(script: ReturnType<typeof ScriptSchema.parse>, manifest: NarrationManifest) {
  const timeline = timelineFromManifest(manifest, script, RATES);
  const placed = new Map(timeline.utterances.map((item) => [item.id, item]));
  const scenes = [];
  for (const chapter of script.chapters) {
    for (const utterance of chapter.utterances) {
      const item = placed.get(utterance.id);
      if (!item) throw new RangeError(`missing narration for ${utterance.id}`);
      scenes.push(
        TimedScene.parse({
          ...utterance.scene,
          startSample: item.startSample,
          endSampleExclusive: item.cueEndSample,
          sampleRate: RATES.sampleRate,
          frameRate: RATES.frameRate
        })
      );
    }
  }
  const covered = scenes.reduce((total, scene) => total + scene.frameCount, 0);
  if (covered !== timeline.totalFrames) {
    throw new RangeError(`scenes cover ${covered} frames but the timeline has ${timeline.totalFrames}; refusing to render`);
  }
  return { timeline, scenes };
}

/** Measured on nemotron-3.5-super-vl:free: the outline needed 4,627 completion tokens where 4,225 was the plan, because
 * reasoning tokens are billed against max_tokens and no reasoning_effort/thinking flag these routes honour disables it.
 * A 4-utterance segment burned 19,098 reasoning characters against a 5,400-token cap, and the same call only answered at
 * 14,000 (9,455 tokens, 26,138 of them reasoning, 44.6 s), hence the floor. */
const GATEWAY_TOKEN_MULTIPLIER = 3;
const GATEWAY_MIN_TOKENS = 14_000;
/** One wait for the free-tier window, then give up loudly: an unattended job must not sit in a retry loop forever. */
const QUOTA_ROUNDS = 2;

async function commandDraft(flags: string[]): Promise<void> {
  const projectPath = arg(flags, "project");
  if (!projectPath) throw new Error("draft needs --project");
  const project = DraftInputSchema.parse(JSON.parse(await readFile(projectPath, "utf8")));
  const sources = validateEvidence(project.sources);
  if (sources.problems.length > 0) throw new Error(`draft packet is invalid: ${JSON.stringify(sources.problems)}`);
  const host = arg(flags, "host") ?? "http://127.0.0.1:11435";
  const out = arg(flags, "out") ?? join(ROOT, "work", "draft.json");
  const gateway = arg(flags, "gateway");
  const keyEnv = arg(flags, "key-env") ?? "OMNIROUTE_API_KEY";
  const apiKey = gateway ? (process.env[keyEnv] ?? "") : "";
  if (gateway && apiKey === "") throw new Error(`--gateway reads its key from $${keyEnv}, which is not set`);
  const listed = (arg(flags, "models") ?? "").split(",").map((item) => item.trim()).filter((item) => item !== "");
  const single = arg(flags, "model") ?? project.job.modelId;
  const models = gateway && listed.length > 0 ? listed : [single];

  let result: Awaited<ReturnType<typeof draftEpisode>> | null = null;
  for (let round = 1; round <= QUOTA_ROUNDS; round += 1) {
    const waits: number[] = [];
    let answered = !gateway;
    for (const [index, modelId] of models.entries()) {
      const generate: GenerateFn | undefined = gateway
        ? (request) =>
            generateJsonChat({
              host: gateway,
              apiKey,
              model: request.model,
              system: request.system,
              prompt: request.prompt,
              maxTokens: Math.max(request.numPredict * GATEWAY_TOKEN_MULTIPLIER, GATEWAY_MIN_TOKENS),
              idleMs: 90_000
            })
        : undefined;
      if (gateway) {
        const health = await generateJsonChat({
          host: gateway,
          apiKey,
          model: modelId,
          system: "Reply with exactly this JSON object and nothing else: {\"ok\":true}",
          prompt: "health check",
          maxTokens: 16,
          idleMs: 30_000,
          maxAttempts: 1
        }).catch((error: unknown) => {
          const wait = quotaWaitSeconds(error);
          if (wait !== null) waits.push(wait);
          console.error(`model ${index + 1}/${models.length} ${modelId} preflight failed: ${error instanceof Error ? error.message : String(error)}`);
          return null;
        });
        if (!health) continue;
        answered = true;
        console.error(`model ${index + 1}/${models.length} ${modelId} preflight ok in ${health.seconds.toFixed(1)}s`);
      }
      result = await draftEpisode({
        job: project.job,
        sources: sources.sources,
        host,
        modelId,
        ...(generate ? { generate, segmentAttempts: 3 } : {}),
        onProgress: (line) => console.error(line)
      });
      if (result.ok) break;
      if (index + 1 < models.length) {
        console.error(`draft with ${modelId} rejected with ${result.problems.length} problem(s), trying the next model`);
      }
    }
    // a 429 on every route is one shared bucket, so the only recovery is the reset window rather than another model
    if (answered || result !== null || round === QUOTA_ROUNDS || waits.length === 0) break;
    const seconds = Math.max(...waits) + 30;
    console.error(`free-tier quota exhausted on all ${models.length} gateway models; waiting ${Math.ceil(seconds / 60)} min for the reset`);
    await new Promise((resolve) => setTimeout(resolve, seconds * 1000));
  }
  if (!result) throw new Error("no model in the chain answered the preflight");
  await writeJson(out, { ok: result.ok, problems: result.problems, outline: result.outline, script: result.script, calls: result.calls, totals: result.totals });
  console.error(`${result.ok ? "draft ok" : "draft rejected"}: ${out}`);
  console.log(out);
}

async function loadNarration(dir: string, script: DraftScript): Promise<{ manifestPath: string; manifest: NarrationManifest } | null> {
  const manifestPath = join(dir, "manifest.json");
  const manifest = JSON.parse((await readFile(manifestPath, "utf8").catch(() => "")) || "null") as NarrationManifest | null;
  if (!manifest || manifest.sampleRate !== 24000 || !Array.isArray(manifest.utterances) || manifest.utterances.length === 0) return null;
  for (const item of manifest.utterances) {
    const info = await stat(join(dir, item.file)).catch(() => null);
    if (!info || info.size !== 44 + item.samples * 2) return null;
  }
  try {
    timelineFromManifest(manifest, script, RATES);
  } catch {
    return null;
  }
  return { manifestPath, manifest };
}

async function commandRun(flags: string[]): Promise<void> {
  const projectPath = arg(flags, "project");
  if (!projectPath) throw new Error("run needs --project");
  const project = ProjectSchema.parse(JSON.parse(await readFile(projectPath, "utf8")));
  const jobDir = arg(flags, "work") ?? join(ROOT, "work", `${project.job.topic.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`);
  const reuseScenes = flags.includes("--reuse-scenes");
  await mkdir(join(jobDir, "narration"), { recursive: true });

  const script = project.script;
  const evidence = validateEvidence(project.sources);
  const ledger = withReviews(script.claims, project.reviews);
  const claims = validateClaims(ledger.claims, evidence.sources);
  const licenses = validateLicenses(project.licenses);
  const ungrounded = checkScriptClaims(script, script.claims.map((claim) => claim.id)).map((message) => ({ code: "ungrounded-claim", message }));
  const gate = exportGate({ claims: claims.claims, licenses: licenses.licenses });
  const snapshots = await verifySnapshots(evidence.sources, async (path) => (await digestFile(path)).sha256);
  const rejected = [...evidence.problems, ...ledger.problems, ...claims.problems, ...licenses.problems, ...snapshots, ...ungrounded];
  if (!gate.ready || rejected.length > 0) {
    await writeJson(join(jobDir, "blocked.json"), { blockers: gate.blockers, warnings: gate.warnings, rejected });
    throw new Error(`export blocked by ${[...gate.blockers.map((blocker) => blocker.code), ...rejected.map((problem) => problem.code)].join(", ")}`);
  }

  const timings: Record<string, number> = {};
  const stage = async <T>(name: string, work: () => Promise<T>): Promise<T> => {
    const started = Date.now();
    try {
      return await work();
    } finally {
      timings[name] = Math.round(((Date.now() - started) / 1000) * 10) / 10;
    }
  };

  const request = narrationRequest(script, project.narration);
  const narrationDir = join(jobDir, "narration");
  const narration = await stage("narration", async () => (reuseScenes ? await loadNarration(narrationDir, script) : null) ?? (await synthesizeNarration({
    python: join(ROOT, ".venv", "Scripts", "python.exe"),
    script: join(ROOT, "python", "narrate.py"),
    model: join(ROOT, "models", "kokoro", "kokoro-v1.0.onnx"),
    voices: join(ROOT, "models", "kokoro", "voices-v1.0.bin"),
    outDir: narrationDir,
    request
  })));

  const utterances = narration.manifest.utterances.map((item) => ({ id: item.id, file: item.file, samples: item.samples, text: item.text }));
  const compiled = await stage("timeline", () => compileScenes(script, narration.manifest));
  const pauseMap: Record<string, number> = {};
  for (const item of compiled.timeline.utterances) pauseMap[item.id] = item.pauseAfterSamples;
  const master = await stage("masterAudio", () => buildMasterAudio({ dir: join(jobDir, "narration"), utterances, pausesAfter: pauseMap }));

  const rendered: RenderedScene[] = [];
  const framesReused = { count: 0 };
  await stage("scenes", async () => {
    for (const scene of compiled.scenes) {
      const sceneDir = join(jobDir, "scenes", scene.id);
      await mkdir(sceneDir, { recursive: true });
      const cached = reuseScenes ? await readRenderedScene(scene, sceneDir, STYLE) : null;
      if (cached) framesReused.count += cached.frameCount;
      rendered.push(cached ?? (await renderScene({ scene, dir: sceneDir, style: STYLE })));
    }
    return rendered;
  });

  const chapters = chaptersFromTimeline(compiled.timeline, script);
  const exportDir = join(jobDir, "exports");
  const outputName = `${script.title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.mp4`;
  const muxed = await stage("mux", () => muxExport({ dir: exportDir, scenes: rendered, masterAudio: master, timeline: compiled.timeline, chapters, frameRate: RATES.frameRate, outputName }));
  const thumbnail = await stage("thumbnail", () => writeThumbnail({
    scenes: compiled.scenes,
    atFrame: Math.round(compiled.timeline.totalFrames * 0.35),
    dir: exportDir,
    style: STYLE
  }));

  const captions = captionsFor(compiled.timeline);
  await writeFile(join(exportDir, `${outputName}.srt`), captions, "utf8");
  await writeJson(join(exportDir, "chapters.json"), chapters.map((chapter) => ({ ...chapter, timestamp: timestamp(chapter.startSeconds) })));
  await writeJson(join(exportDir, "citations.json"), evidence.sources.map((source) => ({ id: source.id, publisher: source.publisher, title: source.title, url: source.url ?? null, retrievedAt: source.retrievedAt, snapshotHash: source.snapshotHash })));
  await writeJson(join(exportDir, "licenses.json"), licenses.licenses);
  await writeJson(
    join(exportDir, "provenance.json"),
    provenanceManifest({
      job: { id: outputName, revision: 1, title: script.title, category: project.job.category, targetSeconds: project.job.targetSeconds },
      writer: { provider: "imported-reviewed-script", modelId: "none", digest: "none", seed: 0 },
      narrator: { engine: "kokoro-onnx", version: "0.6.1", modelSha256: (await readJson<{ assets: { file: string; sha256: string }[] }>(join(ROOT, "models", "kokoro", "assets.json"))).assets.find((asset) => asset.file === "kokoro-v1.0.onnx")?.sha256 ?? "", voice: project.narration.voice, speed: project.narration.speed },
      renderer: { engine: "svg-deterministic", versions: { rasterizer: "@resvg/resvg-js", assembler: "ffmpeg" }, toolchainHash: "0".repeat(64) },
      timeline: compiled.timeline,
      sourceIds: evidence.sources.map((source) => source.id),
      licenses: licenses.licenses.map((license) => ({ id: license.id, licenseId: license.licenseId, artifactHash: license.artifactHash }))
    })
  );
  const description = [
    script.title,
    "",
    chapters.map((chapter) => `${timestamp(chapter.startSeconds)} ${chapter.title}`).join("\n"),
    "",
    "Sources:",
    ...evidence.sources.map((source) =>
      `- ${source.publisher}: ${source.title}${source.url?.startsWith("http") ? ` — ${source.url}` : ` — recorded at ${source.locator}`}`
    ),
    "",
    `Narrated with the local Kokoro-82M speech model (Apache-2.0). Animated with original vector scenes rendered deterministically. No third-party music.`
  ].join("\n");
  await writeFile(join(exportDir, "description.txt"), `${description}\n`, "utf8");

  const report = {
    ok: muxed.problems.length === 0,
    video: muxed.path,
    sha256: muxed.sha256,
    bytes: muxed.bytes,
    durationSeconds: compiled.timeline.masterDurationSeconds,
    narrationSeconds: master.seconds,
    totalFrames: muxed.expectedFrames,
    thumbnail,
    scenes: rendered.map((scene) => ({ id: scene.sceneId, frames: scene.frameCount, sha256: scene.sha256 })),
    timings: { ...timings, framesReused: framesReused.count },
    problems: muxed.problems,
    gate: { blockers: gate.blockers, warnings: gate.warnings }
  };
  await writeJson(join(jobDir, "report.json"), report);
  console.log(JSON.stringify(report, null, 2));
}

async function commandVerify(flags: string[]): Promise<void> {
  const path = arg(flags, "path");
  if (!path) throw new Error("verify needs --path");
  const { probeJson } = await import("./run.ts");
  const { verifyExport } = await import("./export.ts");
  const probe = (await probeJson(path, ["-show_entries", "stream=index,codec_type,codec_name,avg_frame_rate,nb_frames,sample_rate", "-show_entries", "format=duration,nb_streams"])) as never;
  const expectedSeconds = Number(process.env.EXPECTED_SECONDS ?? 0);
  const expectedFrames = Number(process.env.EXPECTED_FRAMES ?? 0);
  const result = verifyExport({
    probe,
    expected: {
      durationSeconds: expectedSeconds,
      frameRate: Number(process.env.EXPECTED_FPS ?? 30),
      totalFrames: expectedFrames,
      sampleRate: Number(process.env.EXPECTED_SAMPLE_RATE ?? 48000),
      videoStreams: 1,
      audioStreams: 1
    },
    distinctFrameDigests: Number(process.env.EXPECTED_DISTINCT ?? 1000),
    sampledFrames: Number(process.env.EXPECTED_SAMPLED ?? 1000)
  });
  console.log(JSON.stringify(result, null, 2));
}

if (import.meta.main) {
  const flags = process.argv.slice(2);
  const command = flags[0];
  try {
    if (command === "draft") await commandDraft(flags);
    else if (command === "run") await commandRun(flags);
    else if (command === "verify") await commandVerify(flags);
    else console.log("usage: node src/cli.ts run --project <file> | draft --project <file> | verify --path <file>");
  } catch (error) {
    console.error(`${command ?? "cli"} failed: ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  }
}
