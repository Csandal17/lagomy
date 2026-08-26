# Lagomy

Snap a supplement label and get a structured record of what it says, with UK-sourced evidence for each ingredient and a printable report you can hand to a clinician.

**Log, don't advise. Show, link, source — never conclude.** Lagomy records what a label says and what published UK sources say. It does not rank products, reassure, diagnose, or tell you what to take. Named for *lagom*, the Swedish idea of *just enough*.

## What it does

- **Reads a label** — Claude vision transcribes exactly what's printed, flagging anything unclear in a `needs_review` list rather than guessing.
- **Normalises ingredient names** — keeps the printed name and adds a canonical one, so "Methylcobalamin" and "Vitamin B12" don't fragment the log.
- **Retrieves UK evidence** — a CrewAI agent searches NHS, NICE and BNF via Tavily and returns statements with their sources.
- **Checks and structures** — a second agent verifies each claim against the retrieved evidence, distinguishing what a nutrient does from what a deficiency causes, and emits JSON where every statement carries its source URL, authority and retrieval date.
- **Serves it over an API** — `POST /evidence` runs the crew and returns the structured record.

## The guardrail

The no-advice rule is tested, not just intended. `guardrail_cases.yaml` holds adversarial probes in three directions: prompts designed to make the crew rank, reassure or diagnose; a crisis case that *must* hand off to emergency services; and positive controls that must still surface sourced regulatory facts, so the crew can't pass by refusing everything.

The same phrase checks run on live API responses. If advice-like language appears in the prose, the prose is withheld and the sourced evidence is returned without it — the record survives, the risky rendering doesn't.

## Running it

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

Create a `.env` file with:

ANTHROPIC_API_KEY=your-key
TAVILY_API_KEY=your-key


Run the crew directly:

```bash
crewai run
```

Or serve the API:

```bash
uvicorn api:app --reload
```

Interactive docs at `http://127.0.0.1:8000/docs`.

Run the guardrail suite:

```bash
python run_guardrail_eval.py
```

Note: each eval run executes the full crew against six cases with live searches, so it takes several minutes and costs API credit. Results are written to `eval_results.json`.

## Status

In active development, built in the open. Working: label reading, ingredient normalisation, evidence retrieval, synthesis, the PDF report, the API, and the guardrail suite. Not yet built: the front end, search by product name, and subjective tracking over time.

## Licence

The code in this repository is MIT licensed — see [LICENSE](LICENSE).

The Lagomy UK Supplements dataset is published separately on [Hugging Face](https://huggingface.co/datasets/Csandal17/lagomy-uk-supplements) under CC BY-NC 4.0. The MIT licence above does not cover the dataset.
