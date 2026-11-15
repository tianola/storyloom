import { DatabaseSync } from "node:sqlite";
import { randomUUID } from "node:crypto";
import type { JobBrief } from "./contracts.ts";

export const STAGES = ["evidence", "script", "narration", "timeline", "scenes", "mux", "verify"] as const;
export type Stage = (typeof STAGES)[number];

export type JobState = "queued" | "running" | "needs_review" | "cancel_requested" | "cancelled" | "interrupted" | "failed" | "completed";

export type Lease = { jobId: string; workerId: string; fencingToken: number; stage: Stage };
type Row = Record<string, string | number | null>;

const DEFAULT_LEASE_MS = 30_000;

export class JobStore {
  #db: DatabaseSync;

  constructor(path: string) {
    this.#db = new DatabaseSync(path);
    this.#db.exec(`
      create table if not exists jobs (
        id text primary key,
        brief text not null,
        state text not null,
        current_stage text,
        revision integer not null,
        lease_worker text,
        lease_token integer not null default 0,
        lease_expires_at integer,
        cancel_reason text,
        error text,
        created_at integer not null,
        updated_at integer not null
      );
      create table if not exists revisions (
        id text primary key,
        job_id text not null references jobs(id) on delete cascade,
        number integer not null,
        content text not null,
        created_by text not null,
        created_at integer not null,
        approved_by text,
        approved_at integer
      );
      create table if not exists stage_runs (
        id text primary key,
        job_id text not null references jobs(id) on delete cascade,
        stage text not null,
        fencing_token integer not null,
        output_hash text not null,
        started_at integer not null,
        finished_at integer not null
      );
      create table if not exists artifacts (
        id text primary key,
        job_id text not null references jobs(id) on delete cascade,
        stage text not null,
        inputs_hash text not null,
        dependency_hash text not null,
        toolchain_hash text not null,
        path text not null,
        sha256 text not null,
        bytes integer not null,
        created_at integer not null
      );
      create table if not exists events (
        id text primary key,
        job_id text not null references jobs(id) on delete cascade,
        sequence integer not null,
        type text not null,
        payload text not null,
        created_at integer not null
      );
      create unique index if not exists events_sequence on events(job_id, sequence);
      create unique index if not exists artifacts_cache on artifacts(job_id, stage, inputs_hash, dependency_hash, toolchain_hash);
      create index if not exists jobs_claim on jobs(state, created_at);
    `);
  }

  createJob(brief: JobBrief, content: unknown): { id: string; state: JobState; revision: number } {
    const id = randomUUID();
    const now = Date.now();
    this.#db
      .prepare("insert into jobs (id, brief, state, current_stage, revision, created_at, updated_at) values (?, ?, 'queued', 'evidence', 1, ?, ?)")
      .run(id, JSON.stringify(brief), now, now);
    this.#insertRevision(id, 1, content, brief.topic, now);
    this.#event(id, "job.created", { brief, revision: 1 });
    return { id, state: "queued", revision: 1 };
  }

  claimNext(input: { workerId: string; now: number; leaseMs?: number }): Lease | null {
    const leaseMs = input.leaseMs ?? DEFAULT_LEASE_MS;
    const row = this.#db
      .prepare("select id from jobs where state = 'queued' and cancel_reason is null order by created_at, id limit 1")
      .get() as Row | undefined;
    if (!row || typeof row.id !== "string") return null;
    const jobId = row.id;
    const changes = this.#db
      .prepare(
        `update jobs set state = 'running', lease_worker = ?, lease_token = lease_token + 1, lease_expires_at = ?, updated_at = ?
         where id = ? and state = 'queued' and cancel_reason is null`
      )
      .run(input.workerId, input.now + leaseMs, input.now, jobId).changes;
    if (changes !== 1) return null;
    const claimed = this.#db.prepare("select lease_token, current_stage from jobs where id = ?").get(jobId) as Row;
    const lease = {
      jobId,
      workerId: input.workerId,
      fencingToken: Number(claimed.lease_token),
      stage: String(claimed.current_stage) as Stage
    };
    this.#event(jobId, "job.claimed", lease);
    return lease;
  }

  renew(lease: Lease, now: number, leaseMs = DEFAULT_LEASE_MS): boolean {
    return this.#withLease(lease, (statement) => statement.run(now + leaseMs, now, lease.jobId, lease.workerId, lease.fencingToken).changes === 1, "lease_expires_at = ?, updated_at = ?");
  }

  completeStage(input: Lease & { stage: Stage; outputHash: string; now: number }): boolean {
    const row = this.#leaseRow(input);
    if (!row || row.state !== "running" || row.current_stage !== input.stage) return false;
    if (row.cancel_reason !== null) {
      this.markCancelled(input.jobId);
      return false;
    }
    const now = input.now;
    this.#db
      .prepare("insert into stage_runs (id, job_id, stage, fencing_token, output_hash, started_at, finished_at) values (?, ?, ?, ?, ?, ?, ?)")
      .run(randomUUID(), input.jobId, input.stage, input.fencingToken, input.outputHash, now, now);
    const index = STAGES.indexOf(input.stage);
    const next: Stage | null = index === -1 || index === STAGES.length - 1 ? null : STAGES[index + 1] ?? null;
    this.#db
      .prepare("update jobs set state = ?, current_stage = ?, lease_worker = null, lease_expires_at = null, updated_at = ? where id = ?")
      .run(next === null ? "completed" : "queued", next, now, input.jobId);
    this.#event(input.jobId, next === null ? "job.completed" : "stage.completed", {
      stage: input.stage,
      nextStage: next,
      fencingToken: input.fencingToken,
      outputHash: input.outputHash
    });
    return true;
  }

  failStage(input: Lease & { stage: Stage; error: string; now: number }): boolean {
    const row = this.#leaseRow(input);
    if (!row || row.state !== "running") return false;
    this.#db
      .prepare("update jobs set state = 'failed', error = ?, lease_worker = null, lease_expires_at = null, updated_at = ? where id = ?")
      .run(input.error, input.now, input.jobId);
    this.#event(input.jobId, "stage.failed", { stage: input.stage, error: input.error });
    return true;
  }

  recover(input: { now: number; leaseMs?: number }): { jobId: string; from: JobState; to: JobState }[] {
    void input.leaseMs;
    const rows = this.#db
      .prepare("select id from jobs where state = 'running' and lease_expires_at is not null and lease_expires_at <= ?")
      .all(input.now) as Row[];
    return rows.map((row) => {
      const jobId = String(row.id);
      this.#db.prepare("update jobs set state = 'interrupted', lease_worker = null, lease_expires_at = null, updated_at = ? where id = ?").run(input.now, jobId);
      this.#event(jobId, "job.interrupted", { reason: "lease expired" });
      return { jobId, from: "running" as JobState, to: "interrupted" as JobState };
    });
  }

  resume(jobId: string, input: { now: number }): { state: JobState } {
    const row = this.#job(jobId);
    if (!row) return { state: "failed" };
    const state = String(row.state) as JobState;
    if (state !== "interrupted" && state !== "failed" && state !== "cancelled") return { state };
    const nextStage = (row.current_stage as Stage | null) ?? STAGES[0];
    this.#db.prepare("update jobs set state = 'queued', current_stage = ?, cancel_reason = null, updated_at = ? where id = ?").run(nextStage, input.now, jobId);
    this.#event(jobId, "job.resumed", { stage: nextStage });
    return { state: "queued" };
  }

  requestCancel(jobId: string, reason: string): boolean {
    const changes = this.#db
      .prepare("update jobs set cancel_reason = ?, updated_at = ? where id = ? and state in ('queued','running','needs_review') and cancel_reason is null")
      .run(reason, Date.now(), jobId).changes;
    if (changes !== 1) return false;
    this.#event(jobId, "job.cancel_requested", { reason });
    return true;
  }

  cancelRequested(jobId: string): boolean {
    return this.#job(jobId)?.cancel_reason !== null;
  }

  markCancelled(jobId: string): boolean {
    const changes = this.#db
      .prepare("update jobs set state = 'cancelled', lease_worker = null, lease_expires_at = null, updated_at = ? where id = ? and state not in ('completed','cancelled')")
      .run(Date.now(), jobId).changes;
    if (changes !== 1) return false;
    this.#event(jobId, "job.cancelled", {});
    return true;
  }

  approve(jobId: string): { state: JobState } {
    return this.resume(jobId, { now: Date.now() });
  }

  addRevision(jobId: string, content: unknown, createdBy: string): { number: number } {
    const latest = this.#db.prepare("select max(number) as number from revisions where job_id = ?").get(jobId) as Row;
    const number = Number(latest.number ?? 0) + 1;
    const now = Date.now();
    this.#insertRevision(jobId, number, content, createdBy, now);
    this.#db.prepare("update jobs set state = 'needs_review', revision = ?, updated_at = ? where id = ?").run(number, now, jobId);
    this.#event(jobId, "revision.added", { number, createdBy });
    return { number };
  }

  approveRevision(jobId: string, number: number, reviewer: string): boolean {
    const now = Date.now();
    const changes = this.#db
      .prepare("update revisions set approved_by = ?, approved_at = ? where job_id = ? and number = ?")
      .run(reviewer, now, jobId, number).changes;
    if (changes !== 1) return false;
    const row = this.#job(jobId);
    if (row && Number(row.revision) === number) {
      this.#db.prepare("update jobs set state = 'queued', updated_at = ? where id = ? and state = 'needs_review'").run(now, jobId);
    }
    this.#event(jobId, "revision.approved", { number, reviewer });
    return true;
  }

  recordArtifact(input: {
    jobId: string;
    stage: Stage;
    inputsHash: string;
    dependencyHash: string;
    toolchainHash: string;
    path: string;
    sha256: string;
    bytes: number;
  }): void {
    this.#db
      .prepare(
        `insert into artifacts (id, job_id, stage, inputs_hash, dependency_hash, toolchain_hash, path, sha256, bytes, created_at)
         values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
         on conflict(job_id, stage, inputs_hash, dependency_hash, toolchain_hash) do update set path = excluded.path, sha256 = excluded.sha256, bytes = excluded.bytes, created_at = excluded.created_at`
      )
      .run(randomUUID(), input.jobId, input.stage, input.inputsHash, input.dependencyHash, input.toolchainHash, input.path, input.sha256, input.bytes, Date.now());
  }

  cachedArtifact(jobId: string, key: { stage: Stage; inputsHash: string; dependencyHash: string; toolchainHash: string }): { path: string; sha256: string; bytes: number } | null {
    const row = this.#db
      .prepare("select path, sha256, bytes from artifacts where job_id = ? and stage = ? and inputs_hash = ? and dependency_hash = ? and toolchain_hash = ?")
      .get(jobId, key.stage, key.inputsHash, key.dependencyHash, key.toolchainHash) as Row | undefined;
    if (!row) return null;
    return { path: String(row.path), sha256: String(row.sha256), bytes: Number(row.bytes) };
  }

  recordEvent(jobId: string, type: string, payload: unknown): void {
    this.#event(jobId, type, payload);
  }

  eventsAfter(jobId: string, sequence: number): { sequence: number; type: string; payload: unknown }[] {
    const rows = this.#db.prepare("select sequence, type, payload from events where job_id = ? and sequence > ? order by sequence").all(jobId, sequence) as Row[];
    return rows.map((row) => ({ sequence: Number(row.sequence), type: String(row.type), payload: JSON.parse(String(row.payload)) as unknown }));
  }

  stateOf(jobId: string): JobState | null {
    const row = this.#job(jobId);
    return row ? (String(row.state) as JobState) : null;
  }

  stageFor(jobId: string): Stage | null {
    const row = this.#job(jobId);
    return row && row.current_stage !== null ? (String(row.current_stage) as Stage) : null;
  }

  listJobs(): { id: string; state: JobState; stage: Stage | null; revision: number }[] {
    const rows = this.#db.prepare("select id, state, current_stage, revision from jobs order by created_at desc, id").all() as Row[];
    return rows.map((row) => ({
      id: String(row.id),
      state: String(row.state) as JobState,
      stage: row.current_stage === null ? null : (String(row.current_stage) as Stage),
      revision: Number(row.revision)
    }));
  }

  close(): void {
    this.#db.close();
  }

  #job(jobId: string): Row | undefined {
    return this.#db.prepare("select id, state, current_stage, revision, cancel_reason from jobs where id = ?").get(jobId) as Row | undefined;
  }

  #leaseRow(lease: Lease): Row | undefined {
    const row = this.#db
      .prepare("select state, current_stage, cancel_reason, lease_worker, lease_token from jobs where id = ?")
      .get(lease.jobId) as Row | undefined;
    if (!row) return undefined;
    if (String(row.lease_worker) !== lease.workerId || Number(row.lease_token) !== lease.fencingToken) return undefined;
    return row;
  }

  #withLease(lease: Lease, run: (statement: ReturnType<DatabaseSync["prepare"]>) => boolean, assignment: string): boolean {
    const statement = this.#db.prepare(`update jobs set ${assignment} where id = ? and lease_worker = ? and lease_token = ? and state = 'running'`);
    return run(statement);
  }

  #insertRevision(jobId: string, number: number, content: unknown, createdBy: string, now: number): void {
    this.#db
      .prepare("insert into revisions (id, job_id, number, content, created_by, created_at) values (?, ?, ?, ?, ?, ?)")
      .run(randomUUID(), jobId, number, JSON.stringify(content), createdBy, now);
  }

  #event(jobId: string, type: string, payload: unknown): void {
    const last = this.#db.prepare("select max(sequence) as sequence from events where job_id = ?").get(jobId) as Row;
    const sequence = Number(last.sequence ?? 0) + 1;
    this.#db
      .prepare("insert into events (id, job_id, sequence, type, payload, created_at) values (?, ?, ?, ?, ?, ?)")
      .run(randomUUID(), jobId, sequence, type, JSON.stringify(payload), Date.now());
  }
}
