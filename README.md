# Lagomy

Snap a supplement label and get a structured record of what it says, with UK-sourced evidence for each ingredient and a printable report you can hand to a clinician.

**Log, don't advise. Show, link, source — never conclude.** Lagomy records what a label says and what published UK sources say. It does not rank products, reassure, diagnose, or tell you what to take. Named for *lagom*, the Swedish idea of *just enough*.

Live API: [api.lagomy.com/docs](https://api.lagomy.com/docs)

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

## Checking the dataset

`check_data.py` checks the master sheet against the dataset's own rules before anything is published. It needs nothing beyond Python itself.

1. In Google Sheets, download each of these tabs as CSV (File > Download > Comma-separated values): Products, Ingredients, Product_Ingredients, Product_Warnings, Product_Claims, Brands, Categories.
2. Put the files in a folder called `sheet_export/` in this repo. It's in `.gitignore`, so the data never gets committed. Google's file names work as they are.
3. Run:

```bash
python check_data.py sheet_export
```

It reports two kinds of finding, with the sheet's own row numbers:

- **Errors** break a rule, and make the script exit with status 1. For example: an ingredient name that isn't the dictionary's exact canonical name, a unit that isn't on the list (`mcg` instead of `µg`, or a Greek μ that looks like µ but doesn't match), a `per` value that isn't on the list, a % NRV on a botanical (which has no NRV), a barcode with the wrong check digit, or a CAS number with the wrong check digit.
- **Checks** are worth comparing with the label, but may be right as printed. For example: a % NRV that doesn't match the amount against the adult NRV, the same barcode on two products, or a TBC product that has ingredient rows (so the export would publish it).

It also prints the next free IDs (P, I, W, C and B), so new rows don't need counting by hand.

The tests use small made-up sheets, never the real data:

```bash
uv run --with pytest pytest
```

## Status

In active development, built in the open.

**Working:** the dataset, label reading, ingredient normalisation, evidence retrieval, synthesis, the PDF report, the API, and the guardrail suite.

**Not yet built:** the front end, search by product name, and subjective tracking over time.

The dataset is a working sample rather than a finished corpus, and is growing.

## Licence

The code in this repository is MIT licensed — see [LICENSE](LICENSE).

The Lagomy UK Supplements dataset is published separately on [Hugging Face](https://huggingface.co/datasets/Csandal17/lagomy-uk-supplements) under CC BY-NC 4.0. The MIT licence above does not cover the dataset.
