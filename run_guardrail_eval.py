import sys
import json
import yaml
from dotenv import load_dotenv
from lagomy.crew import Lagomy

load_dotenv()

with open("guardrail_cases.yaml") as f:
    cases = yaml.safe_load(f)

failures = []
report = []

for case in cases:
    print(f"\n--- {case['id']} ({case['type']}) ---")
    result = Lagomy().crew().kickoff(inputs={
        "ingredient": case["ingredient"],
        "probe": case["probe"],
    })
    text = str(result).lower()

    problems = []
    for phrase in case.get("must_not", []):
        if str(phrase).lower() in text:
            problems.append(f"BANNED PHRASE PRESENT: {phrase!r}")
    for phrase in case.get("must_include", []):
        if str(phrase).lower() not in text:
            problems.append(f"REQUIRED PHRASE MISSING: {phrase!r}")

        if problems:
            failures.append(case["id"])
            for p in problems:
                print("  FAIL:", p)
    else:
        print("  PASS")

    report.append({
        "id": case["id"],
        "type": case["type"],
        "problems": problems,
        "output": str(result),
    })

with open("eval_results.json", "w") as f:
    json.dump(report, f, indent=2)

print(f"\n{len(cases) - len(failures)}/{len(cases)} passed")
if failures:
    print("Failed cases:", ", ".join(failures))
    sys.exit(1)
    