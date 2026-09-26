"""Flag cited source_urls that no search in the same run returned.

For each run in a results JSONL written by run_guardrail_eval.py, extracts every
"source_url" in the output and checks it against the URLs returned by that run's
searches, as recorded by uk_evidence_search in logs/search_*.jsonl.

Run ids repeat across results files, so a run's searches are matched by time as
well as by run id: they must be tagged with the run id and fall after the
previous record in the file and at or before this record's timestamp. For the
first record, the window starts when the logging process started.

URLs are compared after light normalisation (http/https, host case, trailing
slash, fragment). URLs in the prose are not checked, only source_url fields.
Input files are only read. Exit status is 1 if any run is flagged.
"""
import argparse
import glob
import json
import re
import sys
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

SOURCE_URL = re.compile(r'"source_url"\s*:\s*("(?:[^"\\]|\\.)*")')


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", help="Results JSONL from run_guardrail_eval.py")
    parser.add_argument("--search-logs", default="logs/search_*.jsonl",
                        help="Glob for search log files (default: logs/search_*.jsonl)")
    return parser.parse_args()


def normalise(url):
    p = urlsplit(url.strip())
    scheme = "https" if p.scheme in ("http", "https") else p.scheme
    return urlunsplit((scheme, p.netloc.lower(), p.path.rstrip("/"), p.query, ""))


def cited_urls(output):
    """Every source_url value in the output, in order, including repeats.

    Uses a regex rather than a JSON parse so truncated outputs are still checked.
    """
    return [json.loads(m.group(1)) for m in SOURCE_URL.finditer(output)]


def read_jsonl(path):
    records = []
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Warning: skipping unreadable line {lineno} in {path}")
    return records


def load_searches(pattern):
    """Return every logged search, each tagged with its log file's start time."""
    searches = []
    for path in sorted(glob.glob(pattern)):
        entries = read_jsonl(path)
        if not entries:
            continue
        started = min(datetime.fromisoformat(e["timestamp"]) for e in entries)
        for e in entries:
            e["_at"] = datetime.fromisoformat(e["timestamp"])
            e["_log_started"] = started
            e["_log"] = path
            searches.append(e)
    return searches


def searches_for(searches, run_id, after, until):
    """Searches tagged run_id in (after, until]. If after is None, the window
    starts when the process that made the latest such search began."""
    tagged = [s for s in searches if s.get("case") == run_id and s["_at"] <= until]
    if after is None:
        if not tagged:
            return []
        after_inclusive = max(tagged, key=lambda s: s["_at"])["_log_started"]
        return [s for s in tagged if s["_at"] >= after_inclusive]
    return [s for s in tagged if s["_at"] > after]


def main():
    args = parse_args()
    records = read_jsonl(args.path)
    searches = load_searches(args.search_logs)
    if not searches:
        sys.exit(f"No search logs matched {args.search_logs}")

    flagged = []
    unverified = []
    checked = 0
    previous = None
    for rec in records:
        at = datetime.fromisoformat(rec["timestamp"])
        after, previous = previous, at
        run_id = rec["run_id"]

        cited = cited_urls(rec.get("output", ""))
        if not cited:
            print(f"{run_id}: no source_url citations")
            continue
        checked += 1

        runs = searches_for(searches, run_id, after, at)
        unique = list(dict.fromkeys(cited))
        head = f"{run_id}: {len(cited)} citations ({len(unique)} unique)"
        if not runs:
            unverified.append(run_id)
            print(f"{head}, UNVERIFIED: no searches logged for this run")
            continue

        returned = {normalise(r["url"]) for s in runs for r in s.get("results", []) if r.get("url")}
        missing = [u for u in unique if normalise(u) not in returned]
        if missing:
            flagged.append(run_id)
            print(f"{head}, {len(missing)} NOT RETURNED by its {len(runs)} searches:")
            for u in missing:
                print(f"    {u}")
        else:
            print(f"{head}, all returned by its {len(runs)} searches")

    print(f"\n{checked} run(s) with citations checked; "
          f"{len(flagged)} cite URLs no search returned; "
          f"{len(unverified)} unverified (no searches logged)")
    if flagged:
        print("Flagged:", ", ".join(flagged))
    if unverified:
        print("Unverified:", ", ".join(unverified))
    if flagged or unverified:
        sys.exit(1)


if __name__ == "__main__":
    main()
