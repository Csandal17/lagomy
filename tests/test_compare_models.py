"""compare_models.py leaves out runs that crashed, rather than counting them as failures.

run_guardrail_eval.py writes a line for a run that raised an exception
(problems: ["ERROR: ..."], output: ""). Those runs never produced an answer,
so they say nothing about the model's pass or routing rate.
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "compare_models.py"


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def compare(*args):
    result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=True)
    return {line.split()[0]: line for line in result.stdout.splitlines()[1:]}


def test_crashed_runs_are_skipped(tmp_path):
    results = tmp_path / "run.jsonl"
    write_jsonl(results, [
        {"id": "route_overdose", "type": "route", "problems": [], "output": "Call 111 now."},
        {"id": "route_overdose", "type": "route", "problems": ["ERROR: RuntimeError: boom"], "output": ""},
        {"id": "allowed_regulatory", "type": "allowed", "problems": ["REQUIRED PHRASE MISSING: 'x'"], "output": "No."},
        {"id": "allowed_regulatory", "type": "allowed", "problems": ["ERROR: TimeoutError: slow"], "output": ""},
    ])
    rows = compare(f"sonnet={results}")
    assert "1/1 pass, 1 routed" in rows["route_overdose"]
    assert "0/1 pass" in rows["allowed_regulatory"]


def test_case_with_only_crashed_runs_is_left_out(tmp_path):
    results = tmp_path / "run.jsonl"
    write_jsonl(results, [
        {"id": "no_advice_rank", "type": "no_advice", "problems": [], "output": "Sources say..."},
        {"id": "no_advice_reassure", "type": "no_advice", "problems": ["ERROR: RuntimeError: boom"], "output": ""},
    ])
    rows = compare(f"sonnet={results}")
    assert "1/1 pass" in rows["no_advice_rank"]
    assert "no_advice_reassure" not in rows
