# Draft: "How Tavily is used" (proposed README subsection)

Proposed to replace the one-paragraph **Tavily** entry under "How Nebius, Nemotron and Tavily are used" in `README.md`. Not yet applied.

---

### How Tavily is used

Tavily's results define what the model is allowed to cite. That makes a fabricated citation countable without a judge model: every cited address either is or is not among the pages that run's own searches returned.

**The search.** Tavily is the crew's only tool, given to the evidence agent (`src/lagomy/crew.py`). Each call uses `include_domains` set to www.nhs.uk, www.nice.org.uk, bnf.nice.org.uk, cks.nice.org.uk and 111.wales.nhs.uk, with `max_results=3`, and the model sees each result's title, URL and first 600 characters (`src/lagomy/tools/uk_evidence_search.py`). The task asks for one search per field and six at most, and tells the synthesis step to keep source URLs exactly and drop any claim it cannot trace to a source (`src/lagomy/config/tasks.yaml`). Each agent is capped at `max_iter=5` (`src/lagomy/crew.py`).

**The research trail.** Every search is appended to `logs/search_<timestamp>.jsonl` with its query, its eval case, and each result's title, URL and 600-character snippet (`src/lagomy/tools/uk_evidence_search.py`). From 14 to 28 September the evaluation logged 4,512 searches across all three models, in 29 files kept locally because `logs/` is gitignored (`.gitignore`).

**The allowlist check.** `check_citations.py` takes every `source_url` in an answer and compares it with the URLs returned by that run's searches, matched by run id and time. It treats http and https alike and ignores host case, a trailing slash, the fragment, query parameter order and escaped ampersands. A citation that matches only once a returned URL's query string is removed is reported separately, not as unmatched (`check_citations.py`). The demo imports the same normalisation and checks in memory against the searches it has just run, without that separate category (`demo_api.py`).

**What the demo shows live.** As each search finishes, `POST /ask` streams a `search` event, and the page adds it to a Research trail: the query, then each page's title, address and snippet (`demo_api.py`, `demo_page.html`). When the answer arrives, any evidence card or source whose page no search returned says "Not among this run's search results" (`demo_page.html`).

**The numbers.** Nemotron cited a page its searches never returned in 55 of 174 citing runs, Opus 5.5 in none of 202, and Sonnet 4.6 in 2 of 179, both real pages (`results/FINDINGS.md`). Of the 47 unique unmatched URLs from the three later Nemotron files, 35 are dead, 1 is live and 11 could not be determined (`results/FINDINGS.md`, `results/CITATION_CHECKS.md`).

**The limit.** The check matches addresses, not content: it cannot tell whether a returned page supports the claim made from it (`README.md`, Limits).

---

## Video moments

1. **The header line.** Open on the provenance line under the tagline: "Searches run through Tavily and are restricted to NHS, NICE and BNF pages." Read it aloud. It is the only place the page names Tavily (`demo_page.html`).
2. **The trail building.** Run the vitamin D example and hold on the Research trail as "Searched for" entries arrive, each with titles, addresses and snippets, while the status reads "Searching NHS, NICE and BNF pages". Say that each entry is a Tavily search, streamed as it finishes, and open one "Show more" (`demo_page.html`).
3. **The allowlist at work.** Scroll to Sources, which opens with "Nemotron sometimes cites a page its searches didn't return; Lagomy marks every one." Point to a "Not among this run's search results" note and say the Tavily results are the list it was checked against. If the run comes back clean, say so and cut to the routing example, where the page states "No search was run and no model was called" (`demo_page.html`).
