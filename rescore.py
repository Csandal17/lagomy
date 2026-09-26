"""Add the scoped guardrail verdict to an existing results file without re-running the crew.

Reads either the JSONL format written by run_guardrail_eval.py or the older
eval_results*.json list format, adds "problems_scoped" to every record, and
writes <name>_rescored<ext> next to the input. "problems" is left untouched.

Scoring uses the current case definitions. If a record's stored "problems" no
longer match what check_output gives today, the case has changed since that run;
a warning is printed because the two verdicts are then not directly comparable.
"""
import argparse
import json
import os
import sys

import yaml

from run_guardrail_eval import check_output, check_output_scoped, is_error


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", help="Results file (.jsonl or eval_results*.json)")
    parser.add_argument("--cases", default="guardrail_cases.yaml",
                        help="YAML file of cases (default: guardrail_cases.yaml)")
    return parser.parse_args()


def read_records(path):
    """Return (records, is_jsonl)."""
    with open(path) as f:
        content = f.read()
    stripped = content.lstrip()
    if stripped.startswith("["):
        return json.loads(stripped), False
    records = []
    for lineno, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"Warning: skipping unreadable line {lineno} in {path}")
    return records, True


def write_records(path, records, is_jsonl):
    with open(path, "w") as f:
        if is_jsonl:
            for rec in records:
                f.write(json.dumps(rec) + "\n")
        else:
            json.dump(records, f, indent=2)


def main():
    args = parse_args()
    base, ext = os.path.splitext(args.path)
    out_path = f"{base}_rescored{ext}"
    if os.path.abspath(out_path) == os.path.abspath(args.path):
        sys.exit("Refusing to overwrite the input file")

    with open(args.cases) as f:
        cases = {case["id"]: case for case in yaml.safe_load(f)}

    records, is_jsonl = read_records(args.path)

    changed = []
    drifted = set()
    for rec in records:
        label = rec.get("run_id", rec["id"])
        case = cases.get(rec["id"])
        if case is None:
            print(f"Warning: {label}: case not in {args.cases}; problems_scoped set to null")
            rec["problems_scoped"] = None
            continue
        if is_error(rec):
            rec["problems_scoped"] = rec["problems"]
            continue

        text = rec["output"].lower()
        if check_output(case, text) != rec["problems"]:
            print(f"Warning: {label}: stored problems differ from current check_output; "
                  f"the case has changed since this run")
            drifted.add(label)
        rec["problems_scoped"] = check_output_scoped(case, text)

        if bool(rec["problems"]) != bool(rec["problems_scoped"]):
            changed.append(rec)

    write_records(out_path, records, is_jsonl)

    total = len(records)
    passed = sum(1 for r in records if not r["problems"])
    passed_scoped = sum(1 for r in records if r["problems_scoped"] == [])
    print(f"Wrote {out_path}")
    print(f"Passed: {passed}/{total} (scoped: {passed_scoped}/{total})")
    if changed:
        print("\nVerdict changed:")
        for rec in changed:
            before = "; ".join(rec["problems"]) or "PASS"
            after = "; ".join(rec["problems_scoped"]) or "PASS"
            label = rec.get("run_id", rec["id"])
            note = "  [case changed since run, not a scoping effect]" if label in drifted else ""
            print(f"  {label}: {before}  ->  {after}{note}")


if __name__ == "__main__":
    main()
