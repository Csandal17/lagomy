"""Eval runner for the Intake agent. Compares parsed rows against known-good cases."""

import sys
import yaml
from collections import Counter

CASES = "intake_cases.yaml"


def load_cases(path: str = CASES) -> list[dict]:
    with open(path) as f:
        return yaml.safe_load(f)


def check_case(case: dict, rows: list[dict]) -> tuple[bool, str]:
    """Compare one case's expectations against the rows the agent returned.

    Returns (passed, detail).
    """
    expect = dict(case["expect"])
    key = expect.pop("match_on")
    target = expect[key]

    matches = [r for r in rows if str(r.get(key, "")).strip().lower() == str(target).lower()]
    if not matches:
        return False, f"row not found: no {key} == {target!r}"
    row = matches[0]

    problems = []
    for field, want in expect.items():
        got = row.get(field)
        if str(got).strip() != str(want).strip():
            problems.append(f"{field}: expected {want!r}, got {got!r}")

    if problems:
        return False, "; ".join(problems)
    return True, "ok"


if __name__ == "__main__":
    cases = load_cases()
    print(f"Loaded {len(cases)} cases.")
    for c in cases:
        print(f"  {c['id']:16} {c['error_class']:10} match_on={c['expect']['match_on']}")
        