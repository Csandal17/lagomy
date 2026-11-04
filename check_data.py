"""Check the Lagomy master sheet against the dataset's own rules.

How to run it:

1. In Google Sheets, open lagomy_uk_supplement_tracker. For each of these
   tabs, open it and choose File > Download > Comma-separated values:
   Products, Ingredients, Product_Ingredients, Product_Warnings,
   Product_Claims, Brands, Categories.
2. Put the downloaded files in one folder (for example sheet_export/ in
   this repo, which .gitignore keeps out of git). Google's file names,
   like "lagomy_uk_supplement_tracker - Products.csv", work as they are.
3. Run:  python check_data.py sheet_export

What it reports:

- An error breaks one of the dataset's rules (a name that doesn't match
  the dictionary, a unit that isn't on the list, a barcode whose check
  digit is wrong). The script exits with status 1 if there are any.
- A check is something to look at against the label. It may be correct as
  printed (labels sometimes round % NRV their own way), so it never
  changes the exit status.

Row numbers are the sheet's own, so row 2 is the first row under the
headers. The script only reads the files: it changes nothing, uploads
nothing, and needs nothing beyond Python itself.
"""

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

TABS = ["Products", "Ingredients", "Product_Ingredients", "Product_Warnings", "Product_Claims", "Brands", "Categories"]
REQUIRED_TABS = ["Products", "Ingredients", "Product_Ingredients"]

# Dropdown values, as set in the sheet. The sheet's own dropdowns also
# contain a few leftover header words ("form", "per", "daily_dose_source"),
# which are deliberately not valid here.
UNITS = {"mg", "µg", "μg", "g", "IU", "ml", "billion CFU", "other"}
PER_VALUES = {"per capsule", "per serving", "per tablet", "per spray"}
FORMS = {"capsule", "liquid", "other", "tablet", "gummy"}
DATA_SOURCES = {"brand_website", "label_photo", "retailer", "TBC"}
BARCODE_SOURCES = {"retailer_instore", "label_photo", "TBC"}
DAILY_DOSE_SOURCES = {"label_photo", "brand_website", "retailer_instore", "TBC"}
STATUSES = {"current", "delisted", "unknown"}
INGREDIENT_TYPES = {"vitamin", "mineral", "botanical", "amino acid", "fatty acid", "probiotic", "enzyme", "other"}
WARNING_TYPES = {"allergen", "interaction", "upper_limit", "population", "contains_caution", "storage", "other"}
HEADER_LEFTOVERS = {"form", "per", "daily_dose_source"}

# Ingredient types that have no NRV, so a % NRV on them can't be right.
NO_NRV_TYPES = {"botanical", "amino acid", "fatty acid", "probiotic", "enzyme"}

# Two characters look like "µ": the micro sign (U+00B5) and the Greek
# letter mu (U+03BC). They don't match each other, so the dataset should
# use one throughout.
MICRO_SIGN = "µ"
GREEK_MU = "μ"

