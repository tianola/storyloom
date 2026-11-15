import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { createReadStream, mkdirSync } from "node:fs";
import { readFile, readdir, stat } from "node:fs/promises";
import { extname, join, resolve, sep } from "node:path";
import { JobStore, STAGES, type Stage } from "../jobs.ts";
import { ProjectSchema } from "../cli.ts";

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".mp4": "video/mp4",
  ".srt": "text/plain; charset=utf-8",
  ".png": "image/png",
  ".txt": "text/plain; charset=utf-8"
};

export type Episode = {
  name: string;
  topic: string;
  category: string;
  targetSeconds: number;
  chapters: number;
  utterances: number;
  path: string;
  exported: boolean;
  mediaBase: string;
  report?: Record<string, unknown> | undefined;
};

export type Runner = {
  episode: Episode;
  jobId: string;
  state: "idle" | "running" | "done" | "failed" | "cancelled" | "interrupted";
  pid?: number | undefined;
  log: string[];
  report?: Record<string, unknown> | undefined;
  problem?: string | undefined;
};

export function episodesIn(root: string): Promise<Episode[]> {
  const dir = join(root, "topics");
  return readdir(dir).then(async (names) => {
    const found: Episode[] = [];
    for (const name of names.filter((file) => file.endsWith(".project.json"))) {
      const path = join(dir, name);
      const summary = (topic: string, category: string, targetSeconds: number, chapters: number, utterances: number): Episode => {
        const mediaBase = `/media/${slug(topic)}/exports/`;
        return { name, topic, category, targetSeconds, chapters, utterances, path, exported: false, mediaBase };
      };
      try {
        const project = ProjectSchema.parse(JSON.parse(await readFile(path, "utf8")));
        const episode = summary(project.job.topic, project.job.category, project.job.targetSeconds, project.script.chapters.length, project.script.chapters.reduce((total, chapter) => total + chapter.utterances.length, 0));
        const report = await readJson(join(root, "work", slug(episode.topic), "report.json"));
        if (report) {
          episode.exported = true;
          episode.report = report;
        }
        found.push(episode);
      } catch (error) {
        found.push(summary(`${name} is not a valid package`, "invalid", 0, 0, 0));
        console.warn(`${name}: ${(error as Error).message.slice(0, 200)}`);
      }
    }
    return found;
  });
}

function within(root: string, requested: string): string | null {
  const target = resolve(root, `.${requested}`);
  return target === root || target.startsWith(root + sep) ? target : null;
}

export class Studio {
  private readonly runners = new Map<string, Runner>();
  private readonly root: string;
  private readonly store: JobStore;

  constructor(root: string, store: JobStore) {
    this.root = root;
    this.store = store;
  }

  list(): Runner[] {
    return Array.from(this.runners.values());
  }

  /**
   * A run whose worker died leaves a `running` row with an expired lease. Releasing it on start is what makes the
   * difference between "the page says it is still rendering" and a job the operator can actually restart.
   */
  recover(now = Date.now()): { jobId: string; from: string; to: string }[] {
    const moved = this.store.recover({ now });
    for (const entry of moved) {
      const runner = this.runners.get(entry.jobId);
      if (runner && runner.state === "running") runner.state = "interrupted";
    }
    return moved;
  }

  async progress(runner: Runner): Promise<{ stage: Stage | null; scenes: string[]; frames: number; done: boolean }> {
    const work = join(this.root, "work", slug(runner.episode.topic));
    const scenesDir = join(work, "scenes");
    const scenes: string[] = [];
    let frames = 0;
    try {
      for (const id of await readdir(scenesDir)) {
        try {
          const files = await readdir(join(scenesDir, id, "frames"));
          scenes.push(id);
          frames += files.filter((file) => file.endsWith(".png")).length;
        } catch {
          scenes.push(id);
        }
      }
    } catch {
      /* nothing rendered yet */
    }
    const stage: Stage | null = runner.state === "running" ? (scenes.length > 0 ? "scenes" : "narration") : null;
    return { stage, scenes, frames, done: runner.state === "done" };
  }

