"""audit_sources.py, run on a small made-up evidence store."""

import json

import pytest

import audit_sources as a


def statement(url, authority="NHS"):
    return {"text": "A made-up statement.", "source_url": url, "source_authority": authority, "retrieval_date": "2026-11-05"}


def entry(**fields):
    evidence = {"canonical_name": "x", **{f: [] for f in a.FIELDS}}
    evidence.update(fields)
    return {"evidence": evidence, "prose": "", "computed_on": "2026-11-05"}


def made_up_store():
    return {
        "Vitamin D": entry(
            role=[statement("https://www.nhs.uk/conditions/vitamins-and-minerals/vitamin-d/")],
            upper_limit=[statement("https://bnf.nice.org.uk/drugs/colecalciferol/", "BNF")],
        ),
        "Iron": entry(
            role=[statement("https://www.nice.org.uk/guidance/ng1", "NICE")],
            food_sources=[statement("https://cks.nice.org.uk/topics/anaemia/", "NICE")],
        ),
        "Quercetin": entry(
            role=[statement("https://www.examplegp.nhs.uk/leaflets/quercetin")],
            regulatory_flags=[statement("https://www.examplehospital.nhs.uk/formulary", "NICE")],
        ),
        "Ashwagandha": entry(role=[statement("https://www.example.com/ashwagandha", "NHS")]),
        "Empty": entry(),
    }


@pytest.mark.parametrize(
    "url, group",
    [
        ("https://www.nhs.uk/a", a.NATIONAL_NHS),
        ("https://WWW.NHS.UK./a", a.NATIONAL_NHS),
        ("https://111.wales.nhs.uk/a", a.OTHER_NHS),
        ("https://primarycare.northeastlondon.icb.nhs.uk/a", a.OTHER_NHS),
        ("https://www.nice.org.uk/a", a.NICE),
        ("https://cks.nice.org.uk/a", a.NICE),
        ("https://bnf.nice.org.uk/a", a.BNF),
        ("https://notnhs.uk/a", a.OTHER),
        ("https://www.nhs.uk.example.com/a", a.OTHER),
        ("https://fakenice.org.uk/a", a.OTHER),
        ("not a url", a.OTHER),
    ],
)
def test_classify(url, group):
    assert a.classify_host(a.host_of(url)) == group


def test_audit_groups_and_labels():
    result = a.audit(made_up_store())
    rows = result["rows"]
    assert len(rows) == 7
    groups = [r["group"] for r in rows]
    assert groups.count(a.NATIONAL_NHS) == 1 and groups.count(a.BNF) == 1
    assert groups.count(a.NICE) == 2 and groups.count(a.OTHER_NHS) == 2 and groups.count(a.OTHER) == 1
    mismatched = {(r["ingredient"], r["host"], r["label"]) for r in rows if not r["label_matches"]}
    assert mismatched == {
        ("Quercetin", "www.examplegp.nhs.uk", "NHS"),
        ("Quercetin", "www.examplehospital.nhs.uk", "NICE"),
        ("Ashwagandha", "www.example.com", "NHS"),
    }


def test_only_non_national_and_empty_ingredients():
    result = a.audit(made_up_store())
    assert result["only_non_national"] == ["Quercetin", "Ashwagandha"]
    assert result["no_statements"] == ["Empty"]


def test_report_and_cli(tmp_path, capsys):
    store_path = tmp_path / "store.json"
    store_path.write_text(json.dumps(made_up_store()))
    before = store_path.read_text()
    out = tmp_path / "results" / "audit.md"

    assert a.main(["--store", str(store_path), "--out", str(out)]) == 0
    report = out.read_text()
    assert report == capsys.readouterr().out
    assert store_path.read_text() == before  # the store is only read

    assert "5 ingredients, 7 statements" in report
    assert "| national NHS | 1 | 1 | 1 |" in report
    assert "| other NHS organisations | 2 | 2 | 1 |" in report
    assert "| www.examplegp.nhs.uk | 1 |" in report
    assert "| Quercetin | role | other NHS organisations | www.examplegp.nhs.uk | https://www.examplegp.nhs.uk/leaflets/quercetin |" in report
    assert "| Iron |" not in report.split("## Every non-national citation")[1].split("## Labels")[0]
    assert "- Quercetin: www.examplegp.nhs.uk, www.examplehospital.nhs.uk" in report
    assert "- Empty" in report
