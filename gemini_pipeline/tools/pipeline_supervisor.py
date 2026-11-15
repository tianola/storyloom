import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from src.database import init_db, get_db_connection
from python.narrate import synthesize_narration
from tools.qc_episode import run_qc_checks
from tools.utils.retry import retry_with_backoff
from tools.utils.logger import get_logger

logger = get_logger("PipelineSupervisor")

class PipelineSupervisor:
    def __init__(self, blender_bin: str = "blender"):
        self.blender_bin = blender_bin
        init_db()

    def enqueue_job(self, job_type: str, payload: dict, max_attempts: int = 3) -> str:
        job_id = str(uuid.uuid4())
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO jobs (id, type, payload, status, max_attempts) VALUES (?, ?, ?, 'PENDING', ?)",
                (job_id, job_type, json.dumps(payload), max_attempts)
            )
        logger.info(f"Enqueued job {job_id} [{job_type}]")
        return job_id

    @retry_with_backoff(retries=2, initial_delay=2.0)
    def _run_blender_subprocess(self, payload: dict) -> str:
        output_dir = payload.get("output_dir", "output/frames")
        beat_id = payload.get("beat_id", "beat_001")
        cmd = [
            self.blender_bin,
            "--background",
            "--python", "tools/blender/render_worker.py",
            "--",
            "--payload", json.dumps(payload),
            "--output-dir", output_dir
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
        except FileNotFoundError:
            # Fallback to direct python execution if blender binary is not installed on host
            logger.warning("Blender binary not found; falling back to Python worker mode.")
            subprocess.run(
                ["python3", "tools/blender/render_worker.py", "--payload", json.dumps(payload), "--output-dir", output_dir],
                check=True, capture_output=True, text=True
            )
        return f"{output_dir}/{beat_id}.png"

    def process_job(self, job_row: dict):
        job_id = job_row["id"]
        job_type = job_row["type"]
        payload = json.loads(job_row["payload"])

        with get_db_connection() as conn:
            conn.execute(
                "UPDATE jobs SET status='RUNNING', attempts=attempts+1, updated_at=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), job_id)
            )

        try:
            artifacts = []
            if job_type == "NARRATE":
                res = synthesize_narration(
                    script_text=payload["text"],
                    output_audio_path=payload["output_path"],
                    voice_model=payload.get("voice_model", "default")
                )
                artifacts.append(res["audio_path"])
            elif job_type == "RENDER_BEAT":
                frame_path = self._run_blender_subprocess(payload)
                artifacts.append(frame_path)
            else:
                raise ValueError(f"Unknown job type: {job_type}")

            qc = run_qc_checks(artifacts)
            if not qc["passed"]:
                raise RuntimeError(f"QC Failed: {qc['failures']}")

            with get_db_connection() as conn:
                conn.execute(
                    "UPDATE jobs SET status='COMPLETED', updated_at=? WHERE id=?",
                    (datetime.now(timezone.utc).isoformat(), job_id)
                )
            logger.info(f"Job {job_id} completed and passed QC.")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            with get_db_connection() as conn:
                row = conn.execute("SELECT attempts, max_attempts FROM jobs WHERE id=?", (job_id,)).fetchone()
                new_status = "FAILED" if row["attempts"] >= row["max_attempts"] else "PENDING"
                conn.execute(
                    "UPDATE jobs SET status=?, error_log=?, updated_at=? WHERE id=?",
                    (new_status, str(e), datetime.now(timezone.utc).isoformat(), job_id)
                )

    def run_once(self):
        with get_db_connection() as conn:
            jobs = conn.execute("SELECT * FROM jobs WHERE status='PENDING' ORDER BY created_at ASC").fetchall()
        for job in jobs:
            self.process_job(dict(job))

    def run_forever(self, poll_interval: float = 2.0):
        logger.info("Pipeline Supervisor started in daemon mode.")
        while True:
            self.run_once()
            time.sleep(poll_interval)

if __name__ == "__main__":
    sup = PipelineSupervisor()
    sup.enqueue_job("NARRATE", {"text": "Welcome to the automated production pipeline.", "output_path": "output/audio/intro.wav"})
    sup.enqueue_job("RENDER_BEAT", {"beat_id": "beat_01", "output_dir": "output/frames"})
    sup.run_once()
