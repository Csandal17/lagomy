"""Tests for demo_api.py. No model and no Tavily: the crew and the Tavily
client are replaced for every test, and the keys are dummies."""
import asyncio
import copy
import json
import os
import queue
import re
import sys
import threading
import time
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

os.environ.update({
    "NEBIUS_API_KEY": "dummy-nebius-key",
    "NEBIUS_BASE_URL": "http://127.0.0.1:9/v1",
    "TAVILY_API_KEY": "dummy-tavily-key",
    "CREWAI_TELEMETRY_OPTOUT": "true",
    "OTEL_SDK_DISABLED": "true",
})
os.environ.pop("LAGOMY_MODEL", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
# demo_api.py lives at the repo root, outside the lagomy package.
sys.path.insert(0, str(REPO_ROOT))
import demo_api  # noqa: E402
from lagomy.routing_gate import RULE_1_RESPONSE, RULE_2_RESPONSE  # noqa: E402
from lagomy.tools import uk_evidence_search  # noqa: E402
from lagomy.tools.uk_evidence_search import UKEvidenceSearchTool  # noqa: E402

client = TestClient(demo_api.app)

UNGATED = {"ingredient": "Iron", "question": "What is the UK upper limit for iron?"}
GATED_INGESTION = {"ingredient": "Iron",
                   "question": "I took 15 iron tablets this morning and feel fine"}
GATED_WARFARIN = {"ingredient": "Vitamin K",
                  "question": "Should I stop my warfarin?"}

SEARCH_RESULTS = {
    "iron nhs": [
        {"title": "Iron - NHS", "url": "https://www.nhs.uk/vitamins-and-minerals/iron/",
         "content": "Iron is important in making red blood cells."},
    ],
    "iron upper limit uk": [
        {"title": "Ferrous sulfate | BNF", "url": "https://bnf.nice.org.uk/drugs/ferrous-sulfate",
         "content": "x" * 700},
        {"title": "Iron deficiency anaemia - NHS",
         "url": "https://www.nhs.uk/conditions/iron-deficiency-anaemia/",
         "content": "Iron deficiency anaemia is caused by a lack of iron."},
    ],
}

EVIDENCE = {
    "canonical_name": "Iron",
    "role": [{
        "text": "Iron is important in making red blood cells.",
        # Returned with a trailing slash; matches after normalisation.
        "source_url": "https://www.nhs.uk/vitamins-and-minerals/iron",
        "source_authority": "NHS",
    }],
    "upper_limit": [{
        "text": "Taking 17mg or less a day is unlikely to cause any harm.",
        "source_url": "https://www.nhs.uk/conditions/iron-deficiency-anemia/",
        "source_authority": "NHS",
    }],
}


def crew_output(prose: str, evidence: dict = EVIDENCE) -> str:
    return f"{prose}\n\n```json\n{json.dumps(evidence, indent=2)}\n```"


class FakeCrew:
    """Stands in for Lagomy().crew(): runs the real search tool (against a
    fake Tavily) for each query, optionally holds, then returns output."""

    def __init__(self):
        self.constructed = 0
        self.inputs = []
        self.queries = ["iron nhs", "iron upper limit uk"]
        self.output = crew_output("Iron helps the body make red blood cells.")
        self.hold = False
        self.started = threading.Event()
        self.release = threading.Event()
        self.tavily_calls = []

    def kickoff(self, inputs):
        self.inputs.append(inputs)
        tool = UKEvidenceSearchTool()
        for q in self.queries:
            tool._run(q)
        if self.hold:
            self.started.set()
            assert self.release.wait(10), "test never released the crew"
        return self.output


@pytest.fixture(autouse=True)
def fake(monkeypatch, tmp_path):
    crew = FakeCrew()

    class FakeLagomy:
        def __init__(self):
            crew.constructed += 1

        def crew(self):
            return crew

    class FakeTavily:
        def __init__(self, api_key=None):
            pass

        def search(self, query, **kwargs):
            crew.tavily_calls.append(query)
            return {"results": copy.deepcopy(SEARCH_RESULTS[query])}

    monkeypatch.setattr(demo_api, "Lagomy", FakeLagomy)
    monkeypatch.setattr(uk_evidence_search, "TavilyClient", FakeTavily)
    monkeypatch.setattr(uk_evidence_search, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(uk_evidence_search, "LOG_PATH", tmp_path / "logs" / "search.jsonl")
    monkeypatch.setattr(demo_api, "DAILY_RUN_LIMIT", 30)
    monkeypatch.setattr(demo_api, "_runs_day", None)
    monkeypatch.setattr(demo_api, "_runs_today", 0)
    yield crew
    crew.release.set()
    wait_until_unlocked()
    assert uk_evidence_search.ON_SEARCH is None


def wait_until_unlocked(timeout=10):
    deadline = time.monotonic() + timeout
    while demo_api._run_lock.locked():
        assert time.monotonic() < deadline, "run lock never released"
        time.sleep(0.01)


def parse_sse(text: str) -> list[tuple[str, object]]:
    events = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def ask(body):
    return client.post("/ask", json=body)


def search_log_lines(tmp_path):
    path = tmp_path / "logs" / "search.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


# --- Routing gate -------------------------------------------------------------

@pytest.mark.parametrize("body, rule, response", [
    (GATED_INGESTION, "ingestion", RULE_1_RESPONSE),
    (GATED_WARFARIN, "prescription_medicine", RULE_2_RESPONSE),
])
def test_gated_question_returns_gate_then_done_without_crew(fake, body, rule, response):
    r = ask(body)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert parse_sse(r.text) == [
        ("gate", {"rule": rule, "response": response}),
        ("done", {}),
    ]
    assert fake.constructed == 0
    assert fake.tavily_calls == []


# --- Ungated run --------------------------------------------------------------

def test_ungated_question_streams_searches_report_citations_done(fake):
    r = ask(UNGATED)
    assert r.status_code == 200
    events = parse_sse(r.text)
    assert [e for e, _ in events] == ["search", "search", "report", "citations", "done"]

    assert fake.constructed == 1
    assert fake.inputs == [{"ingredient": "Iron", "probe": UNGATED["question"]}]

    first, second = events[0][1], events[1][1]
    assert first == {"query": "iron nhs", "results": [{
        "title": "Iron - NHS",
        "url": "https://www.nhs.uk/vitamins-and-minerals/iron/",
        "snippet": "Iron is important in making red blood cells.",
    }]}
    assert second["query"] == "iron upper limit uk"
    assert [h["url"] for h in second["results"]] == [
        "https://bnf.nice.org.uk/drugs/ferrous-sulfate",
        "https://www.nhs.uk/conditions/iron-deficiency-anaemia/",
    ]
    assert len(second["results"][0]["snippet"]) == 600

    assert events[2][1] == {
        "prose": "Iron helps the body make red blood cells.",
        "evidence": EVIDENCE,
        "prose_withheld": False,
        "matched_phrases": [],
    }


def test_search_events_arrive_while_crew_is_running(fake):
    fake.hold = True
    events = queue.Queue()
    demo_api._run_lock.acquire()  # _run_crew releases it, as after _reserve_run
    worker = threading.Thread(target=demo_api._run_crew,
                              args=("Iron", UNGATED["question"], events))
    worker.start()
    assert fake.started.wait(5)
    assert events.get(timeout=5)[0] == "search"
    assert events.get(timeout=5)[0] == "search"
    assert worker.is_alive()
    assert events.empty()
    fake.release.set()
    worker.join(5)
    assert [events.get_nowait()[0] for _ in range(2)] == ["report", "citations"]
    assert events.get_nowait() is demo_api._DONE


def test_banned_phrase_in_prose_withholds_prose_but_ships_evidence(fake):
    fake.output = crew_output("You should take iron with vitamin C. That's fine for most people.")
    report = dict(parse_sse(ask(UNGATED).text))["report"]
    assert report == {
        "prose": None,
        "evidence": EVIDENCE,
        "prose_withheld": True,
        "matched_phrases": ["you should", "that's fine"],
    }


def test_banned_phrase_only_in_evidence_does_not_withhold_prose(fake):
    evidence = copy.deepcopy(EVIDENCE)
    evidence["role"][0]["text"] = "You should be able to get all the iron you need from your diet."
    fake.output = crew_output("Iron helps the body make red blood cells.", evidence)
    report = dict(parse_sse(ask(UNGATED).text))["report"]
    assert report["prose"] == "Iron helps the body make red blood cells."
    assert report["prose_withheld"] is False
    assert report["evidence"] == evidence


def test_unfenced_evidence_is_removed_from_prose_and_cannot_withhold_it(fake):
    evidence = copy.deepcopy(EVIDENCE)
    evidence["role"][0]["text"] = "You should be able to get all the iron you need from your diet."
    fake.output = ("Iron helps the body make red blood cells.\n\n"
                   + json.dumps(evidence, indent=2))
    report = dict(parse_sse(ask(UNGATED).text))["report"]
    assert report["evidence"] == evidence
    assert report["prose"] == "Iron helps the body make red blood cells."
    assert "{" not in report["prose"] and "source_url" not in report["prose"]
    assert report["prose_withheld"] is False
    assert report["matched_phrases"] == []


@pytest.mark.parametrize("output", [
    "Before.\n```json\n{json}\n```\nAfter.",
    "Before.\n```\n{json}\n```\nAfter.",
    "Before.\n{json}\nAfter.",
])
def test_evidence_json_is_cut_out_wherever_it_sits(output):
    evidence, prose = demo_api.split_output(output.replace("{json}", json.dumps(EVIDENCE)))
    assert evidence == EVIDENCE
    assert prose == "Before.\n\nAfter."


def test_old_page_wording_is_gone():
    page = client.get("/").text
    assert "No UK source found." not in page
    assert 'href="https://github.com/Csandal17/lagomy"' not in page


def test_citations_flag_urls_no_search_returned(fake):
    citations = dict(parse_sse(ask(UNGATED).text))["citations"]
    assert citations == [
        {"url": "https://www.nhs.uk/vitamins-and-minerals/iron", "in_search_results": True},
        {"url": "https://www.nhs.uk/conditions/iron-deficiency-anemia/", "in_search_results": False},
    ]


def test_output_without_evidence_block_is_an_error(fake):
    fake.output = "I could not find anything."
    events = parse_sse(ask(UNGATED).text)
    assert [e for e, _ in events] == ["search", "search", "error", "done"]


def test_crew_failure_is_an_error_event_without_details(fake):
    def boom(inputs):
        raise RuntimeError("upstream said dummy-nebius-key is invalid")
    fake.kickoff = boom
    events = parse_sse(ask(UNGATED).text)
    assert events == [("error", {"message": demo_api.FAILED_MESSAGE}), ("done", {})]
    assert not demo_api._run_lock.locked()


# --- Credit protection --------------------------------------------------------

def test_second_request_while_a_run_is_active_gets_429(fake):
    fake.hold = True
    first = {}
    worker = threading.Thread(target=lambda: first.update(r=ask(UNGATED)))
    worker.start()
    assert fake.started.wait(5)

    busy = ask(UNGATED)
    assert busy.status_code == 429
    assert busy.json() == {"detail": demo_api.BUSY_MESSAGE}
    # The gate does not wait for the lock.
    assert parse_sse(ask(GATED_INGESTION).text)[0][0] == "gate"

    fake.release.set()
    worker.join(10)
    assert [e for e, _ in parse_sse(first["r"].text)][-3:] == ["report", "citations", "done"]
    assert ask(UNGATED).status_code == 200


def test_lock_held_until_crew_finishes_even_if_client_disconnects(fake):
    fake.hold = True
    body = json.dumps(UNGATED).encode()

    async def scenario():
        received = []

        async def receive():
            if not received:
                received.append(1)
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message):
            pass

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "POST", "scheme": "http", "path": "/ask", "raw_path": b"/ask",
            "query_string": b"", "root_path": "",
            "headers": [(b"content-type", b"application/json"), (b"host", b"test")],
            "client": ("test", 1), "server": ("test", 80),
        }
        await demo_api.app(scope, receive, send)  # returns once the client is gone
        assert fake.started.wait(5)
        assert demo_api._run_lock.locked()
        assert ask(UNGATED).status_code == 429
        fake.release.set()
        await asyncio.to_thread(wait_until_unlocked)

    asyncio.run(scenario())
    assert ask(UNGATED).status_code == 200


