"""Check the routing gate against every guardrail case.

Prints one line per case: id, type, and which rule fired (or '-').
Expected: the four route_* cases match, and nothing else does.
"""
import yaml

from lagomy.routing_gate import check_routing

CASE_FILES = [
    "guardrail_cases.yaml",
    "guardrail_cases_expanded.yaml",
    "guardrail_cases_batch2.yaml",
]

fired = 0
for path in CASE_FILES:
    for case in yaml.safe_load(open(path)):
        decision = check_routing(case["probe"])
        if decision:
            fired += 1
        print(f"{case['id']:28} {case['type']:10} {decision.rule if decision else '-'}")

print(f"\n{fired} of 20 cases matched a rule.")
