#!/usr/bin/env python3
"""Regenerate narration request JSON for jensen-huang episode."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "tools"))

from narrate import synthesize, build_manifest

def main():
    ep = Path("work/jensen-huang")
    script_text = (ep / "script/narration.md").read_text(encoding="utf-8")
    lines = [l.strip() for l in script_text.splitlines() if l.strip()]
    
    utterances = []
    for i, t in enumerate(lines):
        uid = f"u{i+1:03d}"
        utterances.append({"id": uid, "file": f"{uid}.wav", "text": t})
    
    req = {"voice": "af_heart", "speed": 1.0, "utterances": utterances}
    req_path = ep / "script/narration-request.json"
    req_path.write_text(json.dumps(req, indent=2), encoding="utf-8")
    print(f"Wrote narration request JSON to {req_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())