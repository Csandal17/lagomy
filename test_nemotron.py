"""Smoke test: does Nemotron on Token Factory return usable content?"""
import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url=os.environ["NEBIUS_BASE_URL"],
    api_key=os.environ["NEBIUS_API_KEY"],
)
model = os.environ["NEBIUS_MODEL"]

print("=== 1. Plain completion ===")
r = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Reply with exactly: hello"}],
    max_tokens=200,
)
msg = r.choices[0].message
print("content:", repr(msg.content))
print("finish_reason:", r.choices[0].finish_reason)
print("full message:", json.dumps(msg.model_dump(), indent=2)[:1000])

print("\n=== 2. Tool calling ===")
tools = [{
    "type": "function",
    "function": {
        "name": "search_uk_evidence",
        "description": "Search UK health authority sources for an ingredient.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}]

r2 = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Find NHS guidance on magnesium intake."}],
    tools=tools,
    max_tokens=500,
)
m2 = r2.choices[0].message
print("content:", repr(m2.content))
print("finish_reason:", r2.choices[0].finish_reason)
print("tool_calls:", m2.tool_calls)
