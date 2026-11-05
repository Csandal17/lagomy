"""The plain-words dictionary: the entry format, the checks, and the first entry."""

import copy
import sys
import types
from datetime import date
from pathlib import Path

import pytest

import check_dictionary
import models
from dictionary_model import DICTIONARY_DIR, SECTIONS, DictionaryEntry, load_entries, slug

TODAY = date(2026, 11, 4)


def entry(**changes):
    """A small valid entry, with any fields replaced."""
    base = {
        "term": "bioavailability",
        "question": "What is bioavailability?",
        "synonyms": ["bioavailable"],
        "category": "measurement",
        "what_it_means": [
            {
                "text": "Bioavailability describes how much of a compound the body absorbs and can use.",
                "source_url": "https://www.gov.uk/government/publications/example",
                "source_authority": "COT",
                "retrieval_date": "2026-11-04",
            }
        ],
        "status": "reviewed",
    }
    base.update(changes)
    return base


def statement(text="A sourced line.", url="https://www.nhs.uk/conditions/vitamins-and-minerals/", authority="NHS", when="2026-11-01"):
    return {"text": text, "source_url": url, "source_authority": authority, "retrieval_date": when}


def check(*entries):
    return check_dictionary.check_entries({Path(f"{e['term']}.json"): e for e in entries}, today=TODAY)


# The real entries ---------------------------------------------------------------


def test_real_entries_have_no_errors():
    entries = load_entries()
    assert entries, "dictionary/ should hold at least the liposomal entry"
    # Real entries are checked against the real date, as check_dictionary.py does.
    errors, _ = check_dictionary.check_entries(entries)
    assert errors == []


def test_liposomal_entry():
    raw = load_entries()[DICTIONARY_DIR / "liposomal.json"]
    liposomal = DictionaryEntry.model_validate(raw)
    assert liposomal.question == "What does liposomal mean?"
    assert liposomal.category == "formulation"
    assert liposomal.status == "draft"  # until Chantal reviews it
    assert liposomal.what_it_doesnt_tell_you, "each limit needs its own source"
    assert all(s.source_authority == "COT" for _, s in liposomal.statements())
    assert liposomal.related_ingredients == ["ascorbic acid"]  # the dataset's canonical name


def test_liposomal_statements_stand_alone():
    """The app may show one statement on its own, so none may lean on another
    for its subject, and Annex A lines name the discussion paper in full."""
    liposomal = DictionaryEntry.model_validate(load_entries()[DICTIONARY_DIR / "liposomal.json"])
    texts = [s.text for _, s in liposomal.statements()]
    for text in texts:
        lowered = text.lower()
        assert "the discussion paper" not in lowered, text
        assert not lowered.startswith(("it ", "in those", "the report", "the committee recommended", "the word on its own")), text
    annex_a = [t for t in texts if "discussion paper" in t]
    assert len(annex_a) == 6
    assert all("a discussion paper reviewed by the Committee on Toxicity (COT)" in t.replace("A discussion", "a discussion") for t in annex_a)


def test_bioavailability_entry():
    bioavailability = DictionaryEntry.model_validate(load_entries()[DICTIONARY_DIR / "bioavailability.json"])
    assert bioavailability.question == "What is bioavailability?"
    assert bioavailability.category == "measurement"
    assert bioavailability.status == "draft"  # until Chantal reviews it
    assert bioavailability.related_terms == ["liposomal"]
    assert bioavailability.what_it_doesnt_tell_you and bioavailability.what_the_evidence_says
    assert all(s.source_authority == "COT" for _, s in bioavailability.statements())


def test_bioavailability_statements_stand_alone():
    """Same rule as liposomal: each statement names its own source in full."""
    bioavailability = DictionaryEntry.model_validate(load_entries()[DICTIONARY_DIR / "bioavailability.json"])
    for _, statement in bioavailability.statements():
        text = statement.text
        assert "the discussion paper" not in text.lower(), text
        assert not text.lower().startswith(("it ", "in those", "the report", "the committee noted", "the committee said", "the committee recommended", "this ")), text
        assert any(name in text for name in (
            "A discussion paper reviewed by the Committee on Toxicity (COT)",
            "The Committee on Toxicity (COT)",
            "The COT report",
        )), text


# The format -------------------------------------------------------------------


def test_a_valid_entry_passes():
    assert check(entry()) == ([], [])


@pytest.mark.parametrize(
    "changes, expected",
    [
        ({"category": "superfood"}, "category"),
        ({"what_it_means": []}, "what_it_means"),
        ({"surprise": "field"}, "surprise"),
        ({"status": "approved"}, "status"),
    ],
)
def test_format_errors(changes, expected):
    errors, _ = check(entry(**changes))
    assert any(expected in e for e in errors), errors


def test_a_statement_needs_all_four_fields():
    bad = entry()
    del bad["what_it_means"][0]["source_authority"]
    errors, _ = check(bad)
    assert any("source_authority" in e for e in errors), errors


def test_shared_model_is_the_apis_model(monkeypatch):
    """One EvidenceStatement for the API and the dictionary."""
    monkeypatch.setitem(sys.modules, "dataset", types.ModuleType("dataset"))  # skip the Hugging Face download
    monkeypatch.delitem(sys.modules, "api", raising=False)
    import api

    assert api.EvidenceStatement is models.EvidenceStatement
    assert DictionaryEntry.model_fields["what_it_means"].annotation == list[models.EvidenceStatement]