def test_daily_cap_returns_429_and_gated_questions_do_not_count(fake, monkeypatch):
    monkeypatch.setattr(demo_api, "DAILY_RUN_LIMIT", 2)
    for _ in range(3):
        assert parse_sse(ask(GATED_INGESTION).text)[0][0] == "gate"
    assert ask(UNGATED).status_code == 200
    assert ask(UNGATED).status_code == 200

    capped = ask(UNGATED)
    assert capped.status_code == 429
    assert capped.json() == {"detail": demo_api.CAP_MESSAGE}
    assert parse_sse(ask(GATED_WARFARIN).text)[0][0] == "gate"
    assert fake.constructed == 2

    tomorrow = demo_api._today() + timedelta(days=1)
    monkeypatch.setattr(demo_api, "_today", lambda: tomorrow)
    assert ask(UNGATED).status_code == 200


# --- Search tool hook ---------------------------------------------------------

EXPECTED_TOOL_OUTPUT = (
    "TITLE: Ferrous sulfate | BNF\nURL: https://bnf.nice.org.uk/drugs/ferrous-sulfate\n"
    f"CONTENT: {'x' * 600}\n"
    "\n"
    "TITLE: Iron deficiency anaemia - NHS\n"
    "URL: https://www.nhs.uk/conditions/iron-deficiency-anaemia/\n"
    "CONTENT: Iron deficiency anaemia is caused by a lack of iron.\n"
)


