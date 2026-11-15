# Production Pipeline

Ολοκληρωμένο, production-ready pipeline αυτοματοποίησης (Python, Blender CLI, SQLite WAL Queue & TypeScript Client).

## Δομή Αρχείων
- `tools/pipeline_supervisor.py`: Κεντρικός daemon/supervisor με αυτόματο retry, διαχείριση ουράς SQLite και QC έλεγχο.
- `tools/utils/retry.py`: Decorator εκθετικής καθυστέρησης (Exponential Backoff).
- `tools/utils/logger.py`: Δομημένο JSON logging (`logs/pipeline.jsonl`) & console output.
- `src/database.py`: SQLite connection manager με ενεργοποιημένο WAL mode και busy timeout.
- `src/jobs.ts`: TypeScript client (`better-sqlite3`) συμβατός με το ίδιο WAL schema.
- `tools/blender/utils_purge.py` & `render_worker.py`: Headless Blender rendering με αυτόματο καθαρισμό orphan data blocks.
- `python/narrate.py`: TTS narration engine με ενσωματωμένο retry logic.
- `tools/qc_episode.py`: Έλεγχος ακεραιότητας παραγόμενων αρχείων (Quality Control).

## Εκτέλεση & Tests
```bash
PYTHONPATH=. python3 test_pipeline.py
PYTHONPATH=. python3 tools/pipeline_supervisor.py
```
