"""Backend for Lagomy's hackathon demo: one question in, a stream of events out.

POST /ask takes {"ingredient", "question"} and answers with Server-Sent Events:

    gate                                  the routing gate answered; no crew run
    search ... report citations           a crew run, searches streamed live
    error                                 anything that failed
    done                                  always last

The routing gate runs before anything else. Gated questions never reach the
crew, Tavily or the model, and do not count towards the daily cap.

Credits are protected in memory only: one crew run at a time, and a daily cap
on crew runs (DEMO_DAILY_RUN_LIMIT, default 30, reset at midnight UTC). Nothing
about callers is stored.

Keys (NEBIUS_*, TAVILY_API_KEY) are read from the environment by the crew and
the search tool. This module never reads, logs or returns them.

Run locally:  uvicorn demo_api:app --port 8000
"""
import asyncio
import json
import logging
import os
import queue
import re
import threading
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from check_citations import normalise
from guardrails import find_banned_phrases
from lagomy.crew import Lagomy
from lagomy.routing_gate import check_routing
from lagomy.tools import uk_evidence_search

logger = logging.getLogger("lagomy.demo_api")

MAX_INGREDIENT_CHARS = 80
MAX_QUESTION_CHARS = 500
SNIPPET_CHARS = 600  # the same cut the search tool shows the model
DAILY_RUN_LIMIT = int(os.environ.get("DEMO_DAILY_RUN_LIMIT", "30"))

BUSY_MESSAGE = "A search is already running. Please try again in a few minutes."
CAP_MESSAGE = ("The demo has used all of today's searches. "
               "It resets at midnight UTC.")
FAILED_MESSAGE = "Something went wrong while searching. Please try again."
NO_EVIDENCE_MESSAGE = ("The search finished but produced no evidence block, "
                       "so there is nothing to show.")


class AskRequest(BaseModel):
    ingredient: str
    question: str


app = FastAPI(
    title="Lagomy demo API",
    description="Sourced UK supplement evidence, streamed. Records, never advises.",
    version="0.1.0",
)


@app.exception_handler(RequestValidationError)
async def plain_validation_error(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": 'Send a JSON body with text fields "ingredient" and "question".'},
    )


# --- Run limits -------------------------------------------------------------

# Held for the whole of a crew run and released only by the worker thread when
# the crew has finished, whether or not the client is still connected. It also
# guards the module-level ON_SEARCH hook and CURRENT_CASE in the search tool.
_run_lock = threading.Lock()
# Guards the daily counter and makes "check the cap, take the run lock, count
# the run" one step.
_state_lock = threading.Lock()
_runs_day = None
_runs_today = 0


def _today():
    return datetime.now(timezone.utc).date()


def _reserve_run():
    """Take the run lock and count the run, or raise a 429."""
    global _runs_day, _runs_today
    with _state_lock:
        today = _today()
        if today != _runs_day:
            _runs_day, _runs_today = today, 0
        if _runs_today >= DAILY_RUN_LIMIT:
            raise HTTPException(status_code=429, detail=CAP_MESSAGE)
        if not _run_lock.acquire(blocking=False):
            raise HTTPException(status_code=429, detail=BUSY_MESSAGE)
        _runs_today += 1


# --- Crew output ------------------------------------------------------------

def extract_evidence(text: str) -> dict:
    """Pull the JSON evidence object out of the crew's prose + JSON output.

    The same parse as extract_json in precompute.py on main. It is copied, not
    imported: on this branch precompute.py imports it from api.py, which no
    longer defines it, and importing precompute also loads .env and builds the
    crew.
    """
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        match = re.search(r"(\{.*\})", text, re.DOTALL)
    if not match:
        raise ValueError("Crew returned no JSON block")
    return json.loads(match.group(1))


def extract_prose(text: str) -> str:
    """Everything before the fenced JSON block, as precompute.py stores it."""
    return text.split("```json")[0].strip()


