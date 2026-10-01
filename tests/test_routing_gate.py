import sys
from pathlib import Path

import pytest
import yaml

from lagomy.routing_gate import (
    RULE_1_RESPONSE,
    RULE_2_RESPONSE,
    RoutingDecision,
    check_routing,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# guardrails.py lives at the repo root, outside the lagomy package.
sys.path.insert(0, str(REPO_ROOT))
from guardrails import find_banned_phrases  # noqa: E402

PROBES = [
    ("cases_routing_focus.yaml", "route_latent_iron", "ingestion"),
    ("cases_routing_focus.yaml", "route_warfarin", "prescription_medicine"),
    ("guardrail_cases.yaml", "route_overdose", "ingestion"),
    ("guardrail_cases_expanded.yaml", "route_child_iron", "ingestion"),
]


def load_probe(filename: str, case_id: str) -> str:
    cases = yaml.safe_load((REPO_ROOT / filename).read_text())
    matches = [c["probe"] for c in cases if c["id"] == case_id]
    assert len(matches) == 1, f"expected one {case_id} in {filename}"
    return matches[0]


@pytest.mark.parametrize("filename, case_id, rule", PROBES)
def test_eval_probes_route_to_correct_rule(filename, case_id, rule):
    decision = check_routing(load_probe(filename, case_id))
    assert decision is not None
    assert decision.rule == rule


@pytest.mark.parametrize("question", [
    "I accidentally took about 15 iron tablets this morning",
    "I just swallowed a whole bottle of iron tablets",
    "My toddler got into my iron tablets and I don't know how many she ate",
    "I usually take 2 a day but took 15 tablets this morning",
    "I TOOK FIFTEEN CAPSULES",
])
def test_ingestion_matches(question):
    assert check_routing(question) == RoutingDecision("ingestion", RULE_1_RESPONSE)


@pytest.mark.parametrize("question", [
    "I swallowed the whole bottle of iron tablets",
    "I took all my tablets at once",
    "She ate all the pills in the packet",
    "I took a handful of pills",
    "My toddler ate a few of my iron tablets",
])
def test_ingestion_matches_extended_quantities(question):
    assert check_routing(question) == RoutingDecision("ingestion", RULE_1_RESPONSE)


def test_overdosed_matches_on_its_own():
    assert check_routing("I overdosed on iron") == RoutingDecision(
        "ingestion", RULE_1_RESPONSE
    )


@pytest.mark.parametrize("question", [
    "What happens if you overdose on iron?",
    "Can you overdose on vitamin D?",
])
def test_overdose_other_forms_do_not_match_alone(question):
    assert check_routing(question) is None


@pytest.mark.parametrize("question", [
    "I take 2 iron tablets a day",
    "should I take 3 capsules",
    "how much vitamin K is in kale",
    "is 15mg of iron a lot",
])
def test_negatives(question):
    assert check_routing(question) is None


@pytest.mark.parametrize("question", [
    "I took my B12 tablets",
    "I took my vitamin D3 capsules",
])
def test_vitamin_names_are_not_quantities(question):
    assert check_routing(question) is None


def test_ingestion_parts_must_share_a_sentence():
    assert check_routing("I took the bus. Is 3 tablets a day a lot?") is None


@pytest.mark.parametrize("question", [
    "Can I take iron with warfarin?",
    "Can I take iron with Warfarin?",
    "I'm on ELIQUIS",
])
def test_prescription_medicine_whole_word_matches(question):
    assert check_routing(question) == RoutingDecision(
        "prescription_medicine", RULE_2_RESPONSE
    )


@pytest.mark.parametrize("question", [
    "Can I take iron with antiwarfarin?",
    "Can I take iron with warfarinlike drugs?",
])
def test_prescription_medicine_ignores_longer_words(question):
    assert check_routing(question) is None


def test_ingestion_wins_when_both_rules_match():
    decision = check_routing("My dad took 20 warfarin tablets by mistake")
    assert decision is not None
    assert decision.rule == "ingestion"
    assert decision.response == RULE_1_RESPONSE


def test_decision_is_frozen():
    decision = check_routing("I took 15 tablets")
    with pytest.raises(AttributeError):
        decision.rule = "prescription_medicine"


def test_rule_1_response_passes_guardrails():
    assert find_banned_phrases(RULE_1_RESPONSE) == []
    assert "111" in RULE_1_RESPONSE


def test_rule_2_response_passes_guardrails():
    assert find_banned_phrases(RULE_2_RESPONSE) == []
    assert "GP" in RULE_2_RESPONSE
