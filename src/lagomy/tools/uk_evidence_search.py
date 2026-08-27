import os
from crewai.tools import BaseTool
from tavily import TavilyClient


class UKEvidenceSearchTool(BaseTool):
    name: str = "UK evidence search"
    description: str = (
        "Searches authoritative UK health sources (nhs.uk, nice.org.uk, "
        "bnf.nice.org.uk) for published information about a supplement "
        "ingredient. Input should be a plain search query string."
    )

    def _run(self, query: str) -> str:
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        results = client.search(
            query=query,
            include_domains=["www.nhs.uk", "www.nice.org.uk", "bnf.nice.org.uk", "cks.nice.org.uk", "111.wales.nhs.uk"],
            max_results=3,
        )
        formatted = []
        for r in results["results"]:
            snippet = r["content"][:600]
            formatted.append(
                f"TITLE: {r['title']}\nURL: {r['url']}\nCONTENT: {snippet}\n"
            )
        return "\n".join(formatted) if formatted else "No results found from UK sources."
    