def _log_without_timestamp(tmp_path):
    return [{k: v for k, v in line.items() if k != "timestamp"}
            for line in search_log_lines(tmp_path)]


def test_search_tool_without_hook_behaves_as_before(fake, tmp_path):
    assert uk_evidence_search.ON_SEARCH is None
    out = UKEvidenceSearchTool()._run("iron upper limit uk")
    assert out == EXPECTED_TOOL_OUTPUT
    assert _log_without_timestamp(tmp_path) == [{
        "case": uk_evidence_search.CURRENT_CASE,
        "query": "iron upper limit uk",
        "result_count": 2,
        "results": [
            {"title": "Ferrous sulfate | BNF",
             "url": "https://bnf.nice.org.uk/drugs/ferrous-sulfate",
             "content": "x" * 600},
            {"title": "Iron deficiency anaemia - NHS",
             "url": "https://www.nhs.uk/conditions/iron-deficiency-anaemia/",
             "content": "Iron deficiency anaemia is caused by a lack of iron."},
        ],
    }]


@contextmanager
def search_hook(hook):
    # Set and cleared here, not with monkeypatch, because the fake fixture's
    # teardown checks that nothing left a hook behind.
    uk_evidence_search.ON_SEARCH = hook
    try:
        yield
    finally:
        uk_evidence_search.ON_SEARCH = None


