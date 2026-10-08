# Lagomy

Snap a supplement label and get a structured record of what it says, with UK-sourced evidence for each ingredient and a printable report you can hand to a clinician.

**Log, don't advise. Show, link, source — never conclude.** Lagomy records what a label says and what published UK sources say. It does not rank products, reassure, diagnose, or tell you what to take. Named for *lagom*, the Swedish idea of *just enough*.

Live API: [api.lagomy.com/docs](https://api.lagomy.com/docs)

## Nebius x NVIDIA hackathon branch

This branch, `hackathon/nemotron`, is an evaluation track rather than the product. It runs Lagomy's no-advice rules against an open model and asks a narrower question: can the output be trusted enough to show anyone? `main` and the store-only Evidence API at api.lagomy.com are untouched by it, and nothing in this section is merged back.

**Live demo: [lagomy-nemotron.up.railway.app](https://lagomy-nemotron.up.railway.app)**

### What the demo does

Ask a supplement question and one of two paths runs.

A deterministic routing gate goes first, with no model call and no search. If the question describes something already swallowed, or names an anticoagulant, the gate returns a short routing message and stops there.

Otherwise the crew runs: Tavily retrieves UK sources, the agents produce a sourced report, and a citation check compares every URL in the answer against what the searches actually returned. `POST /ask` streams those stages as events (`gate`, `search`, `report`, `citations`, `error`, `done`), so the demo page shows the work rather than only the result.

### How Nebius, Nemotron and Tavily are used

**Nebius Token Factory** serves the model over an OpenAI-compatible endpoint, configured with `NEBIUS_BASE_URL` and `NEBIUS_API_KEY`.

**NVIDIA Nemotron 3 Nano** (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`) is the model behind the crew's agents, run through CrewAI 1.15.21 at `max_tokens` 8000. Reasoning tokens are drawn from that same budget. `LAGOMY_MODEL` selects a different model for comparison runs.

**Where Token Factory accelerated the work.** Because the endpoint is OpenAI-compatible, moving the crew from Claude to Nemotron was a configuration change rather than a rewrite: the same agents, tasks and tools, with a different `base_url` and model string. Plain completions and tool calling both worked on the first smoke test. Per-token pricing low enough to repeat every evaluation case many times (240 Nemotron runs at 8000 tokens) is what turned one-off failures into measured rates.

**Tavily** defines the evidence set. The search results are the only material the model is entitled to cite, so anything outside them can be caught without a judge model: the citation check flags any URL in the answer that no search returned.

### The routing gate

`src/lagomy/routing_gate.py`. Two rules, pattern-matched, no model involved:

1. Past-tense ingestion plus a quantity and a dose noun, or the word "overdosed", returns NHS 111 text.
2. A named anticoagulant returns GP text. Rule 1 takes precedence.

The gate routes and makes no clinical claim. Its known false positives and negatives are documented in the module docstring, and `check_gate_coverage.py` measures its reach: it fires on 4 of 20 evaluation cases, so it narrows the risky surface rather than standing in for the model.

### Findings

Full write-up in [results/FINDINGS.md](results/FINDINGS.md). Six results, with the raw eval files committed alongside. Two that shaped the build:

**Framing decides routing.** On the latent iron case, Nemotron routed correctly in 5 of 32 runs, against 16 of 16 for Sonnet and 29 of 30 for Opus. On the warfarin case, Nemotron routed correctly in 4 of 32.

**Nemotron cites pages its searches never returned.** This appeared in 55 of 174 citing runs. The later 134 of those runs cited 47 distinct URLs that no search returned: 35 were dead, 1 was live, and 11 could not be determined. The comparison runs showed 0 of 202 for Opus and 2 of 179 for Sonnet, both of those real pages. This is the finding the deterministic citation check exists to catch.

### Limits

- Output from this branch is not reliable on its own. Three runs of the vitamin D example on the live demo produced two answers containing an address no search returned, and one clean answer.
- The citation check compares URLs exactly. It does not understand negation and it does not verify that a cited page supports the claim made from it.
- The demo has no user accounts and no database. It holds one crew run at a time under an in-memory daily cap. Search queries, which the model writes from the question, are appended to `logs/` inside the container and are lost when it restarts.
- Lagomy logs and sources. It does not advise, rank, reassure or diagnose, and the gate text is routing rather than clinical guidance.

### Running the demo locally

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

Create a `.env` file with:

```
NEBIUS_API_KEY=your-key
NEBIUS_BASE_URL=your-endpoint
TAVILY_API_KEY=your-key
DEMO_DAILY_RUN_LIMIT=30
```

The server will not start without the two Nebius settings. Placeholder values are enough to load the page and try the routing gate, which calls no model and no search; a full crew run needs real keys.

Serve the demo:

```bash
uv run uvicorn demo_api:app --reload
```

`/` is the demo page, `/test` a bare page without styling, `/health` a status check, and `POST /ask` the streaming endpoint. The deployed copy builds from the `Dockerfile` in this repository and listens on `$PORT`.

Run the tests:

```bash
uv run pytest tests/
```

All 64 tests should pass.

---

*The sections below describe Lagomy's main product, as it runs on `main` and at api.lagomy.com. To run this branch, use "Running the demo locally" above.*

## Why there's a dataset

The crew needed a reliable source of UK supplement compositions, and there wasn't one. The available options were US-regime databases, retailer scrapes, or aggregator sites, none of which are trustworthy for UK products.

So the dataset came first: 50 products, 149 ingredients and 952 ingredient rows, transcribed by hand from physical labels and brand-published nutrition tables, with every field traceable to its source. It's published openly on [Hugging Face](https://huggingface.co/datasets/Csandal17/lagomy-uk-supplements), and everything in this repository is built on top of it.

## What it does

- **Reads a label** — Claude Vision transcribes exactly what's printed, flagging anything unclear in a `needs_review` list rather than guessing.
- **Normalises ingredient names** — keeps the printed name and adds a canonical one, so "Methylcobalamin" and "Vitamin B12" don't fragment the log.
- **Retrieves UK evidence** — a CrewAI agent searches NHS, NICE and BNF via Tavily and returns statements with their sources.
- **Checks and structures** — a second agent verifies each claim against the retrieved evidence, distinguishing what a nutrient does from what a deficiency causes, and emits JSON where every statement carries its source URL, authority and retrieval date.
- **Serves it over an API** — `POST /evidence` runs the crew and returns the structured record.

## The guardrail

The no-advice rule is tested, not just intended. `guardrail_cases.yaml` holds adversarial probes in three directions: prompts designed to make the crew rank, reassure or diagnose; a crisis case that *must* hand off to emergency services; and positive controls that must still surface sourced regulatory facts, so the crew can't pass by refusing everything.

The same phrase checks run on live API responses. If advice-like language appears in the prose, the prose is withheld, and the sourced evidence is returned without it — the record survives, the risky rendering doesn't.

## Running it

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

Create a `.env` file with:

```
ANTHROPIC_API_KEY=your-key
TAVILY_API_KEY=your-key
```

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

In active development, built in the open.

**Working:** the dataset, label reading, ingredient normalisation, evidence retrieval, synthesis, the PDF report, the API, and the guardrail suite.

**Not yet built:** the front end, search by product name, and subjective tracking over time.

The dataset is a working sample rather than a finished corpus, and is growing.

## Licence

The code in this repository is MIT licensed — see [LICENSE](LICENSE).

The Lagomy UK Supplements dataset is published separately on [Hugging Face](https://huggingface.co/datasets/Csandal17/lagomy-uk-supplements) under CC BY-NC 4.0. The MIT licence above does not cover the dataset.
