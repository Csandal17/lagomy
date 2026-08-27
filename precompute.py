"""Run the crew once per ingredient and store the results.

Usage:  python precompute.py Vitamin\\ B12 Magnesium Iron
"""
import json
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from api import extract_json
from lagomy.crew import Lagomy

load_dotenv()

STORE = Path("evidence_store.json")
NEUTRAL_PROBE = "What do published UK sources say about this ingredient?"


def load_store() -> dict:
    try:
        return json.loads(STORE.read_text())
    except FileNotFoundError:
        return {}


def main(ingredients: list[str]) -> None:
    store = load_store()

    for name in ingredients:
        if name in store:
            print(f"SKIP {name} — already in store")
            continue

        print(f"RUN  {name} ...")
        result = Lagomy().crew().kickoff(inputs={
            "ingredient": name,
            "probe": NEUTRAL_PROBE,
        })
        text = str(result)
        data = extract_json(text)

        today = str(date.today())
        for field in ["role", "food_sources", "reference_intake",
                      "upper_limit", "regulatory_flags"]:
            for statement in data.get(field, []):
                statement["retrieval_date"] = today

        store[name] = {
            "evidence": data,
            "prose": text.split("```json")[0].strip(),
            "computed_on": today,
        }
        STORE.write_text(json.dumps(store, indent=2))
        print(f"DONE {name} — saved")

    print(f"\nStore now holds {len(store)} ingredients.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Give one or more ingredient names as arguments.")
        sys.exit(1)
    main(sys.argv[1:])
    