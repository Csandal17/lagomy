"""check_data.py, run on small made-up sheets with the master sheet's real headers.

No real dataset is used or needed: the dataset stays out of this repository.
"""

import csv

import pytest

import check_data

HEADERS = {
    "Brands": ["brand_id", "brand_name", "website", "country", "notes"],
    "Categories": ["category"],
    "Ingredients": ["ingredient_id", "canonical_name", "synonyms", "type", "notes", "cas_number", "unii"],
    "Products": [
        "product_id", "brand_name", "product_name", "barcode_ean", "category", "form", "pack_size",
        "price_gbp", "url_source", "date_added", "notes", "data_source", "barcode_source",
        "date_verified", "units_per_day", "daily_dose_source",
    ],
    "Product_Ingredients": ["product_id", "ingredient_name", "amount", "unit", "per", "pct_nrv", "notes"],
    "Product_Warnings": ["warning_id", "product_id", "warning_type", "warning_text", "notes"],
    "Product_Claims": ["claim_id", "product_id", "ingredient", "claim_text", "source"],
}

MICRO = "µ"
GREEK_MU = "μ"


def clean_sheet():
    """A small sheet that follows every rule, based on real rows."""
    return {
        "Brands": [["B001", "Vitabiotics", "https://www.vitabiotics.com", "UK", ""]],
        "Categories": [["Vitamins"], ["Minerals"]],
        "Ingredients": [
            ["I001", "vitamin D3", "cholecalciferol; vitamin D", "vitamin", "", "67-97-0", "1C6V77QF41"],
            ["I002", "ascorbic acid", "vitamin C", "vitamin", "", "50-81-7", "PQ6CK8PD0R"],
            ["I003", "ferrous fumarate", "iron", "mineral", "", "141-01-5", "R5L488RY0Q"],
            ["I004", "turmeric", "curcuma longa", "botanical", "whole botanical", "NULL", "NULL"],
        ],
        "Products": [
            ["P001", "Vitabiotics", "Ultra Vitamin D 1000IU", "5021265248742", "Vitamins", "tablet", "96", "£5.10",
             "https://www.vitabiotics.com/products/ultra-vitamin-d-tablets", "2026-07-17", "", "brand_website",
             "retailer_instore", "2026-07-17", "1", "brand_website"],
            ["P002", "Vitabiotics", "Ultra Iron", "5021265246168", "Minerals", "tablet", "30", "£3.85",
             "https://www.vitabiotics.com/products/ultra-iron-sustained-release-tablets", "2026-07-19", "",
             "brand_website", "retailer_instore", "2026-07-19", "1", "brand_website"],
            ["P003"] + [""] * 15,  # a pre-numbered empty row
        ],
        "Product_Ingredients": [
            ["P001", "vitamin D3", "25", f"{MICRO}g", "per tablet", "500%", ""],
            ["P002", "ascorbic acid", "80", "mg", "per tablet", "100%", ""],
            ["P002", "ferrous fumarate", "14", "mg", "per tablet", "100%", ""],
            ["P002", "turmeric", "50", "mg", "per tablet", "", ""],
        ],
        "Product_Warnings": [
            ["W001", "P002", "contains_caution", "Contains iron, which if taken in excess may be harmful to very young children", ""],
        ],
        "Product_Claims": [
            ["C001", "P002", "ascorbic acid", "Vitamin C contributes to the normal function of the immune system", "label"],
        ],
    }


def write_sheet(folder, sheet, google_names=False):
    for tab, rows in sheet.items():
        name = f"lagomy_uk_supplement_tracker - {tab}.csv" if google_names else f"{tab}.csv"
        with (folder / name).open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(HEADERS[tab])
            writer.writerows(rows)


def run(tmp_path, sheet):
    write_sheet(tmp_path, sheet)
    data, missing = check_data.load(tmp_path)
    report, summary = check_data.run_checks(data)
    return report, summary


def messages(report, level=None):
    return [f"{f.tab} {f.row}: {f.message}" for f in report.findings if level is None or f.level == level]


def only_finding(report):
    assert len(report.findings) == 1, messages(report)
    return report.findings[0]


# A clean sheet ---------------------------------------------------------------


def test_clean_sheet_has_no_findings(tmp_path):
    report, summary = run(tmp_path, clean_sheet())
    assert messages(report) == []
    assert summary["products"] == 2
    assert summary["detailed"] == 2
    assert summary["reserved"] == 1
    assert summary["next_ids"] == ["P003", "I005", "W002", "C002", "B002"]


def test_google_download_names_are_found(tmp_path):
    write_sheet(tmp_path, clean_sheet(), google_names=True)
    data, missing = check_data.load(tmp_path)
    assert missing == []
    assert set(data) == set(check_data.TABS)


