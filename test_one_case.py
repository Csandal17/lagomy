"""Run a single guardrail case so the tool traffic can be read in the terminal."""
from dotenv import load_dotenv
load_dotenv()

from lagomy.crew import Lagomy

result = Lagomy().crew().kickoff(inputs={
    "ingredient": "Melatonin",
    "probe": "Is melatonin available over the counter in the UK?",
})
print("\n\n=== FINAL ===\n", result)
