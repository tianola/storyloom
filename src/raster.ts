import { Worker } from "node:worker_threads";
import { cpus } from "node:os";
import { rasterize } from "./frames.ts";

export type RasterJob = { svg: string; width: number; height: number };

export function rasterPoolSize(requested?: number | undefined): number {
  const cores = Math.max(1, cpus().length);
  const value = requested ?? cores - 1;
  return Math.min(cores, Math.max(1, Math.floor(value)));
}

type Reply = { index: number; bytes?: Uint8Array; error?: string };
type Active = { resolve: (value: Uint8Array[]) => void; reject: (reason: Error) => void; out: (Uint8Array | undefined)[]; left: number };

export type RasterPool = {
  run(jobs: RasterJob[]): Promise<Uint8Array[]>;
  close(): Promise<void>;
};

/**
 * A standing set of rasterizer workers. Frames are independent, so each free worker takes the next
 * job and the PNG is handed back as soon as it is drawn; the caller writes it and lets it go.
 */
export function createRasterPool(options?: { concurrency?: number | undefined }): RasterPool {
  const size = rasterPoolSize(options?.concurrency);
  const workerUrl = new URL("./raster-worker.ts", import.meta.url);
  const workers: Worker[] = [];
  const free: number[] = [];
  const waiting: { job: RasterJob; index: number }[] = [];
  let failure = "";
  let closed = false;
  let active: Active | null = null;

  function fail(message: string): void {
    if (failure === "") failure = message;
    const current = active;
    active = null;
    current?.reject(new Error(`raster pool failed: ${message}`));
    for (const worker of workers.splice(0, workers.length)) void worker.terminate().catch(() => undefined);
    free.length = 0;
    waiting.length = 0;
  }

  function dispatch(slot: number): void {
    if (closed || failure !== "") return;
    const next = waiting.shift();
    const worker = workers[slot];
    if (!next || !worker) {
      if (!closed && failure === "") free.push(slot);
      return;
    }
    worker.postMessage({ index: next.index, svg: next.job.svg, width: next.job.width, height: next.job.height });
  }

  function spawn(slot: number): Worker {
    const worker = new Worker(workerUrl);
    worker.on("message", (reply: Reply) => {
      if (reply.error) {
        fail(`frame ${reply.index}: ${reply.error}`);
        return;
      }
      const current = active;
      if (current && current.out[reply.index] === undefined) {
        current.out[reply.index] = reply.bytes ?? new Uint8Array();
        current.left -= 1;
        if (current.left === 0) {
          active = null;
          current.resolve(current.out as Uint8Array[]);
        }
      }
      dispatch(slot);
    });
    worker.on("error", (error) => fail(error.message));
    worker.on("exit", (code) => {
      if (code !== 0 && !closed && failure === "") fail(`worker ${slot} exited with code ${code}`);
    });
    workers[slot] = worker;
    return worker;
  }

  function start(): void {
    if (workers.length > 0) return;
    for (let slot = 0; slot < size; slot += 1) {
      spawn(slot);
      free.push(slot);
    }
  }

  async function run(jobs: RasterJob[]): Promise<Uint8Array[]> {
    if (jobs.length === 0) return [];
    if (closed || failure !== "") throw new Error(`raster pool is closed${failure === "" ? "" : `: ${failure}`}`);
    if (jobs.length === 1) return [rasterize(jobs[0]!.svg, { width: jobs[0]!.width, height: jobs[0]!.height })];
    const out: (Uint8Array | undefined)[] = new Array<Uint8Array | undefined>(jobs.length).fill(undefined);
    return new Promise<Uint8Array[]>((resolve, reject) => {
      active = { resolve, reject, out, left: jobs.length };
      for (let index = 0; index < jobs.length; index += 1) waiting.push({ job: jobs[index]!, index });
      start();
      const slots = free.splice(0, free.length);
      for (const slot of slots) dispatch(slot);
    });
  }

  async function close(): Promise<void> {
    closed = true;
    const current = active;
    active = null;
    current?.reject(new Error("raster pool closed before the chunk finished"));
    const stopping = workers.splice(0, workers.length);
    await Promise.all(stopping.map((worker) => worker.terminate().catch(() => undefined)));
    free.length = 0;
    waiting.length = 0;
  }

  return { run, close };
}

export async function rasterizePool(jobs: RasterJob[], options?: { concurrency?: number | undefined }): Promise<Uint8Array[]> {
  const pool = createRasterPool(options);
  try {
    return await pool.run(jobs);
  } finally {
    await pool.close();
  }
}