# Nutrient reference values for adults, from Regulation (EU) No 1169/2011,
# Annex XIII Part A (retained in Great Britain). Used only to sanity-check
# a row's % NRV against its amount; nothing here is written to the data.
NRV = {
    "vitamin a": (800, "µg"),
    "vitamin d": (5, "µg"),
    "vitamin e": (12, "mg"),
    "vitamin k": (75, "µg"),
    "vitamin c": (80, "mg"),
    "thiamin": (1.1, "mg"),
    "riboflavin": (1.4, "mg"),
    "niacin": (16, "mg"),
    "vitamin b6": (1.4, "mg"),
    "folic acid": (200, "µg"),
    "vitamin b12": (2.5, "µg"),
    "biotin": (50, "µg"),
    "pantothenic acid": (6, "mg"),
    "potassium": (2000, "mg"),
    "chloride": (800, "mg"),
    "calcium": (800, "mg"),
    "phosphorus": (700, "mg"),
    "magnesium": (375, "mg"),
    "iron": (14, "mg"),
    "zinc": (10, "mg"),
    "copper": (1, "mg"),
    "manganese": (2, "mg"),
    "fluoride": (3.5, "mg"),
    "selenium": (55, "µg"),
    "chromium": (40, "µg"),
    "molybdenum": (50, "µg"),
    "iodine": (150, "µg"),
}
# Everyday names that mean the same nutrient. Matching is exact on these
# names only (never by substring), so an ingredient that matches nothing
# is simply not checked rather than checked against the wrong NRV.
NRV_NAMES = {
    **{name: name for name in NRV},
    "vitamin d2": "vitamin d", "vitamin d3": "vitamin d",
    "vitamin k1": "vitamin k", "vitamin k2": "vitamin k",
    "thiamine": "thiamin", "vitamin b1": "thiamin",
    "vitamin b2": "riboflavin",
    "vitamin b3": "niacin",
    "folate": "folic acid", "folacin": "folic acid", "vitamin b9": "folic acid",
    "vitamin b7": "biotin",
    "vitamin b5": "pantothenic acid",
}
TO_MICROGRAMS = {"g": 1_000_000, "mg": 1000, MICRO_SIGN + "g": 1, GREEK_MU + "g": 1}

PLAIN_NUMBER = re.compile(r"^\d+(\.\d+)?$")
PCT_NRV = re.compile(r"^[<>]?\d+(\.\d+)?%$")
CAS = re.compile(r"^(\d{2,7})-(\d{2})-(\d)$")
UNII = re.compile(r"^[A-Z0-9]{10}$")
PRICE = re.compile(r"^£\d+(\.\d{2})?$")
STATUTORY_LINE = re.compile(r"should not be used as a substitute for a varied", re.I)
NULL_WORDS = {"", "NULL", "TBC"}


@dataclass
class Finding:
    tab: str
    row: int | None  # the sheet's row number; None for whole-tab findings
    level: str  # "error" or "check"
    message: str


class Report:
    def __init__(self):
        self.findings: list[Finding] = []
        self.notes: list[str] = []

    def error(self, tab, row, message):
        self.findings.append(Finding(tab, row, "error", message))

    def check(self, tab, row, message):
        self.findings.append(Finding(tab, row, "check", message))

    @property
    def errors(self):
        return [f for f in self.findings if f.level == "error"]

    @property
    def checks(self):
        return [f for f in self.findings if f.level == "check"]


# Reading the files ----------------------------------------------------------


def find_tab_file(folder: Path, tab: str) -> Path | None:
    """Find a tab's CSV: "Products.csv", or Google's "<title> - Products.csv"."""
    exact = folder / f"{tab}.csv"
    if exact.exists():
        return exact
    matches = sorted(folder.glob(f"* - {tab}.csv"))
    return matches[0] if matches else None


