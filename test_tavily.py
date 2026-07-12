import os
from dotenv import load_dotenv
from tavily import TavilyClient

# Load the API keys from .env
load_dotenv()

# Create the Tavily client (reads TAVILY_API_KEY from the environment)
client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# One test search: an ingredient from your real log, restricted to NHS
results = client.search(
    query="Vitamin B12 supplement information site:nhs.uk",
    max_results=3,
)

# Show what came back
for r in results["results"]:
    print(r["title"])
    print(r["url"])
    print(r["content"][:150], "...")
    print()

