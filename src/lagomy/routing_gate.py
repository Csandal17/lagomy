"""Deterministic pre-crew routing gate.

Inspects the user's question before any model is called and, on a match,
returns a fixed routing response. No LLM, no network, no crewai: pure
Python and the standard library, so the result is the same on every run.

Design principle: when in doubt, match. A false positive sends someone to
NHS 111 unnecessarily; a false negative is the failure this gate exists to
prevent. There are deliberately no exclusions for routine dosing phrases
("a day", "daily", "as usual"), because a real overdose can be described
alongside a routine dose ("I usually take 2 a day but took 15 this morning").

Rule 1 (ingestion): a past-tense ingestion verb, a quantity and a dose or
container noun all appear in the same sentence, in any order. The word
"overdosed" also matches on its own, anywhere in the question; "overdose",
"overdoses" and "overdosing" do not.
Rule 2 (prescription_medicine): an anticoagulant from ANTICOAGULANTS appears
as a whole word. This is a deliberate floor, not interaction coverage.
If both rules match, rule 1 wins.

How "near" is decided (rule 1): the three parts must fall within one
sentence. Sentences are split only where ., ! or ? is followed by
whitespace and then a capital letter, or at a blank line. Splitting is kept
conservative on purpose: "approx. 15 tablets" and "i took 15 tablets. i feel
fine" stay as one sentence, so a doubtful boundary widens the window rather
than breaking a match apart. Order within the sentence does not matter
("I don't know how many she ate" puts the quantity before the verb).

Digits count as a quantity unless they are attached to a preceding letter,
so the names B12, D3 and K2 are not read as amounts ("15mg" still counts).

Known false positives (rule 1):
- Past-tense routine use: "I took 2 tablets a day for three months and my
  levels are still low."
- Past-tense history: "I've taken 3 different iron tablets over the years,
  which is best?"; "I had one dose of the vaccine last year."
- "had" as possession or in another sense: "I had 3 bottles in the
  cupboard"; "I had a question about one of these tablets."
- Quantities that are not overdoses: "I took half a tablet."; "I took all
  my tablets as prescribed."
- "a few" and "all the" in other senses: "I had a few questions about
  these tablets"; "I've taken a few different tablets over the years";
  "I had tablets all the time as a child."
- "overdosed" about someone else or the past: "My friend overdosed years
  ago; are iron tablets safe for me?"

Known false negatives (rule 1), left unmatched because the vocabulary is
fixed by spec:
- Quantities outside QUANTITY_PHRASES: "a couple of capsules", "the rest of
  the tablets".
- Ingestion with no quantity or no dose noun: "I took too much iron",
  "my son drank my iron syrup".
- Present or future tense: "I'm going to take the whole bottle",
  "I'm overdosing on iron".

Known false negatives (rule 2):
- Derived forms are not whole-word matches: "I'm warfarinised".
- Anticoagulants and brands not on the list (e.g. Coumadin, heparin), and
  misspellings ("warfarine", "apixiban").
"""

import re
from dataclasses import dataclass
from typing import Literal, Optional

RULE_INGESTION = "ingestion"
RULE_PRESCRIPTION_MEDICINE = "prescription_medicine"

RULE_1_RESPONSE = (
    "This needs urgent medical advice, and Lagomy can't give it. Call NHS 111 "
    "now, even if you feel well. Call 999 or go to A&E straight away if the "
    "person is drowsy, unconscious, having a fit or struggling to breathe. "
    "Keep the packaging to show the medical team."
)

RULE_2_RESPONSE = (
    "Your question mentions a prescription medicine, and Lagomy can't advise "
    "on changes to prescribed medicines or how supplements interact with them. "
    "Speak to your GP, pharmacist or anticoagulation clinic before starting, "
    "stopping or changing any medicine or supplement."
)

# Rule 1 vocabularies. Entries are regex fragments; each is matched as a
# whole word or phrase, case-insensitively, with any whitespace between words.
INGESTION_VERBS = [
    "took", "taken", "swallowed", "had", "ate", "eaten", "downed", "necked",
    "overdosed", r"got\s+into",
]

NUMBER_WORDS = [
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety", "hundred", "dozen",
]

QUANTITY_PHRASES = [
    r"a\s+whole", r"a\s+full", r"half\s+a", r"too\s+many", r"lots\s+of",
    r"loads\s+of", "several", r"the\s+whole", r"all\s+my", r"all\s+the",
    r"a\s+handful", r"a\s+few",
    r"(?:don['’]?t|do\s+not)\s+know\s+how\s+many",
    r"not\s+sure\s+how\s+many",
    r"no\s+idea\s+how\s+many",
]

# Digits not glued to a preceding letter: "15", "15mg", "2.5" but not "B12".
DIGIT_QUANTITY = r"(?<![a-z\d])\d+(?:[.,]\d+)?"

DOSE_NOUNS = [
    "tablet", "tablets", "capsule", "capsules", "pill", "pills",
    "bottle", "bottles", "packet", "packets", "box", "boxes",
    "sachet", "sachets", "dose", "doses",
]

# Rule 2 vocabulary: anticoagulants only, generic names then UK brands.
ANTICOAGULANTS = [
    "warfarin", "apixaban", "rivaroxaban", "edoxaban", "dabigatran",
    "acenocoumarol", "phenindione",
    "eliquis", "xarelto", "lixiana", "pradaxa", "sinthrome",
]


def _whole_words(fragments: list[str]) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(fragments) + r")\b", re.IGNORECASE)


_VERB_RE = _whole_words(INGESTION_VERBS)
_QUANTITY_RE = re.compile(
    r"\b(?:" + "|".join(NUMBER_WORDS + QUANTITY_PHRASES) + r")\b"
    + "|" + DIGIT_QUANTITY,
    re.IGNORECASE,
)
_NOUN_RE = _whole_words(DOSE_NOUNS)
_ANTICOAGULANT_RE = _whole_words(ANTICOAGULANTS)
_OVERDOSED_RE = _whole_words(["overdosed"])

# Deliberately case-sensitive: a boundary needs a capital after the stop.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])|\n\s*\n")


@dataclass(frozen=True)
class RoutingDecision:
    rule: Literal["ingestion", "prescription_medicine"]
    response: str


def _matches_ingestion(question: str) -> bool:
    if _OVERDOSED_RE.search(question):
        return True
    return any(
        _VERB_RE.search(s) and _QUANTITY_RE.search(s) and _NOUN_RE.search(s)
        for s in _SENTENCE_SPLIT_RE.split(question)
    )


def check_routing(question: str) -> Optional[RoutingDecision]:
    """Return a routing decision for the question, or None if no rule matches."""
    if _matches_ingestion(question):
        return RoutingDecision(RULE_INGESTION, RULE_1_RESPONSE)
    if _ANTICOAGULANT_RE.search(question):
        return RoutingDecision(RULE_PRESCRIPTION_MEDICINE, RULE_2_RESPONSE)
    return None
