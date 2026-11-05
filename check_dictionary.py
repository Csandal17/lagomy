"""Check every plain-words dictionary entry in dictionary/.

Run:  python check_dictionary.py

Errors exit with status 1. They cover what the dictionary must never do:
an entry that doesn't match the format, a statement from a site that
isn't on the trusted list (or labelled with the wrong authority), a
banned advice phrase (the same list the API's guardrail uses), a brand
name, or two entries that claim the same word.

Checks never change the exit status. They're worth a look: an em dash, a
question that sounds suspicious rather than neutral, or a related term
with no entry yet.
"""

import argparse
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import ValidationError

from dictionary_model import DICTIONARY_DIR, DictionaryEntry, load_entries, slug
from guardrails import find_banned_phrases

# Which authority labels each site may carry. A host not listed here isn't a
# trusted source for the dictionary. Add to this deliberately, not to make
# an entry pass.
AUTHORITIES_BY_HOST = {
    "www.nhs.uk": {"NHS"},
    "www.nice.org.uk": {"NICE"},
    "cks.nice.org.uk": {"NICE"},
    "bnf.nice.org.uk": {"BNF"},
    "www.gov.uk": {"COT", "FSA", "DHSC"},
    "assets.publishing.service.gov.uk": {"COT", "FSA", "DHSC"},
    "cot.food.gov.uk": {"COT"},
    "www.food.gov.uk": {"FSA"},
}

# Brand names must never appear in the dictionary: it explains the language,
# not who uses it. The dataset's brands, plus brands used only as research
# references. Extend this as the dataset grows.
BRAND_NAMES = [
    "Vitabiotics", "Wild Nutrition", "Solgar", "Sainsbury's", "Vitl", "Centrum",
    "Seven Seas", "OVA", "Active Iron", "BetterYou", "Viridian", "Cymbiotika", "Healf",
]

# Words that make a question sound like an accusation rather than a question.
SUSPICIOUS_WORDS = ["actually", "really", "truth", "scam", "hype", "myth", "lie"]

EM_DASH = "\u2014"


def check_entries(entries: dict[Path, dict], today: date | None = None) -> tuple[list[str], list[str]]:
    today = today or date.today()
    errors, checks = [], []
    parsed: dict[Path, DictionaryEntry] = {}

    for path, raw in entries.items():
        try:
            parsed[path] = DictionaryEntry.model_validate(raw)
        except ValidationError as exc:
            for problem in exc.errors():
                where = ".".join(str(part) for part in problem["loc"])
                errors.append(f"{path.name}: {where}: {problem['msg']}")

    claimed = defaultdict(list)  # every word an entry can be looked up by
    for path, entry in parsed.items():
        name = path.name
        if path.stem != slug(entry.term):
            checks.append(f"{name}: the file for {entry.term!r} would usually be called {slug(entry.term)}.json.")
        for word in [entry.term] + entry.synonyms:
            claimed[word.strip().lower()].append(name)

        question = entry.question.strip()
        if not question.endswith("?"):
            checks.append(f"{name}: the question should end with a question mark.")
        for word in SUSPICIOUS_WORDS:
            if re.search(rf"\b{word}\b", question, re.I):
                checks.append(f"{name}: the question uses {word!r}, which can sound like an accusation. Keep it neutral.")

        if entry.status == "draft":
            checks.append(f"{name}: still a draft. Check the wording against the sources, then set status to \"reviewed\".")

        for section, statement in entry.statements():
            where = f"{name}: {section}: {statement.text[:50]!r}"
            parts = urlsplit(statement.source_url)
            host = (parts.hostname or "").lower()
            if parts.scheme != "https":
                errors.append(f"{where}: source_url must start with https://.")
            elif host not in AUTHORITIES_BY_HOST:
                if host.endswith(".nhs.uk"):
                    errors.append(f"{where}: {host} is a regional or GP practice site, not national NHS guidance (www.nhs.uk).")
                else:
                    errors.append(f"{where}: {host} isn't on the dictionary's trusted list.")
            elif statement.source_authority not in AUTHORITIES_BY_HOST[host]:
                allowed = ", ".join(sorted(AUTHORITIES_BY_HOST[host]))
                errors.append(f"{where}: {host} pages are labelled {allowed}, not {statement.source_authority!r}.")
            if statement.retrieval_date > today:
                errors.append(f"{where}: retrieval_date {statement.retrieval_date} is in the future.")
            if not statement.text.strip():
                errors.append(f"{name}: {section}: a statement has no text.")

            hits = find_banned_phrases(statement.text)
            if hits:
                errors.append(f"{where}: uses advice wording the guardrail blocks: {', '.join(hits)}.")
            for brand in BRAND_NAMES:
                if re.search(rf"(?<!\w){re.escape(brand)}(?!\w)", statement.text, re.I):
                    errors.append(f"{where}: names the brand {brand!r}. The dictionary explains terms, not brands.")
            if EM_DASH in statement.text:
                checks.append(f"{where}: contains an em dash.")

    for word, files in claimed.items():
        if len(set(files)) > 1:
            errors.append(f"{word!r} is a term or synonym in more than one entry: {', '.join(sorted(set(files)))}.")

    terms = {entry.term.lower() for entry in parsed.values()}
    for path, entry in parsed.items():
        for related in entry.related_terms:
            if related.lower() not in terms:
                checks.append(f"{path.name}: related term {related!r} has no entry yet.")

    return errors, checks


def plural(count: int, word: str, many: str | None = None) -> str:
    return f"{count} {word if count == 1 else (many or word + 's')}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check the plain-words dictionary entries.")
    parser.add_argument("folder", nargs="?", type=Path, default=DICTIONARY_DIR, help="Folder of entry JSON files (default: dictionary/).")
    args = parser.parse_args(argv)

    entries = load_entries(args.folder)
    if not entries:
        print(f"No entries found in {args.folder}.", file=sys.stderr)
        return 2

    errors, checks = check_entries(entries)
    print(f"Dictionary check: {plural(len(entries), 'entry', 'entries')}, {plural(len(errors), 'error')}, {plural(len(checks), 'check')}")
    for line in errors:
        print(f"  error  {line}")
    for line in checks:
        print(f"  check  {line}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