  async start(episode: Episode): Promise<Runner> {
    const existing = this.runners.get(episode.name);
    if (existing && existing.state === "running") return existing;
    const project = ProjectSchema.parse(JSON.parse(await readFile(episode.path, "utf8")));
    const created = this.store.createJob(
      { ...project.job, modelId: project.job.modelId },
      { package: episode.name, topic: project.job.topic, claims: project.script.claims.length }
    );
    const runner: Runner = { episode, jobId: created.id, state: "running", log: [] };
    this.runners.set(episode.name, runner);
    const lease = this.store.claimNext({ workerId: `studio-${process.pid}`, now: Date.now() });
    if (lease && lease.jobId !== created.id) console.warn(`claimNext handed out ${lease.jobId} instead of ${created.id}`);
    this.store.recordEvent(created.id, "start", { package: episode.name });
    const child = spawn(process.execPath, [join(this.root, "src", "cli.ts"), "run", "--project", episode.path], {
      cwd: this.root,
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"]
    });
    runner.pid = child.pid;
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => runner.log.push(...chunk.split("\n").filter(Boolean).slice(-40)));
    child.stderr.on("data", (chunk: string) => runner.log.push(...chunk.split("\n").filter(Boolean).slice(-40)));
    child.on("error", (error) => this.finish(runner, "failed", undefined, error.message));
    child.on("close", async (code) => {
      if (runner.state === "cancelled") return;
      const reportPath = join(this.root, "work", slug(runner.episode.topic), "report.json");
      const report = code === 0 ? await readJson(reportPath) : undefined;
      const ok = code === 0 && report && report.ok === true;
      this.finish(runner, ok ? "done" : "failed", report, ok ? undefined : `exit ${code}${report ? ` with problems ${JSON.stringify(report.problems)}` : ""}`);
    });
    return runner;
  }

  private finish(runner: Runner, state: Runner["state"], report?: Record<string, unknown>, problem?: string) {
    runner.state = state;
    runner.report = report;
    runner.problem = problem;
    if (state === "done" && report) {
      const hash = createHash("sha256").update(JSON.stringify(report)).digest("hex");
      for (let stage = 0; stage < STAGES.length; stage += 1) {
        const lease = this.store.claimNext({ workerId: `studio-${process.pid}`, now: Date.now() });
        if (!lease || lease.jobId !== runner.jobId) break;
        this.store.completeStage({ ...lease, outputHash: hash, now: Date.now() });
      }
    }
    this.store.recordEvent(runner.jobId, state, { problem, video: report?.video ?? null });
  }

  async cancel(name: string): Promise<boolean> {
    const runner = this.runners.get(name);
    if (!runner || runner.state !== "running" || !runner.pid) return false;
    this.store.requestCancel(runner.jobId, "cancelled from the browser UI");
    runner.state = "cancelled";
    const killed = spawn("taskkill", ["/PID", String(runner.pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
    await new Promise<void>((resolveExit) => killed.on("close", () => resolveExit()));
    this.store.markCancelled(runner.jobId);
    this.store.recordEvent(runner.jobId, "cancelled", { pid: runner.pid });
    return true;
  }

  workDirOf(episode: Episode): string {
    return join(this.root, "work", slug(episode.topic));
  }
}

function slug(topic: string): string {
  return topic.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

async function readJson(path: string): Promise<Record<string, unknown> | undefined> {
  try {
    return JSON.parse(await readFile(path, "utf8")) as Record<string, unknown>;
  } catch {
    return undefined;
  }
}

export function handler(root: string, studio: Studio) {
  return async (req: IncomingMessage, res: ServerResponse) => {
    const url = new URL(req.url ?? "/", "http://127.0.0.1");
    const send = (status: number, body: unknown, type = "application/json; charset=utf-8") => {
      res.writeHead(status, { "content-type": type, "cache-control": "no-store" });
      res.end(typeof body === "string" ? body : JSON.stringify(body));
    };
    try {
      if (url.pathname.startsWith("/media/")) {
        const workRoot = join(root, "work");
        const target = within(workRoot, decodeURIComponent(url.pathname.slice("/media".length)));
        if (!target || !target.startsWith(workRoot + sep)) return send(403, { error: "outside the work directory" });
        const info = await stat(target).catch(() => null);
        if (!info?.isFile()) return send(404, { error: "not found" });
        const type = MIME[extname(target)] ?? "application/octet-stream";
        const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range ?? "");
        if (!range) {
          res.writeHead(200, { "content-type": type, "content-length": info.size, "accept-ranges": "bytes" });
          const whole = createReadStream(target);
          res.on("close", () => whole.destroy());
          whole.pipe(res);
          return undefined;
        }
        const start = range[1] === "" ? Math.max(0, info.size - Number(range[2])) : Number(range[1]);
        const end = range[1] !== "" && range[2] !== "" ? Math.min(info.size - 1, Number(range[2])) : info.size - 1;
        if (!Number.isInteger(start) || start >= info.size || end < start) {
          res.writeHead(416, { "content-range": `bytes */${info.size}` });
          res.end();
          return undefined;
        }
        res.writeHead(206, {
          "content-type": type,
          "content-length": end - start + 1,
          "content-range": `bytes ${start}-${end}/${info.size}`,
          "accept-ranges": "bytes"
        });
        const stream = createReadStream(target, { start, end });
        res.on("close", () => stream.destroy());
        stream.pipe(res);
        return undefined;
      }
      if (url.pathname === "/api/episodes") return send(200, await episodesIn(root));
      if (url.pathname === "/api/jobs" && req.method === "GET") return send(200, studio.list());
      if (url.pathname === "/api/jobs" && req.method === "POST") {
        const body = (await readBody(req)) as { episode?: string };
        const episodes = await episodesIn(root);
        const episode = episodes.find((candidate) => candidate.name === body.episode);
        if (!episode) return send(404, { error: `unknown episode ${String(body.episode)}` });
        return send(202, await studio.start(episode));
      }
      const cancel = url.pathname.match(/^\/api\/jobs\/([^/]+)\/cancel$/);
      if (cancel && req.method === "POST") {
        const done = await studio.cancel(decodeURIComponent(cancel[1]!));
        return send(done ? 200 : 409, { cancelled: done });
      }
      const progress = url.pathname.match(/^\/api\/jobs\/([^/]+)\/progress$/);
      if (progress) {
        const runner = studio.list().find((candidate) => candidate.episode.name === decodeURIComponent(progress[1]!));
        if (!runner) return send(404, { error: "no such job" });
        return send(200, {
          ...runner,
          mediaBase: `/media/${slug(runner.episode.topic)}/exports/`,
          workBase: `/media/${slug(runner.episode.topic)}/`,
          ...(await studio.progress(runner))
        });
      }
      if (url.pathname === "/" || url.pathname === "/index.html") {
        return send(200, await readFile(join(root, "public", "index.html"), "utf8"), MIME[".html"]);
      }
      return send(404, { error: "not found" });
    } catch (error) {
      return send(500, { error: (error as Error).message.slice(0, 400) });
    }
  };
}

function readBody(req: IncomingMessage): Promise<unknown> {
  return new Promise((resolveBody, rejectBody) => {
    let text = "";
    req.on("data", (chunk: Buffer) => {
      text += chunk.toString("utf8");
      if (text.length > 65_536) rejectBody(new RangeError("body too large"));
    });
    req.on("end", () => {
      try {
        resolveBody(JSON.parse(text || "{}"));
      } catch (error) {
        rejectBody(error);
      }
    });
    req.on("error", rejectBody);
  });
}

export function startServer(input: { root: string; host?: string; port?: number }) {
  const host = input.host ?? "127.0.0.1";
  if (host !== "127.0.0.1" && host !== "localhost" && host !== "::1") {
    throw new RangeError(`refusing to bind outside loopback: ${host}`);
  }
  mkdirSync(join(input.root, "data"), { recursive: true });
  const store = new JobStore(join(input.root, "data", "jobs.db"));
  const studio = new Studio(input.root, store);
  const recovered = studio.recover();
  if (recovered.length > 0) console.error(`studio: released ${recovered.length} interrupted job(s) from a previous run`);
  const server = createServer(handler(input.root, studio));
  server.listen(input.port ?? 8787, host);
  return { server, store, studio, recovered };
}

if (import.meta.main) {
  const root = new URL("../..", import.meta.url).pathname.replace(/^\//, "");
  const { server } = startServer({ root, host: process.env.HOST ?? "127.0.0.1", port: Number(process.env.PORT ?? 8787) });
  console.log(`studio listening on http://127.0.0.1:${process.env.PORT ?? 8787}`);
  const shutdown = () => server.close(() => process.exit(0));
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}
