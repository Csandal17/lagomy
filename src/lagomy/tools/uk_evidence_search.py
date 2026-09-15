import os
import json
from datetime import datetime, timezone
from pathlib import Path

from crewai.tools import BaseTool
from tavily import TavilyClient

# One log file per process run, named at import time.
LOG_DIR = Path("logs")
RUN_STAMP = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
LOG_PATH = LOG_DIR / f"search_{RUN_STAMP}.jsonl"
# Set by the eval runner before each case so log lines can be traced back.
CURRENT_CASE = "unknown"

def _log_search(query: str, results: list, error: str | None = None) -> None:
    """Append one JSON line recording a search and what it returned."""
    try:
        LOG_DIR.mkdir(exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "case": CURRENT_CASE,
            "query": query,
            "result_count": len(results),
            "results": [
                {
                    "title": r.get("title"),
                    "url": r.get("url"),
                    "content": r.get("content", "")[:600],
                }
                for r in results
            ],
        }
        if error:
            entry["error"] = error
        with LOG_PATH.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        # Logging must never break a run.
        pass


class UKEvidenceSearchTool(BaseTool):
    name: str = "UK evidence search"
    description: str = (
        "Searches authoritative UK health sources (nhs.uk, nice.org.uk, "
        "bnf.nice.org.uk) for published information about a supplement "
        "ingredient. Input should be a plain search query string."
    )

    def _run(self, query: str) -> str:
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        try:
            results = client.search(
                query=query,
                include_domains=["www.nhs.uk", "www.nice.org.uk", "bnf.nice.org.uk", "cks.nice.org.uk", "111.wales.nhs.uk"],
                max_results=3,
            )
        except Exception as e:
            _log_search(query, [], error=str(e))
            raise

        hits = results["results"]
        _log_search(query, hits)

        formatted = []
        for r in hits:
            snippet = r["content"][:600]
            formatted.append(
                f"TITLE: {r['title']}\nURL: {r['url']}\nCONTENT: {snippet}\n"
            )
        return "\n".join(formatted) if formatted else "No results found from UK sources."
    