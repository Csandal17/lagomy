import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

import yaml
from dotenv import load_dotenv
from lagomy.crew import Lagomy
from guardrails import find_banned_phrases
from lagomy.tools import uk_evidence_search

load_dotenv()


def parse_args():
    now = datetime.now(timezone.utc)
    default_out = os.path.join(
        "results", f"eval_{now:%Y-%m-%d}_{now:%H%M}.jsonl"
    )
    parser = argparse.ArgumentParser(
        description="Run the guardrail eval cases through the crew and log results as JSONL."
    )
    parser.add_argument("--repeats", type=int, default=1,
                        help="Number of times to run each case (default: 1)")
    parser.add_argument("--out", default=default_out,
                        help="JSONL output path; if it exists, completed runs are skipped "
                             "(default: results/eval_<UTC date>_<HHMM>.jsonl)")
    parser.add_argument("--cases", default="guardrail_cases.yaml",
                        help="YAML file of cases (default: guardrail_cases.yaml)")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    return args


def make_run_id(case_id, repeat):
    return f"{case_id}#{repeat}"


def check_output(case, text):
    problems = []
    for phrase in find_banned_phrases(text):
            problems.append(f"BANNED PHRASE PRESENT (universal): {phrase!r}")
    for phrase in case.get("must_not", []):
        if str(phrase).lower() in text:
            problems.append(f"BANNED PHRASE PRESENT: {phrase!r}")
    for phrase in case.get("must_include", []):
        if str(phrase).lower() not in text:
            problems.append(f"REQUIRED PHRASE MISSING: {phrase!r}")
    return problems


_json_decoder = json.JSONDecoder()


def _drop_statement_text(node):
    """Remove "text" from every evidence statement (a dict that also has source_url)."""
    if isinstance(node, dict):
        return {k: _drop_statement_text(v) for k, v in node.items()
                if not (k == "text" and "source_url" in node)}
    if isinstance(node, list):
        return [_drop_statement_text(v) for v in node]
    return node


def strip_evidence_text(text):
    """Return text with evidence statement "text" values removed.

    Each parseable JSON object is re-serialised without them; prose and anything
    that does not parse as JSON is kept verbatim, so it is still checked.
    """
    parts = []
    pos = 0
    start = text.find("{")
    while start != -1:
        try:
            obj, end = _json_decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue
        parts.append(text[pos:start])
        parts.append(json.dumps(_drop_statement_text(obj), ensure_ascii=False))
        pos = end
        start = text.find("{", end)
    parts.append(text[pos:])
    return "".join(parts)


def check_output_scoped(case, text):
    """Diagnostic variant of check_output: banned phrases are only checked in the
    model's own prose, not in quoted evidence statement text. must_include is
    still checked against the full output, since required facts live in the evidence."""
    prose = strip_evidence_text(text)
    problems = []
    for phrase in find_banned_phrases(prose):
        problems.append(f"BANNED PHRASE PRESENT (universal): {phrase!r}")
    for phrase in case.get("must_not", []):
        if str(phrase).lower() in prose:
            problems.append(f"BANNED PHRASE PRESENT: {phrase!r}")
    for phrase in case.get("must_include", []):
        if str(phrase).lower() not in text:
            problems.append(f"REQUIRED PHRASE MISSING: {phrase!r}")
    return problems


def load_existing(path):
    """Return {run_id: record} for every complete line already in path."""
    records = {}
    if not os.path.exists(path):
        return records
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                # Most likely a line truncated by a crash mid-write; that run is redone.
                print(f"Warning: skipping unreadable line {lineno} in {path}")
                continue
            if "run_id" in rec:
                records[rec["run_id"]] = rec
    return records


def ensure_trailing_newline(path):
    """If the file ends mid-line (e.g. after a crash), start appends on a fresh line."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return
    with open(path, "rb") as f:
        f.seek(-1, os.SEEK_END)
        last = f.read(1)
    if last != b"\n":
        with open(path, "a") as f:
            f.write("\n")


def is_error(rec):
    return any(str(p).startswith("ERROR:") for p in rec["problems"])


def main():
    args = parse_args()

    with open(args.cases) as f:
        cases = yaml.safe_load(f)

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    done = load_existing(args.out)
    ensure_trailing_newline(args.out)

    total_runs = len(cases) * args.repeats
    already = sum(
        1 for case in cases for r in range(1, args.repeats + 1)
        if make_run_id(case["id"], r) in done
    )
    print(f"Writing results to {args.out}")
    if already:
        print(f"Resuming: {already}/{total_runs} runs already recorded, skipping those")

    with open(args.out, "a") as out:
        for case in cases:
            for repeat in range(1, args.repeats + 1):
                run_id = make_run_id(case["id"], repeat)
                if run_id in done:
                    continue

                print(f"\n--- {run_id} ({case['type']}) ---")
                uk_evidence_search.CURRENT_CASE = run_id
                try:
                    result = Lagomy().crew().kickoff(inputs={
                        "ingredient": case["ingredient"],
                        "probe": case["probe"],
                    })
                    output = str(result)
                    problems = check_output(case, output.lower())
                    problems_scoped = check_output_scoped(case, output.lower())
                except Exception as e:
                    output = ""
                    problems = [f"ERROR: {type(e).__name__}: {e}"]
                    problems_scoped = problems

                if problems:
                    for p in problems:
                        print("  FAIL:", p)
                else:
                    print("  PASS")
                if problems_scoped != problems:
                    print("  scoped:", "; ".join(problems_scoped) or "PASS")

                rec = {
                    "run_id": run_id,
                    "id": case["id"],
                    "type": case["type"],
                    "repeat": repeat,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "problems": problems,
                    "problems_scoped": problems_scoped,
                    "output": output,
                }
                out.write(json.dumps(rec) + "\n")
                out.flush()
                os.fsync(out.fileno())
                done[run_id] = rec

    # Summary covers every run for the current cases/repeats, including ones
    # recorded by an earlier (resumed) invocation.
    passed = defaultdict(int)
    passed_scoped = defaultdict(int)
    errored = []
    print("\n=== Summary ===")
    for case in cases:
        for repeat in range(1, args.repeats + 1):
            rec = done.get(make_run_id(case["id"], repeat))
            if rec is None:
                continue
            if is_error(rec):
                errored.append(rec["run_id"])
                continue
            if not rec["problems"]:
                passed[case["id"]] += 1
            # Lines written before problems_scoped existed are scored on the fly.
            scoped = rec.get("problems_scoped")
            if scoped is None:
                scoped = check_output_scoped(case, rec["output"].lower())
            if not scoped:
                passed_scoped[case["id"]] += 1
        print(f"{case['id']}: {passed[case['id']]}/{args.repeats} passed "
              f"(scoped: {passed_scoped[case['id']]}/{args.repeats})")

    total_passed = sum(passed.values())
    total_scoped = sum(passed_scoped.values())
    print(f"\nTotal: {total_passed}/{total_runs} passed "
          f"(scoped: {total_scoped}/{total_runs})")
    if errored:
        print(f"{len(errored)} run(s) raised an exception:", ", ".join(errored))
        sys.exit(1)


if __name__ == "__main__":
    main()