def test_sections_and_slug():
    assert SECTIONS == ("what_it_means", "what_it_doesnt_tell_you", "what_the_evidence_says")
    assert slug("Standardised Extract") == "standardised-extract"


# Sources --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, authority, expected",
    [
        ("https://www.blackpoolgp.nhs.uk/vitamins", "NHS", "regional or GP practice site"),
        ("https://www.healthline.com/nutrition/liposomal", "Healthline", "isn't on the dictionary's trusted list"),
        ("https://www.nhs.uk/conditions/vitamins-and-minerals/", "NICE", "labelled NHS, not 'NICE'"),
        ("http://www.nhs.uk/conditions/vitamins-and-minerals/", "NHS", "must start with https://"),
    ],
)
def test_source_errors(url, authority, expected):
    errors, _ = check(entry(what_it_means=[statement(url=url, authority=authority)]))
    assert any(expected in e for e in errors), errors


def test_bnf_and_nice_hosts_carry_their_own_labels():
    ok = entry(
        what_it_means=[statement(url="https://bnf.nice.org.uk/drugs/ascorbic-acid/", authority="BNF")],
        what_the_evidence_says=[statement(url="https://www.nice.org.uk/guidance/ng1", authority="NICE")],
    )
    assert check(ok)[0] == []


def test_dhsc_is_allowed_on_gov_uk_hosts_only():
    ok = entry(
        what_it_means=[statement(url="https://www.gov.uk/government/publications/technical-guidance-on-nutrition-labelling", authority="DHSC")],
        what_the_evidence_says=[statement(url="https://assets.publishing.service.gov.uk/media/x/Nutrition_Technical_Guidance.pdf", authority="DHSC")],
    )
    assert check(ok)[0] == []
    errors, _ = check(entry(what_it_means=[statement(url="https://www.nhs.uk/conditions/vitamins-and-minerals/", authority="DHSC")]))
    assert any("labelled NHS, not 'DHSC'" in e for e in errors), errors
    errors, _ = check(entry(what_it_means=[statement(url="https://cot.food.gov.uk/x", authority="DHSC")]))
    assert any("labelled COT, not 'DHSC'" in e for e in errors), errors


def test_future_retrieval_date():
    errors, _ = check(entry(what_it_means=[statement(when="2026-12-01")]))
    assert any("in the future" in e for e in errors), errors


# Wording ---------------------------------------------------------------------------


def test_advice_wording_is_blocked():
    errors, _ = check(entry(what_the_evidence_says=[statement(text="You should take the liposomal form.")]))
    assert any("you should" in e for e in errors), errors


@pytest.mark.parametrize("brand", ["Cymbiotika", "Wild Nutrition", "vitabiotics"])
def test_brand_names_are_blocked(brand):
    errors, _ = check(entry(what_it_means=[statement(text=f"{brand} uses this term on its labels.")]))
    assert any("names the brand" in e for e in errors), errors


def test_brand_check_matches_whole_words_only():
    errors, _ = check(entry(what_it_means=[statement(text="A supernova of ovals and novas.")]))
    assert errors == []


def test_em_dash_is_a_check():
    errors, checks = check(entry(what_it_means=[statement(text="Absorbed \u2014 mostly.")]))
    assert errors == []
    assert any("em dash" in c for c in checks)


@pytest.mark.parametrize("question", ["What does bioavailability actually tell you?", "Is bioavailability a myth?"])
def test_suspicious_questions_are_flagged(question):
    _, checks = check(entry(question=question))
    assert any("can sound like an accusation" in c for c in checks), checks


def test_question_mark():
    _, checks = check(entry(question="Bioavailability explained"))
    assert any("question mark" in c for c in checks)


# Entries together ---------------------------------------------------------------


def test_two_entries_cant_claim_the_same_word():
    first = entry()
    second = entry(term="absorption", question="What does absorption mean?", synonyms=["Bioavailable"])
    errors, _ = check(first, second)
    assert any("'bioavailable' is a term or synonym in more than one entry" in e for e in errors), errors


def test_related_term_without_an_entry():
    _, checks = check(entry(related_terms=["half-life"]))
    assert any("'half-life' has no entry yet" in c for c in checks)


def test_draft_status_is_a_reminder():
    _, checks = check(entry(status="draft"))
    assert any("still a draft" in c for c in checks)


def test_file_name_should_match_the_term():
    e = entry()
    errors, checks = check_dictionary.check_entries({Path("bio.json"): e}, today=TODAY)
    assert errors == []
    assert any("bioavailability.json" in c for c in checks)


def test_cli(capsys):
    assert check_dictionary.main([]) == 0
    entries = len(load_entries())
    assert f"Dictionary check: {entries} {'entry' if entries == 1 else 'entries'}, 0 errors" in capsys.readouterr().out


def test_nrv_entry():
    nrv = DictionaryEntry.model_validate(load_entries()[DICTIONARY_DIR / "nrv.json"])
    assert nrv.question == "What does % NRV mean?"
    assert nrv.category == "measurement"
    assert nrv.status == "draft"  # until Chantal reviews it
    assert "% NRV" in nrv.synonyms
    for _, statement in nrv.statements():
        assert statement.source_authority == "DHSC"
        assert "Department of Health and Social Care (DHSC)" in statement.text, statement.text
        # Food and supplement labels use the same Annex XIII values, so the entry
        # must not set NRVs and RDAs up as separate systems.
        assert "RDA" not in statement.text and "recommended daily allowance" not in statement.text.lower(), statement.text
        assert "do not apply to food supplements" not in statement.text, statement.text