def test_cli_exit_codes(tmp_path, capsys):
    write_sheet(tmp_path, clean_sheet())
    assert check_data.main([str(tmp_path)]) == 0
    assert "0 errors, 0 checks" in capsys.readouterr().out

    sheet = clean_sheet()
    sheet["Product_Ingredients"][0][1] = "cholecalciferol"
    write_sheet(tmp_path, sheet)
    assert check_data.main([str(tmp_path)]) == 1
    assert "1 error, 0 checks" in capsys.readouterr().out


def test_missing_required_tab(tmp_path, capsys):
    sheet = clean_sheet()
    del sheet["Ingredients"]
    write_sheet(tmp_path, sheet)
    assert check_data.main([str(tmp_path)]) == 2
    assert "Ingredients" in capsys.readouterr().err


def test_missing_optional_tab_is_reported_and_skipped(tmp_path, capsys):
    sheet = clean_sheet()
    del sheet["Product_Claims"]
    write_sheet(tmp_path, sheet)
    assert check_data.main([str(tmp_path)]) == 0
    assert "Not found: Product_Claims.csv" in capsys.readouterr().out


# Product_Ingredients ------------------------------------------------------------


def test_synonym_instead_of_canonical_name(tmp_path):
    """The CANONICAL-NAME TRAP: the dropdown wants the exact canonical name."""
    sheet = clean_sheet()
    sheet["Product_Ingredients"][0][1] = "cholecalciferol"
    finding = only_finding(run(tmp_path, sheet)[0])
    assert finding.level == "error" and finding.row == 2
    assert "is a synonym. Use the canonical name 'vitamin D3'" in finding.message


def test_name_differing_only_in_capitals(tmp_path):
    sheet = clean_sheet()
    sheet["Product_Ingredients"][2][1] = "Ferrous Fumarate"
    assert "differs only in capitals" in only_finding(run(tmp_path, sheet)[0]).message


def test_unknown_ingredient_name(tmp_path):
    sheet = clean_sheet()
    sheet["Product_Ingredients"][2][1] = "alpha-lipoic acid"
    assert "isn't a canonical_name" in only_finding(run(tmp_path, sheet)[0]).message


def test_trailing_space_in_a_name(tmp_path):
    sheet = clean_sheet()
    sheet["Product_Ingredients"][2][1] = "ferrous fumarate "
    finding = only_finding(run(tmp_path, sheet)[0])
    assert finding.level == "error" and "space at the start or end" in finding.message


@pytest.mark.parametrize(
    "unit, expected",
    [
        ("mcg", f"should be {MICRO}g"),
        ("milligrams", "isn't one of the dropdown values"),
    ],
)
def test_bad_units(tmp_path, unit, expected):
    sheet = clean_sheet()
    sheet["Product_Ingredients"][0][3] = unit
    report = run(tmp_path, sheet)[0]
    assert any(expected in m for m in messages(report, "error")), messages(report)


def test_mixed_micro_characters(tmp_path):
    """µ (micro sign) and μ (Greek mu) look the same but don't match."""
    sheet = clean_sheet()
    sheet["Ingredients"].append(["I005", "cyanocobalamin", "vitamin B12", "vitamin", "", "68-19-9", "P6YC3EG204"])
    sheet["Product_Ingredients"] += [
        ["P002", "cyanocobalamin", "10", f"{MICRO}g", "per tablet", "400%", ""],
        ["P002", "vitamin D3", "10", f"{GREEK_MU}g", "per tablet", "200%", ""],
    ]
    finding = only_finding(run(tmp_path, sheet)[0])
    assert finding.row == 7
    assert "Greek letter mu" in finding.message


@pytest.mark.parametrize(
    "amount, expected",
    [
        ("1,000", "should be a plain number"),
        ("25µg", "should be a plain number"),
    ],
)
def test_amount_must_be_a_plain_number(tmp_path, amount, expected):
    sheet = clean_sheet()
    sheet["Product_Ingredients"][0][2] = amount
    report = run(tmp_path, sheet)[0]
    assert any(expected in m for m in messages(report, "error")), messages(report)


def test_amount_without_unit_or_per(tmp_path):
    sheet = clean_sheet()
    sheet["Product_Ingredients"][1][3] = ""
    sheet["Product_Ingredients"][1][4] = ""
    sheet["Product_Ingredients"][1][5] = ""
    errors = messages(run(tmp_path, sheet)[0], "error")
    assert any("has no unit" in m for m in errors)
    assert any("has no per value" in m for m in errors)


