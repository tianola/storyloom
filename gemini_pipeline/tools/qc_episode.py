import os
from tools.utils.logger import get_logger

logger = get_logger("QualityControl")

def run_qc_checks(artifact_paths: list[str], min_bytes: int = 10) -> dict:
    results = {"passed": True, "checked": len(artifact_paths), "failures": []}
    for path in artifact_paths:
        if not os.path.exists(path):
            results["passed"] = False
            results["failures"].append({"file": path, "reason": "File missing"})
        elif os.path.getsize(path) < min_bytes:
            results["passed"] = False
            results["failures"].append({"file": path, "reason": f"File smaller than {min_bytes} bytes"})
    if results["passed"]:
        logger.info(f"QC passed for {len(artifact_paths)} artifacts.")
    else:
        logger.error(f"QC failed: {results['failures']}")
    return results
