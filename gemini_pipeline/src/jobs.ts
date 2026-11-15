import Database from 'better-sqlite3';

export interface JobRecord {
  id: string;
  type: 'NARRATE' | 'RENDER_BEAT';
  payload: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  attempts: number;
  max_attempts: number;
  error_log?: string | null;
  created_at: string;
  updated_at: string;
}

export class JobQueueClient {
  private db: Database.Database;

  constructor(dbPath: string = 'data/jobs.db') {
    this.db = new Database(dbPath, { timeout: 30000 });
    this.db.pragma('journal_mode = WAL');
    this.db.pragma('synchronous = NORMAL');
  }

  public enqueue(id: string, type: JobRecord['type'], payload: Record<string, unknown>, maxAttempts = 3): void {
    const stmt = this.db.prepare(
      `INSERT INTO jobs (id, type, payload, status, max_attempts) VALUES (?, ?, ?, 'PENDING', ?)`
    );
    stmt.run(id, type, JSON.stringify(payload), maxAttempts);
  }

  public getStatus(id: string): JobRecord | undefined {
    return this.db.prepare(`SELECT * FROM jobs WHERE id = ?`).get(id) as JobRecord | undefined;
  }

  public listByStatus(status: JobRecord['status']): JobRecord[] {
    return this.db.prepare(`SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC`).all(status) as JobRecord[];
  }

  public close(): void {
    this.db.close();
  }
}
