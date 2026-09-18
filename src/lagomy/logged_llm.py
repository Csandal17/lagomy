"""OpenAICompletion subclass that logs each raw response, including reasoning.

Overrides a private CrewAI method (_get_sync_client), so a CrewAI upgrade
may break this. Pinned to crewai 1.15.21.
"""
import json
from datetime import datetime, timezone

from crewai.llms.providers.openai.completion import OpenAICompletion

from lagomy.tools import uk_evidence_search
from lagomy.tools.uk_evidence_search import LOG_DIR, RUN_STAMP

RESPONSE_LOG_PATH = LOG_DIR / f"responses_{RUN_STAMP}.jsonl"


def _log_response(response) -> None:
    """Append one JSON line per LLM response. Never raises."""
    try:
        LOG_DIR.mkdir(exist_ok=True)
        choice = response.choices[0]
        message = choice.message
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "case": uk_evidence_search.CURRENT_CASE,
            "finish_reason": choice.finish_reason,
            "reasoning": getattr(message, "reasoning", None),
            "content": message.content,
            "tool_calls": [
                {"name": tc.function.name, "arguments": tc.function.arguments}
                for tc in (message.tool_calls or [])
            ],
        }
        with RESPONSE_LOG_PATH.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(">>> _log_response failed:", type(e).__name__, e)


class _LoggingRawResponse:
    def __init__(self, inner):
        self._inner = inner

    def create(self, *args, **kwargs):
        print(">>> _LoggingRawResponse.create called")
        try:
            raw = self._inner.create(*args, **kwargs)
        except Exception as e:
            print(">>> inner.create raised:", type(e).__name__, e)
            raise
        print(">>> raw response received")
        return raw

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _LoggingCompletions:
    def __init__(self, inner):
        self._inner = inner
        self.with_raw_response = _LoggingRawResponse(inner.with_raw_response)

    def create(self, *args, **kwargs):
        print(">>> _LoggingCompletions.create called")
        response = self._inner.create(*args, **kwargs)
        _log_response(response)
        return response

    def __getattr__(self, name):
        return getattr(self._inner, name)

class _LoggingChat:
    def __init__(self, inner):
        self._inner = inner
        self.completions = _LoggingCompletions(inner.completions)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _LoggingClient:
    def __init__(self, inner):
        self._inner = inner
        self.chat = _LoggingChat(inner.chat)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class LoggedOpenAICompletion(OpenAICompletion):
    """Same as OpenAICompletion, but every response is logged on its way back."""

    def _get_sync_client(self):
        client = super()._get_sync_client()
        print(">>> LoggedOpenAICompletion._get_sync_client called")
        if not isinstance(client, _LoggingClient):
            client = _LoggingClient(client)
            self._client = client
        print(">>> returning client type:", type(client).__name__)
        return client
    