def test_blank_amount_needs_a_reason(tmp_path):
    sheet = clean_sheet()
    sheet["Product_Ingredients"][3] = ["P002", "turmeric", "", "", "", "", ""]
    assert "no reason in notes" in only_finding(run(tmp_path, sheet)[0]).message

    sheet["Product_Ingredients"][3][6] = "amount not stated on label"
    assert messages(run(tmp_path, sheet)[0]) == []


@pytest.mark.parametrize(
    "per, expected",
    [
        ("per 2 tablets", "Use 'per serving'"),
        ("per", "per 'per' is a leftover header word"),
        ("form", "per 'form' is a leftover header word"),
        ("daily_dose_source", "per 'daily_dose_source' is a leftover header word"),
    ],
)
def test_per_values(tmp_path, per, expected):
    sheet = clean_sheet()
    sheet["Product_Ingredients"][1][4] = per
    assert expected in only_finding(run(tmp_path, sheet)[0]).message


def test_per_serving_needs_the_serving_on_the_product(tmp_path):
    sheet = clean_sheet()
    sheet["Products"][1][14] = ""  # units_per_day
    sheet["Products"][1][15] = ""  # daily_dose_source
    for row in sheet["Product_Ingredients"][1:]:
        row[4] = "per serving"
    finding = only_finding(run(tmp_path, sheet)[0])
    assert finding.level == "check"
    assert "doesn't say what a serving is" in finding.message

    sheet["Products"][1][10] = "serving = 2 tablets daily"
    assert messages(run(tmp_path, sheet)[0]) == []


def test_pct_nrv_on_a_botanical_is_an_error(tmp_path):
    """pct_nrv is never invented: botanicals have no NRV."""
    sheet = clean_sheet()
    sheet["Product_Ingredients"][3][5] = "100%"
    finding = only_finding(run(tmp_path, sheet)[0])
    assert finding.level == "error"
    assert "is a botanical, which has no NRV" in finding.message


def test_pct_nrv_that_doesnt_match_the_amount(tmp_path):
    sheet = clean_sheet()
    sheet["Product_Ingredients"][2][5] = "200%"  # 14 mg iron is 100% of 14 mg
    finding = only_finding(run(tmp_path, sheet)[0])
    assert finding.level == "check"
    assert "doesn't match 14 mg against the iron NRV of 14 mg (100%)" in finding.message


def test_pct_nrv_with_the_wrong_unit_is_caught(tmp_path):
    sheet = clean_sheet()
    sheet["Product_Ingredients"][0][3] = "mg"  # 25 mg of vitamin D would be 500,000%
    assert "vitamin d NRV" in only_finding(run(tmp_path, sheet)[0]).message


def test_pct_nrv_rounding_is_allowed(tmp_path):
    sheet = clean_sheet()
    sheet["Product_Ingredients"][1][2] = "82"  # 102.5% printed as 103%
    sheet["Product_Ingredients"][1][5] = "103%"
    assert messages(run(tmp_path, sheet)[0]) == []


def test_pct_nrv_format(tmp_path):
    sheet = clean_sheet()
    sheet["Product_Ingredients"][1][5] = "100"
    finding = only_finding(run(tmp_path, sheet)[0])
    assert finding.level == "check" and "usual 100% form" in finding.message


def test_duplicate_row(tmp_path):
    sheet = clean_sheet()
    sheet["Product_Ingredients"].append(list(sheet["Product_Ingredients"][1]))
    assert "Is it a duplicate?" in only_finding(run(tmp_path, sheet)[0]).message


def test_same_ingredient_twice_with_different_notes_is_fine(tmp_path):
    """Multi-component packs name the component in notes."""
    sheet = clean_sheet()
    sheet["Product_Ingredients"][1][6] = "AM tablet"
    sheet["Product_Ingredients"].append(["P002", "ascorbic acid", "80", "mg", "per tablet", "100%", "PM tablet"])
    assert messages(run(tmp_path, sheet)[0]) == []


def test_ingredient_row_for_unknown_product(tmp_path):
    sheet = clean_sheet()
    sheet["Product_Ingredients"][0][0] = "P099"
    assert "P099 isn't on the Products tab" in only_finding(run(tmp_path, sheet)[0]).message


# Products ------------------------------------------------------------------


@pytest.mark.parametrize(
    "barcode, expected",
    [
        ("5021265248743", "wrong check digit"),
        ("5.02127E+12", "was turned into a number"),
        ("12345678905", "A leading zero may have been dropped"),  # UPC-A 012345678905 without its 0
        ("ABC123", "digits only"),
    ],
)
def test_bad_barcodes(tmp_path, barcode, expected):
    sheet = clean_sheet()
    sheet["Products"][0][3] = barcode
    assert expected in only_finding(run(tmp_path, sheet)[0]).message