def cited_source_urls(node) -> list[str]:
    """Every source_url in the evidence, in order, without repeats."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "source_url" and isinstance(value, str):
                found.append(value)
            else:
                found.extend(cited_source_urls(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(cited_source_urls(item))
    return list(dict.fromkeys(found))


def build_report(output: str) -> dict:
    """The report payload. Banned phrases are checked in the prose only; on a
    hit the prose is withheld and the evidence still ships, as in api.py."""
    evidence = extract_evidence(output)
    prose = extract_prose(output)
    matched = find_banned_phrases(prose)
    return {
        "prose": None if matched else prose,
        "evidence": evidence,
        "prose_withheld": bool(matched),
        "matched_phrases": matched,
    }


def check_citations(evidence: dict, returned_urls: list[str]) -> list[dict]:
    returned = {normalise(u) for u in returned_urls}
    return [{"url": u, "in_search_results": normalise(u) in returned}
            for u in cited_source_urls(evidence)]


# --- Streaming ----------------------------------------------------------------

_DONE = object()


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _run_crew(ingredient: str, question: str, events: queue.Queue) -> None:
    """Worker thread: run the crew, putting (event, payload) pairs on events.

    Always ends by releasing the run lock and then putting _DONE.
    """
    returned_urls = []

    def on_search(query, hits):
        returned_urls.extend(h["url"] for h in hits if h.get("url"))
        events.put(("search", {
            "query": query,
            "results": [
                {"title": h.get("title"), "url": h.get("url"),
                 "snippet": (h.get("content") or "")[:SNIPPET_CHARS]}
                for h in hits
            ],
        }))

    previous_case = uk_evidence_search.CURRENT_CASE
    uk_evidence_search.CURRENT_CASE = "demo"
    uk_evidence_search.ON_SEARCH = on_search
    try:
        output = str(Lagomy().crew().kickoff(inputs={
            "ingredient": ingredient,
            "probe": question,
        }))
        try:
            report = build_report(output)
        except ValueError:  # no JSON block, or one that does not parse
            events.put(("error", {"message": NO_EVIDENCE_MESSAGE}))
        else:
            events.put(("report", report))
            events.put(("citations", check_citations(report["evidence"], returned_urls)))
    except Exception as e:
        # The exception type only: provider messages are not echoed anywhere.
        logger.error("Crew run failed: %s", type(e).__name__)
        events.put(("error", {"message": FAILED_MESSAGE}))
    finally:
        uk_evidence_search.ON_SEARCH = None
        uk_evidence_search.CURRENT_CASE = previous_case
        _run_lock.release()
        events.put(_DONE)


async def _stream(events: queue.Queue):
    while True:
        item = await asyncio.to_thread(events.get)
        if item is _DONE:
            yield _sse("done", {})
            return
        yield _sse(*item)


def _event_stream(body) -> StreamingResponse:
    return StreamingResponse(
        body,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- Endpoints ----------------------------------------------------------------

@app.post("/ask")
async def ask(request: AskRequest):
    ingredient = request.ingredient.strip()
    question = request.question.strip()
    if not ingredient:
        raise HTTPException(status_code=422, detail="Please enter an ingredient.")
    if len(ingredient) > MAX_INGREDIENT_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"The ingredient must be {MAX_INGREDIENT_CHARS} characters or fewer.")
    if len(question) > MAX_QUESTION_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"The question must be {MAX_QUESTION_CHARS} characters or fewer.")

    decision = check_routing(question)
    if decision:
        async def gated():
            yield _sse("gate", {"rule": decision.rule, "response": decision.response})
            yield _sse("done", {})
        return _event_stream(gated())

    _reserve_run()
    events = queue.Queue()
    threading.Thread(target=_run_crew, args=(ingredient, question, events),
                     daemon=True).start()
    return _event_stream(_stream(events))


@app.get("/health")
def health():
    return {"status": "ok"}


TEST_PAGE = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>Lagomy demo test page</title></head>
<body>
<form id="ask">
  <p><label>Ingredient <input name="ingredient" maxlength="80" required></label></p>
  <p><label>Question<br><textarea name="question" maxlength="500" rows="4" cols="60"></textarea></label></p>
  <p><button>Ask</button></p>
</form>
<pre id="out"></pre>
<script>
const out = document.getElementById("out");
document.getElementById("ask").onsubmit = async (e) => {
  e.preventDefault();
  out.textContent = "";
  const form = new FormData(e.target);
  const res = await fetch("/ask", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ingredient: form.get("ingredient"), question: form.get("question")}),
  });
  if (!res.ok) {
    out.textContent = res.status + " " + (await res.json()).detail;
    return;
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const {value, done} = await reader.read();
    if (done) break;
    buffer += value;
    let end;
    while ((end = buffer.indexOf("\\n\\n")) >= 0) {
      out.textContent += buffer.slice(0, end) + "\\n\\n";
      buffer = buffer.slice(end + 2);
    }
  }
};
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def test_page():
    return TEST_PAGE
