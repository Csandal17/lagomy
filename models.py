"""Models shared by the Evidence API and the plain-words dictionary.

EvidenceStatement is the provenance unit for both, so every statement
Lagomy shows, wherever it comes from, carries the same four fields, and
check_links.py can check the sources of both.
"""

from datetime import date

from pydantic import BaseModel


class EvidenceStatement(BaseModel):
    """One sourced claim. The provenance unit of the whole API."""
    text: str
    source_url: str
    source_authority: str   # e.g. "NHS", "NICE", "BNF"
    retrieval_date: date
