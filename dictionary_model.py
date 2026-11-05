"""The plain-words dictionary: what an entry looks like.

Entries live in dictionary/, one JSON file per term (dictionary/liposomal.json).
Each one answers a neutral question ("What does liposomal mean?") in three
sections, and every line in every section is an EvidenceStatement, the same
provenance unit the Evidence API uses: text, source_url, source_authority,
retrieval_date.

- what_it_means: a plain explanation of the term.
- what_it_doesnt_tell_you: the limits of the term. Each line carries its own
  source, or it would become a Lagomy verdict.
- what_the_evidence_says: what independent sources say, with links.

The dictionary explains the language; it doesn't police the brands using it.
No brand names, no quoted brand marketing, no rankings. check_dictionary.py
enforces the mechanical parts of that.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models import EvidenceStatement

DICTIONARY_DIR = Path(__file__).parent / "dictionary"

Category = Literal["ingredient", "formulation", "marketing claim", "measurement", "regulatory term"]

SECTIONS = ("what_it_means", "what_it_doesnt_tell_you", "what_the_evidence_says")


class DictionaryEntry(BaseModel):
    """One term, answered in three sourced sections."""

    model_config = ConfigDict(extra="forbid")

    term: str
    question: str  # neutral and free of suspicion: "What does liposomal mean?"
    synonyms: list[str] = []
    category: Category
    what_it_means: list[EvidenceStatement] = Field(min_length=1)
    what_it_doesnt_tell_you: list[EvidenceStatement] = []
    what_the_evidence_says: list[EvidenceStatement] = []
    related_terms: list[str] = []
    # Canonical names from the dataset's Ingredients tab.
    related_ingredients: list[str] = []
    # "draft" until Chantal has checked the wording against the sources.
    status: Literal["draft", "reviewed"] = "draft"
    # Editorial notes for whoever maintains the entry. Never shown to users.
    notes: str = ""

    def statements(self):
        """Every statement in the entry, with the section it's in."""
        for section in SECTIONS:
            for statement in getattr(self, section):
                yield section, statement


def slug(term: str) -> str:
    """The file name for a term: "standardised extract" -> "standardised-extract"."""
    return "-".join(term.lower().split())


def load_entries(folder: Path = DICTIONARY_DIR) -> dict[Path, dict]:
    """Every entry file's raw JSON, by path. Validation happens in check_dictionary.py."""
    return {path: json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.json"))}
