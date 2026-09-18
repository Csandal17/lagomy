"""Log each agent step, including the model's thought, before the tool runs."""
import json
from datetime import datetime, timezone

from lagomy.tools.uk_evidence_search import LOG_DIR, RUN_STAMP
from lagomy.tools import uk_evidence_search

STEP_LOG_PATH = LOG_DIR / f"steps_{RUN_STAMP}.jsonl"


def log_step(step) -> None:
    """Append one JSON line per agent step. Never raises."""
    try:
        LOG_DIR.mkdir(exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "case": uk_evidence_search.CURRENT_CASE,
            "step_type": type(step).__name__,
            "thought": getattr(step, "thought", None),
            "tool": getattr(step, "tool", None),
            "tool_input": getattr(step, "tool_input", None),
            "text": (getattr(step, "text", "") or "")[:2000],
        }
        with STEP_LOG_PATH.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    