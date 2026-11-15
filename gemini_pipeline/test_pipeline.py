import os
import tempfile
import unittest
from tools.pipeline_supervisor import PipelineSupervisor
from src.database import get_db_connection

class TestProductionPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        os.environ["PIPELINE_DB_PATH"] = os.path.join(self.tmp_dir.name, "test_jobs.db")
        import src.database as db_mod
        db_mod.DB_PATH = os.environ["PIPELINE_DB_PATH"]
        self.supervisor = PipelineSupervisor()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_end_to_end_jobs(self):
        audio_out = os.path.join(self.tmp_dir.name, "narration.wav")
        frames_out = os.path.join(self.tmp_dir.name, "frames")

        j1 = self.supervisor.enqueue_job("NARRATE", {"text": "Production test narration.", "output_path": audio_out})
        j2 = self.supervisor.enqueue_job("RENDER_BEAT", {"beat_id": "beat_test", "output_dir": frames_out})

        self.supervisor.run_once()

        with get_db_connection() as conn:
            r1 = conn.execute("SELECT status FROM jobs WHERE id=?", (j1,)).fetchone()
            r2 = conn.execute("SELECT status FROM jobs WHERE id=?", (j2,)).fetchone()

        self.assertEqual(r1["status"], "COMPLETED")
        self.assertEqual(r2["status"], "COMPLETED")
        self.assertTrue(os.path.exists(audio_out))
        self.assertTrue(os.path.exists(os.path.join(frames_out, "beat_test.png")))

if __name__ == "__main__":
    unittest.main()
