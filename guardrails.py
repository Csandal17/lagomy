"""Shared guardrail checks. Used by the eval runner and the API."""

BANNED_PHRASES = [
    "i recommend", "we recommend", "you should", "i suggest", "we suggest",
    "better than", "optimal choice",
    "that's fine", "safe for you", "no need to worry", "perfectly fine",
    "don't worry", "you have", "you are deficient", "this means you",
    "you likely",
]

def find_banned_phrases(text: str) -> list[str]:
    """Return every banned phrase present in the text."""
    lowered = text.lower()
    return [p for p in BANNED_PHRASES if p in lowered]