def test_search_tool_with_hook_returns_and_logs_the_same(fake, tmp_path):
    calls = []
    with search_hook(lambda query, hits: calls.append((query, hits))):
        out = UKEvidenceSearchTool()._run("iron upper limit uk")
    assert out == EXPECTED_TOOL_OUTPUT
    assert calls == [("iron upper limit uk", SEARCH_RESULTS["iron upper limit uk"])]
    assert len(search_log_lines(tmp_path)) == 1


def test_search_tool_hook_failure_does_not_break_the_search(fake):
    def broken(query, hits):
        raise RuntimeError("hook failed")
    with search_hook(broken):
        assert UKEvidenceSearchTool()._run("iron upper limit uk") == EXPECTED_TOOL_OUTPUT


# --- Validation and other endpoints -------------------------------------------

@pytest.mark.parametrize("body", [
    {"ingredient": "", "question": "What is iron for?"},
    {"ingredient": "   ", "question": "What is iron for?"},
    {"ingredient": "x" * 81, "question": "What is iron for?"},
    {"ingredient": "Iron", "question": "x" * 501},
    {"ingredient": "Iron"},
    {"ingredient": 12, "question": "What is iron for?"},
])
def test_invalid_input_returns_422_with_plain_message(fake, body):
    r = ask(body)
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)
    assert fake.constructed == 0


def test_limits_are_inclusive(fake):
    r = ask({"ingredient": "x" * 80, "question": "y" * 500})
    assert r.status_code == 200


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


PAGE_PALETTE = {"#f4f2ea", "#e7e3d6", "#c8d5bb", "#b2c0aa", "#9eac9b", "#8e9b92",
                "#383b30", "#2b2e26"}


def test_demo_page_is_served_with_its_key_elements():
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    page = r.text
    for text in [
        "<h1>Lagomy</h1>",
        "A little less. A lot clearer.",
        "NVIDIA Nemotron 3 Nano",
        "Nebius Token Factory",
        "Tavily",
        '<input id="ingredient" name="ingredient" maxlength="80"',
        '<textarea id="question" name="question" maxlength="500"',
        "What is the UK reference intake for vitamin D?",
        "I accidentally took about 15 iron tablets this morning but I feel "
        "completely fine now. Do I still need to do anything?",
        "A full answer takes a few minutes.",
        "The summary was withheld because it contained a phrase Lagomy's safety "
        "check blocks. The sourced evidence is below.",
        "This question was answered by Lagomy's routing check. No search was run "
        "and no model was called.",
        "Not among this run's search results",
        "How we know",
        "<td>5 of 32</td><td>10 of 10</td>",
        "<td>4 of 32</td><td>10 of 10</td>",
        "by construction",
        "55 of 174",
        'href="https://github.com/Csandal17/lagomy/blob/hackathon/nemotron/results/FINDINGS.md"',
        "the findings on GitHub",
        "Runs that correctly routed the four safety test cases",
        "No source cited for this.",
        "Show more",
        'aria-expanded',
        'fetch("/ask"',
        "family=Fraunces",
        "family=Hanken+Grotesk",
    ]:
        assert text in page, text
    assert '<form id="ask">' not in page  # not the bare test page


def test_demo_page_never_injects_html_and_uses_only_the_palette():
    page = client.get("/").text
    assert "innerHTML" not in page
    assert "EventSource" not in page
    colours = {c.lower() for c in re.findall(r"#[0-9A-Fa-f]{6}\b", page)}
    assert colours <= PAGE_PALETTE


def test_bare_test_page_is_served_at_test():
    r = client.get("/test")
    assert r.status_code == 200
    assert '<form id="ask">' in r.text
    assert "Lagomy demo test page" in r.text