def test_valid_upc_a_and_ean_8_pass(tmp_path):
    for barcode in ("012345678905", "96385074"):
        sheet = clean_sheet()
        sheet["Products"][0][3] = barcode
        assert messages(run(tmp_path, sheet)[0]) == [], barcode


def test_barcode_used_twice(tmp_path):
    sheet = clean_sheet()
    sheet["Products"][1][3] = sheet["Products"][0][3]
    finding = only_finding(run(tmp_path, sheet)[0])
    assert finding.level == "check" and "is also on row 2" in finding.message


def test_tbc_barcode_is_fine(tmp_path):
    sheet = clean_sheet()
    sheet["Products"][0][3] = "TBC"
    assert messages(run(tmp_path, sheet)[0]) == []


@pytest.mark.parametrize(
    "column, value, expected",
    [
        (1, "Vitabiotic", "isn't on the Brands tab"),
        (4, "Hair", "isn't on the Categories tab"),
        (5, "form", "leftover header word"),
        (11, "website", "data_source 'website' isn't one of"),
        (12, "shop", "barcode_source 'shop' isn't one of"),
        (13, "17/07/2026", "isn't a date in YYYY-MM-DD format"),
        (15, "daily_dose_source", "leftover header word"),
        (14, "one", "isn't a whole number"),
    ],
)
def test_product_field_errors(tmp_path, column, value, expected):
    sheet = clean_sheet()
    sheet["Products"][0][column] = value
    errors = messages(run(tmp_path, sheet)[0], "error")
    assert any(expected in m for m in errors), errors


def test_tbc_product_with_ingredient_rows(tmp_path):
    """The export publishes every product with ingredient rows, so a TBC stub must have none."""
    sheet = clean_sheet()
    sheet["Products"][0][11] = "TBC"
    finding = only_finding(run(tmp_path, sheet)[0])
    assert finding.row == 2
    assert "the export would publish it" in finding.message


def test_duplicate_product_id(tmp_path):
    sheet = clean_sheet()
    sheet["Products"][1][0] = "P001"
    assert any("P001 is used twice (also row 2)" in m for m in messages(run(tmp_path, sheet)[0], "error"))


# Ingredients ----------------------------------------------------------------


def test_cas_check_digit(tmp_path):
    assert check_data.cas_check_digit_ok("67-97-0")
    assert check_data.cas_check_digit_ok("7732-18-5")  # water
    sheet = clean_sheet()
    sheet["Ingredients"][1][5] = "50-81-8"
    assert "wrong check digit" in only_finding(run(tmp_path, sheet)[0]).message


def test_unii_format_and_duplicates(tmp_path):
    sheet = clean_sheet()
    sheet["Ingredients"][1][6] = "pq6ck8pd0r"
    assert "isn't 10 capital letters" in only_finding(run(tmp_path, sheet)[0]).message

    sheet = clean_sheet()
    sheet["Ingredients"][1][6] = "1C6V77QF41"
    finding = only_finding(run(tmp_path, sheet)[0])
    assert finding.level == "check" and "also on I001" in finding.message


def test_null_ids_need_a_reason(tmp_path):
    sheet = clean_sheet()
    sheet["Ingredients"][3][4] = ""
    assert "NULL with no reason in notes" in only_finding(run(tmp_path, sheet)[0]).message


def test_synonym_that_is_another_canonical_name(tmp_path):
    sheet = clean_sheet()
    sheet["Ingredients"][1][2] = "vitamin C; vitamin D3"
    assert "is the canonical name of I001" in only_finding(run(tmp_path, sheet)[0]).message


def test_duplicate_canonical_name(tmp_path):
    sheet = clean_sheet()
    sheet["Ingredients"].append(["I005", "Vitamin D3", "", "vitamin", "", "", ""])
    assert any("already used by I001" in m for m in messages(run(tmp_path, sheet)[0], "error"))


# Warnings and claims --------------------------------------------------------


def test_warning_type_and_statutory_line(tmp_path):
    sheet = clean_sheet()
    sheet["Product_Warnings"].append(["W002", "P002", "general", "Keep out of reach of children", ""])
    sheet["Product_Warnings"].append(
        ["W003", "P002", "other", "Food supplements should not be used as a substitute for a varied and balanced diet", ""]
    )
    report = run(tmp_path, sheet)[0]
    assert any("warning_type 'general'" in m for m in messages(report, "error"))
    assert any("statutory" in m for m in messages(report, "check"))


def test_claim_for_an_ingredient_the_product_doesnt_have(tmp_path):
    sheet = clean_sheet()
    sheet["Product_Claims"][0][2] = "vitamin D3"
    finding = only_finding(run(tmp_path, sheet)[0])
    assert finding.level == "check"
    assert "P002 has no Product_Ingredients row for 'vitamin D3'" in finding.message
