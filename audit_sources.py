"""Audit where the evidence store's statements come from.

Run:  python audit_sources.py
      python audit_sources.py --store evidence_store.json --out results/authority_audit.md

Reads evidence_store.json and changes nothing in it. For every statement it
sorts the source_url's host into a group, checks the source_authority label
against that group, and prints a markdown report (also saved to --out).

Groups:
- national NHS: www.nhs.uk
- other NHS organisations: any other host on *.nhs.uk (trusts, ICBs, GP
  practices, regional formularies, the devolved NHS sites)
- NICE: nice.org.uk and its subdomains, except the BNF
- BNF: bnf.nice.org.uk
- anything else

The report doesn't decide which groups Lagomy should trust. It only shows
where the evidence comes from.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

STORE = "evidence_store.json"
OUT = "results/authority_audit.md"
FIELDS = ["role", "food_sources", "reference_intake", "upper_limit", "regulatory_flags"]

NATIONAL_NHS = "national NHS"
OTHER_NHS = "other NHS organisations"
NICE = "NICE"
BNF = "BNF"
OTHER = "anything else"
GROUPS = [NATIONAL_NHS, OTHER_NHS, NICE, BNF, OTHER]

# The label each group's statements should carry. Other NHS organisations and
# other sites have no matching label: "NHS" reads as national NHS guidance.
EXPECTED_LABEL = {NATIONAL_NHS: "NHS", NICE: "NICE", BNF: "BNF"}

# For "relies only on non-national sources": national NHS, NICE and the BNF
# count as national; other NHS organisations and other sites don't.
NATIONAL_GROUPS = {NATIONAL_NHS, NICE, BNF}


def host_of(url: str) -> str:
    try:
        host = urlsplit(url.strip()).hostname or ""
    except ValueError:
        host = ""
    return host.rstrip(".").lower()


def classify_host(host: str) -> str:
    if host == "www.nhs.uk":
        return NATIONAL_NHS
    if host == "bnf.nice.org.uk":
        return BNF
    if host == "nice.org.uk" or host.endswith(".nice.org.uk"):
        return NICE
    if host == "nhs.uk" or host.endswith(".nhs.uk"):
        return OTHER_NHS
    return OTHER


def statements(store: dict):
    """Every statement as (ingredient, field, statement), in store order."""
    for ingredient, entry in store.items():
        evidence = entry.get("evidence") or {}
        for field in FIELDS:
            for statement in evidence.get(field) or []:
                yield ingredient, field, statement


def audit(store: dict) -> dict:
    rows = []
    for ingredient, field, statement in statements(store):
        url = statement.get("source_url", "")
        host = host_of(url)
        group = classify_host(host)
        label = statement.get("source_authority", "")
        rows.append({
            "ingredient": ingredient,
            "field": field,
            "url": url,
            "host": host or "(no host)",
            "group": group,
            "label": label,
            "label_matches": EXPECTED_LABEL.get(group) == label,
        })

    groups_by_ingredient = defaultdict(set)
    for row in rows:
        groups_by_ingredient[row["ingredient"]].add(row["group"])

    return {
        "ingredients": len(store),
        "rows": rows,
        "no_statements": [i for i in store if i not in groups_by_ingredient],
        "only_non_national": [
            i for i in store
            if i in groups_by_ingredient and not groups_by_ingredient[i] & NATIONAL_GROUPS
        ],
    }


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|")


def render(result: dict) -> str:
    rows = result["rows"]
    by_group = defaultdict(list)
    for row in rows:
        by_group[row["group"]].append(row)

    lines = [
        "# Source authority audit",
        "",
        f"From `evidence_store.json`: {result['ingredients']} ingredients, {len(rows)} statements.",
        "",
        "## Statements per group",
        "",
        "| Group | Statements | Hosts | Ingredients |",
        "| --- | ---: | ---: | ---: |",
    ]
    for group in GROUPS:
        group_rows = by_group[group]
        lines.append(
            f"| {group} | {len(group_rows)} | {len({r['host'] for r in group_rows})} "
            f"| {len({r['ingredient'] for r in group_rows})} |"
        )

    lines += ["", "## Other NHS organisations, by host", ""]
    other_hosts = Counter(r["host"] for r in by_group[OTHER_NHS])
    if other_hosts:
        lines += ["| Host | Statements |", "| --- | ---: |"]
        lines += [f"| {host} | {count} |" for host, count in sorted(other_hosts.items(), key=lambda kv: (-kv[1], kv[0]))]
    else:
        lines.append("None.")

    non_national = [r for r in rows if r["group"] not in NATIONAL_GROUPS]
    lines += [
        "",
        "## Every non-national citation",
        "",
        "Non-national means other NHS organisations and anything else. National NHS, NICE and the BNF count as national.",
        "",
    ]
    if non_national:
        lines += ["| Ingredient | Field | Group | Host | URL |", "| --- | --- | --- | --- | --- |"]
        lines += [
            f"| {_cell(r['ingredient'])} | {r['field']} | {r['group']} | {r['host']} | {_cell(r['url'])} |"
            for r in non_national
        ]
    else:
        lines.append("None.")

    mismatches = [r for r in rows if not r["label_matches"]]
    lines += [
        "",
        "## Labels that don't match the host",
        "",
        "Expected labels: www.nhs.uk is NHS, nice.org.uk is NICE, bnf.nice.org.uk is BNF. "
        "No label matches other NHS organisations or other sites, because \"NHS\" reads as national NHS guidance.",
        "",
    ]
    if mismatches:
        pairs = Counter((r["group"], r["label"]) for r in mismatches)
        lines += ["| Group | Label | Statements |", "| --- | --- | ---: |"]
        lines += [f"| {g} | {_cell(l) or '(none)'} | {n} |" for (g, l), n in sorted(pairs.items(), key=lambda kv: (GROUPS.index(kv[0][0]), kv[0][1]))]
        lines += ["", "| Ingredient | Field | Label | Host |", "| --- | --- | --- | --- |"]
        lines += [f"| {_cell(r['ingredient'])} | {r['field']} | {_cell(r['label']) or '(none)'} | {r['host']} |" for r in mismatches]
    else:
        lines.append("None.")

    lines += ["", "## Ingredients whose evidence relies only on non-national sources", ""]
    if result["only_non_national"]:
        for ingredient in result["only_non_national"]:
            hosts = sorted({r["host"] for r in rows if r["ingredient"] == ingredient})
            lines.append(f"- {ingredient}: {', '.join(hosts)}")
    else:
        lines.append("None.")

    if result["no_statements"]:
        lines += ["", "## Ingredients with no statements", ""]
        lines += [f"- {ingredient}" for ingredient in result["no_statements"]]

    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Audit the evidence store's sources by authority.")
    parser.add_argument("--store", default=STORE, help=f"Evidence store (default: {STORE})")
    parser.add_argument("--out", default=OUT, help=f"Where to save the report (default: {OUT})")
    args = parser.parse_args(argv)

    with open(args.store, encoding="utf-8") as f:
        store = json.load(f)
    report = render(audit(store))
    print(report, end="")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