def read_tab(path: Path) -> list[tuple[int, dict]]:
    """Rows as (sheet row number, {column: value}), skipping fully blank rows."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for i, row in enumerate(reader, start=2):
            clean = {(k or "").strip(): (v if v is not None else "") for k, v in row.items() if k is not None}
            if any(value.strip() for value in clean.values()):
                rows.append((i, clean))
        return rows


def load(folder: Path) -> tuple[dict, list[str]]:
    data, missing = {}, []
    for tab in TABS:
        path = find_tab_file(folder, tab)
        if path is None:
            missing.append(tab)
        else:
            data[tab] = read_tab(path)
    return data, missing


# Small helpers --------------------------------------------------------------


def value(row: dict, column: str) -> str:
    return (row.get(column) or "").strip()


def normalise(name: str) -> str:
    return " ".join(name.lower().replace("-", " ").split())


# Free-text columns, where a stray space doesn't break anything.
FREE_TEXT = {"notes", "warning_text", "claim_text", "source", "synonyms", "url_source", "product_name", "website", "country"}


def check_spaces(report, tab, number, row):
    """A space at the start or end of an ID, name or dropdown value stops it
    matching, even though it looks identical in the sheet."""
    for column, raw in row.items():
        if column not in FREE_TEXT and raw and raw != raw.strip():
            report.error(tab, number, f"{column} {raw!r} has a space at the start or end, so it won't match.")


def check_ids(report, tab, rows, column, prefix):
    """IDs look like P001 and are unique. Returns {id: row number}."""
    pattern = re.compile(rf"^{prefix}\d{{3,}}$")
    seen = {}
    for number, row in rows:
        ident = value(row, column)
        if not ident:
            report.error(tab, number, f"{column} is blank.")
        elif not pattern.match(ident):
            report.error(tab, number, f"{column} {ident!r} isn't in the {prefix}001 format.")
        elif ident in seen:
            report.error(tab, number, f"{column} {ident} is used twice (also row {seen[ident]}).")
        else:
            seen[ident] = number
    return seen


def next_id(ids, prefix):
    numbers = [int(i[len(prefix):]) for i in ids if re.match(rf"^{prefix}\d+$", i)]
    return f"{prefix}{(max(numbers) + 1 if numbers else 1):03d}"


def is_iso_date(text: str) -> bool:
    try:
        date.fromisoformat(text)
        return len(text) == 10
    except ValueError:
        return False


def gs1_check_digit_ok(digits: str) -> bool:
    """GS1 check digit (EAN-8, UPC-A, EAN-13, GTIN-14)."""
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def cas_check_digit_ok(cas: str) -> bool:
    match = CAS.match(cas)
    digits = (match.group(1) + match.group(2))[::-1]
    return sum((i + 1) * int(d) for i, d in enumerate(digits)) % 10 == int(match.group(3))


# The checks, tab by tab -----------------------------------------------------


def check_brands(report, rows):
    ids = check_ids(report, "Brands", rows, "brand_id", "B")
    names = Counter(value(r, "brand_name").lower() for _, r in rows if value(r, "brand_name"))
    for number, row in rows:
        check_spaces(report, "Brands", number, row)
        name = value(row, "brand_name")
        if not name:
            report.error("Brands", number, "brand_name is blank.")
        elif names[name.lower()] > 1:
            report.error("Brands", number, f"brand_name {name!r} appears more than once.")
    return ids, {value(r, "brand_name") for _, r in rows if value(r, "brand_name")}


def check_ingredients(report, rows):
    tab = "Ingredients"
    ids = check_ids(report, tab, rows, "ingredient_id", "I")
    canonical = {}
    by_lower = {}
    unii_seen = {}
    for number, row in rows:
        check_spaces(report, tab, number, row)
        ident, name = value(row, "ingredient_id"), value(row, "canonical_name")
        if not name:
            report.error(tab, number, "canonical_name is blank.")
        elif name.lower() in by_lower:
            report.error(tab, number, f"canonical_name {name!r} is already used by {by_lower[name.lower()]}.")
        else:
            canonical[name] = row
            by_lower[name.lower()] = ident

        kind = value(row, "type")
        if kind and kind not in INGREDIENT_TYPES:
            report.error(tab, number, f"type {kind!r} isn't one of the dropdown values.")
        elif not kind:
            report.check(tab, number, "type is blank.")

        synonyms = value(row, "synonyms")
        if ", " in synonyms:
            report.check(tab, number, "synonyms contain a comma: separate synonyms with ; (semicolons).")

        notes = value(row, "notes")
        cas = value(row, "cas_number")
        if cas not in NULL_WORDS:
            if not CAS.match(cas):
                report.error(tab, number, f"cas_number {cas!r} isn't in the 1234-56-7 format.")
            elif not cas_check_digit_ok(cas):
                report.error(tab, number, f"cas_number {cas} has the wrong check digit. Check it against PubChem.")
        unii = value(row, "unii")
        if unii not in NULL_WORDS:
            if not UNII.match(unii):
                report.error(tab, number, f"unii {unii!r} isn't 10 capital letters and digits.")
            elif unii in unii_seen:
                other = unii_seen[unii]
                report.check(tab, number, f"unii {unii} is also on {other}. If they're the same substance, they're a duplicate pair.")
            else:
                unii_seen[unii] = ident
        if (cas == "NULL" or unii == "NULL") and not notes:
            report.check(tab, number, "cas_number or unii is NULL with no reason in notes.")

    # A synonym that is another ingredient's canonical name makes lookups ambiguous.
    for number, row in rows:
        for synonym in [s.strip() for s in value(row, "synonyms").split(";") if s.strip()]:
            owner = by_lower.get(synonym.lower())
            if owner and owner != value(row, "ingredient_id"):
                report.check(tab, number, f"synonym {synonym!r} is the canonical name of {owner}.")
    return ids, canonical


def check_products(report, rows, brand_names, categories):
    tab = "Products"
    reserved = 0
    filled = []
    for number, row in rows:
        others = [v for k, v in row.items() if k != "product_id" and v.strip()]
        if value(row, "product_id") and not others:
            reserved += 1  # a pre-numbered empty row, not a product yet
        else:
            filled.append((number, row))
    ids = check_ids(report, tab, filled, "product_id", "P")

    barcodes = {}
    for number, row in filled:
        check_spaces(report, tab, number, row)
        for column in ("brand_name", "product_name"):
            if not value(row, column):
                report.error(tab, number, f"{column} is blank.")

        brand = value(row, "brand_name")
        if brand and brand_names is not None and brand not in brand_names:
            report.error(tab, number, f"brand_name {brand!r} isn't on the Brands tab.")
        category = value(row, "category")
        if category and categories is not None and category not in categories:
            report.error(tab, number, f"category {category!r} isn't on the Categories tab.")
        form = value(row, "form")
        if form and form not in FORMS:
            report.error(tab, number, f"form {form!r} isn't a valid form" + (" (it's a leftover header word in the dropdown)." if form in HEADER_LEFTOVERS else "."))

        for column, allowed in (("data_source", DATA_SOURCES), ("barcode_source", BARCODE_SOURCES), ("daily_dose_source", DAILY_DOSE_SOURCES), ("status", STATUSES)):
            text = value(row, column)
            if text and text not in allowed:
                extra = " (it's a leftover header word in the dropdown)" if text in HEADER_LEFTOVERS else ""
                report.error(tab, number, f"{column} {text!r} isn't one of {', '.join(sorted(allowed))}{extra}.")

        for column in ("date_added", "date_verified"):
            text = value(row, column)
            if text and not is_iso_date(text):
                report.error(tab, number, f"{column} {text!r} isn't a date in YYYY-MM-DD format.")

        url = value(row, "url_source")
        if url and not url.startswith(("https://", "http://")):
            report.check(tab, number, f"url_source {url!r} doesn't start with https://.")
        price = value(row, "price_gbp")
        if price and not PRICE.match(price):
            report.check(tab, number, f"price_gbp {price!r} isn't in the £1.23 format.")

        per_day, per_day_source = value(row, "units_per_day"), value(row, "daily_dose_source")
        if per_day and not re.match(r"^[1-9]\d*$", per_day):
            report.error(tab, number, f"units_per_day {per_day!r} isn't a whole number.")
        if bool(per_day) != bool(per_day_source):
            report.check(tab, number, "units_per_day and daily_dose_source should be filled in together.")

        barcode = value(row, "barcode_ean")
        if barcode and barcode != "TBC":
            if re.match(r"^\d+(\.\d+)?[eE]\+\d+$", barcode):
                report.error(tab, number, f"barcode_ean {barcode!r} was turned into a number. Retype it as plain text.")
            elif not barcode.isdigit():
                report.error(tab, number, f"barcode_ean {barcode!r} should contain digits only.")
            elif len(barcode) not in (8, 12, 13, 14):
                hint = " A leading zero may have been dropped." if len(barcode) in (7, 11) else ""
                report.error(tab, number, f"barcode_ean {barcode} has {len(barcode)} digits; barcodes have 8, 12, 13 or 14.{hint}")
            elif not gs1_check_digit_ok(barcode):
                report.error(tab, number, f"barcode_ean {barcode} has the wrong check digit. Check it against the pack.")
            if barcode in barcodes:
                report.check(tab, number, f"barcode_ean {barcode} is also on row {barcodes[barcode]}.")
            else:
                barcodes[barcode] = number
    return ids, {value(r, "product_id"): r for _, r in filled}, reserved


def nrv_for(ingredient_row: dict) -> tuple[float, str, str] | None:
    """The NRV for an ingredient, found by exact name match on its canonical
    name or synonyms. None if nothing matches, or if names point to two
    different nutrients."""
    names = [value(ingredient_row, "canonical_name")] + value(ingredient_row, "synonyms").split(";")
    keys = {NRV_NAMES[normalise(n)] for n in names if normalise(n) in NRV_NAMES}
    if len(keys) != 1:
        return None
    key = keys.pop()
    amount, unit = NRV[key]
    return amount, unit, key


def check_product_ingredients(report, rows, product_ids, products, canonical):
    tab = "Product_Ingredients"
    synonym_owner = {}
    lower_canonical = {}
    for name, row in canonical.items():
        lower_canonical[name.lower()] = name
        for synonym in value(row, "synonyms").split(";"):
            if synonym.strip():
                synonym_owner.setdefault(synonym.strip().lower(), name)

    micro_counts = Counter(value(r, "unit")[0] for _, r in rows if value(r, "unit") in (MICRO_SIGN + "g", GREEK_MU + "g"))
    usual_micro = micro_counts.most_common(1)[0][0] if micro_counts else MICRO_SIGN

    seen_rows = {}
    serving_products = {}
    with_rows = set()
    for number, row in rows:
        check_spaces(report, tab, number, row)
        product_id, name = value(row, "product_id"), value(row, "ingredient_name")
        amount, unit, per = value(row, "amount"), value(row, "unit"), value(row, "per")
        pct, notes = value(row, "pct_nrv"), value(row, "notes")

        if not product_id:
            report.error(tab, number, "product_id is blank.")
        elif product_id not in product_ids:
            report.error(tab, number, f"product_id {product_id} isn't on the Products tab.")
        else:
            with_rows.add(product_id)

        ingredient = canonical.get(name)
        if not name:
            report.error(tab, number, "ingredient_name is blank.")
        elif ingredient is None:
            if name.lower() in lower_canonical:
                report.error(tab, number, f"ingredient_name {name!r} differs only in capitals from the dictionary's {lower_canonical[name.lower()]!r}.")
            elif name.lower() in synonym_owner:
                report.error(tab, number, f"ingredient_name {name!r} is a synonym. Use the canonical name {synonym_owner[name.lower()]!r}.")
            else:
                report.error(tab, number, f"ingredient_name {name!r} isn't a canonical_name on the Ingredients tab.")

        # Amount, unit and per go together.
        if amount:
            if not PLAIN_NUMBER.match(amount):
                report.error(tab, number, f"amount {amount!r} should be a plain number, with no commas, units or symbols.")
            if not unit:
                report.error(tab, number, f"amount {amount} has no unit.")
            if not per:
                report.error(tab, number, f"amount {amount} has no per value.")
        elif unit or pct:
            report.error(tab, number, "unit or pct_nrv is filled in but amount is blank.")
        elif not notes:
            report.error(tab, number, "amount is blank with no reason in notes.")

        if unit:
            if unit in ("mcg", "ug", "mcgs"):
                report.error(tab, number, f"unit {unit!r} should be µg.")
            elif unit not in UNITS:
                report.error(tab, number, f"unit {unit!r} isn't one of the dropdown values.")
            elif unit in (MICRO_SIGN + "g", GREEK_MU + "g") and unit[0] != usual_micro:
                kind = "Greek letter mu" if unit[0] == GREEK_MU else "micro sign"
                report.error(tab, number, f"unit uses the {kind}, which looks like the µ in other rows but doesn't match it. Pick µg from the dropdown.")
            elif unit == "other" and not notes:
                report.check(tab, number, "unit is 'other' with nothing in notes to say what it is.")

        if per:
            if per in HEADER_LEFTOVERS:
                report.error(tab, number, "per is 'per', a leftover header word in the dropdown.")
            elif per not in PER_VALUES:
                report.error(tab, number, f"per {per!r} isn't valid. Use 'per serving' and say what a serving is on the Products row.")
            elif per == "per serving" and product_id:
                serving_products.setdefault(product_id, number)

        # % NRV: never invented, and consistent with the amount where we can tell.
        if pct:
            kind = value(ingredient, "type") if ingredient else ""
            if not PCT_NRV.match(pct):
                report.check(tab, number, f"pct_nrv {pct!r} isn't in the usual 100% form.")
            elif kind in NO_NRV_TYPES:
                report.error(tab, number, f"pct_nrv {pct} is filled in, but {name!r} is a {kind}, which has no NRV.")
            elif ingredient and amount and PLAIN_NUMBER.match(amount) and unit in TO_MICROGRAMS:
                nrv = nrv_for(ingredient)
                stated = float(pct.lstrip("<>").rstrip("%"))
                if nrv and not pct.startswith(("<", ">")):
                    nrv_amount, nrv_unit, nutrient = nrv
                    expected = float(amount) * TO_MICROGRAMS[unit] / (nrv_amount * TO_MICROGRAMS[nrv_unit]) * 100
                    if abs(expected - stated) > max(1.0, expected * 0.05):
                        report.check(
                            tab,
                            number,
                            f"pct_nrv {pct} doesn't match {amount} {unit} against the {nutrient} NRV of "
                            f"{nrv_amount:g} {nrv_unit} ({expected:.0f}%). Check the label; if it prints {pct}, keep it.",
                        )

        key = (product_id, name, amount, unit, per, notes)
        if product_id and name and key in seen_rows:
            report.check(tab, number, f"same ingredient, dose and notes as row {seen_rows[key]}. Is it a duplicate?")
        else:
            seen_rows[key] = number

    for product_id, number in serving_products.items():
        product = products.get(product_id, {})
        if "serving" not in value(product, "notes").lower() and not value(product, "units_per_day"):
            report.check(tab, number, f"{product_id} uses 'per serving', but its Products row doesn't say what a serving is (in notes or units_per_day).")

    for product_id, product in products.items():
        if product_id in with_rows and value(product, "data_source") == "TBC":
            report.check("Products", product_ids.get(product_id), f"{product_id} has ingredient rows but data_source is TBC, so the export would publish it.")
    return with_rows


def check_warnings(report, rows, product_ids):
    tab = "Product_Warnings"
    ids = check_ids(report, tab, rows, "warning_id", "W")
    for number, row in rows:
        check_spaces(report, tab, number, row)
        product_id, kind, text = value(row, "product_id"), value(row, "warning_type"), value(row, "warning_text")
        if product_id not in product_ids:
            report.error(tab, number, f"product_id {product_id!r} isn't on the Products tab.")
        if kind not in WARNING_TYPES:
            report.error(tab, number, f"warning_type {kind!r} isn't one of the dropdown values.")
        if not text:
            report.error(tab, number, "warning_text is blank.")
        elif STATUTORY_LINE.search(text):
            report.check(tab, number, "this is the statutory 'not a substitute for a varied diet' line, which isn't captured as a warning.")
    return ids


def check_claims(report, rows, product_ids, canonical, ingredient_rows):
    tab = "Product_Claims"
    ids = check_ids(report, tab, rows, "claim_id", "C")
    by_product = defaultdict(set)
    for _, row in ingredient_rows:
        by_product[value(row, "product_id")].add(value(row, "ingredient_name"))
    for number, row in rows:
        check_spaces(report, tab, number, row)
        product_id, ingredient = value(row, "product_id"), value(row, "ingredient")
        if product_id not in product_ids:
            report.error(tab, number, f"product_id {product_id!r} isn't on the Products tab.")
        if not value(row, "claim_text"):
            report.error(tab, number, "claim_text is blank.")
        if not value(row, "source"):
            report.check(tab, number, "source is blank.")
        if ingredient and ingredient not in canonical:
            report.check(tab, number, f"ingredient {ingredient!r} isn't a canonical_name on the Ingredients tab.")
        elif ingredient and product_id in product_ids and ingredient not in by_product[product_id]:
            report.check(tab, number, f"{product_id} has no Product_Ingredients row for {ingredient!r}.")
    return ids


# Running it -------------------------------------------------------------------


def run_checks(data: dict) -> tuple[Report, dict]:
    report = Report()
    brand_ids, brand_names = check_brands(report, data["Brands"]) if "Brands" in data else ({}, None)
    categories = {value(r, "category") for _, r in data["Categories"] if value(r, "category")} if "Categories" in data else None
    ingredient_ids, canonical = check_ingredients(report, data["Ingredients"])
    product_ids, products, reserved = check_products(report, data["Products"], brand_names, categories)
    with_rows = check_product_ingredients(report, data["Product_Ingredients"], product_ids, products, canonical)
    warning_ids = check_warnings(report, data["Product_Warnings"], product_ids) if "Product_Warnings" in data else {}
    claim_ids = check_claims(report, data["Product_Claims"], product_ids, canonical, data["Product_Ingredients"]) if "Product_Claims" in data else {}

    used = {value(r, "ingredient_name") for _, r in data["Product_Ingredients"]}
    summary = {
        "products": len(products),
        "detailed": len(with_rows),
        "reserved": reserved,
        "ingredients": len(canonical),
        "unused_ingredients": len([n for n in canonical if n not in used]),
        "ingredient_rows": len(data["Product_Ingredients"]),
        "warnings": len(data.get("Product_Warnings", [])),
        "claims": len(data.get("Product_Claims", [])),
        "next_ids": [
            next_id(product_ids, "P"),
            next_id(ingredient_ids, "I"),
            next_id(warning_ids, "W"),
            next_id(claim_ids, "C"),
            next_id(brand_ids, "B"),
        ],
    }
    return report, summary


def plural(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def format_report(report: Report, summary: dict, missing: list[str]) -> str:
    lines = [f"Lagomy data check: {plural(len(report.errors), 'error')}, {plural(len(report.checks), 'check')}", ""]
    for tab in missing:
        lines.append(f"Not found: {tab}.csv, so its checks were skipped.")
    if missing:
        lines.append("")

    by_tab = defaultdict(list)
    for finding in report.findings:
        by_tab[finding.tab].append(finding)
    for tab in TABS:
        if not by_tab[tab]:
            continue
        lines.append(tab)
        for finding in sorted(by_tab[tab], key=lambda f: (f.level != "error", f.row or 0)):
            where = f"row {finding.row}" if finding.row else "tab"
            lines.append(f"  {where:<9} {finding.level:<6} {finding.message}")
        lines.append("")

    lines += [
        "Summary",
        f"  Products: {summary['products']} ({summary['detailed']} with ingredient rows)"
        + (f", plus {plural(summary['reserved'], 'empty numbered row')}" if summary["reserved"] else ""),
        f"  Ingredients: {summary['ingredients']} ({summary['unused_ingredients']} not used by any product)",
        f"  Ingredient rows: {summary['ingredient_rows']}",
        f"  Warnings: {summary['warnings']}",
        f"  Claims: {summary['claims']}",
        f"  Next free IDs: {', '.join(summary['next_ids'])}",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check the Lagomy master sheet's CSV exports against the dataset's rules.")
    parser.add_argument("folder", type=Path, help="Folder holding one CSV per tab.")
    args = parser.parse_args(argv)

    if not args.folder.is_dir():
        print(f"{args.folder} isn't a folder.", file=sys.stderr)
        return 2
    data, missing = load(args.folder)
    absent_required = [tab for tab in REQUIRED_TABS if tab not in data]
    if absent_required:
        print(f"Can't run without these tabs: {', '.join(absent_required)}. See the top of check_data.py for how to download them.", file=sys.stderr)
        return 2

    report, summary = run_checks(data)
    print(format_report(report, summary, missing))
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
