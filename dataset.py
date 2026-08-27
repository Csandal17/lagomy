"""Lagomy UK Supplements dataset, fetched from Hugging Face.

The dataset is CC BY-NC 4.0 and lives at
https://huggingface.co/datasets/Csandal17/lagomy-uk-supplements
It is deliberately not committed to this repository.
"""
import pandas as pd
from huggingface_hub import hf_hub_download

REPO_ID = "Csandal17/lagomy-uk-supplements"


def _load(filename: str) -> pd.DataFrame:
    path = hf_hub_download(
        repo_id=REPO_ID,
        filename=filename,
        repo_type="dataset",
    )
    return pd.read_csv(path, dtype=str)


products = _load("products.csv")
product_ingredients = _load("product_ingredients.csv")
ingredients = _load("ingredients.csv")

print(
    f"Dataset loaded: {len(products)} products, "
    f"{len(ingredients)} ingredients, "
    f"{len(product_ingredients)} ingredient rows"
)

def find_products(query: str) -> list[dict]:
    """Products whose name or brand contains the query, case-insensitive."""
    q = query.lower()
    matches = products[
        products["product_name"].str.lower().str.contains(q, na=False)
        | products["brand_name"].str.lower().str.contains(q, na=False)
    ]
    return matches.to_dict("records")


def nutrient_name(ingredient_id: str) -> str | None:
    """The everyday nutrient name for an ingredient, from its synonyms."""
    row = ingredients[ingredients["ingredient_id"] == ingredient_id]
    if row.empty:
        return None
    synonyms = row.iloc[0]["synonyms"]
    if pd.isna(synonyms) or not synonyms:
        return row.iloc[0]["canonical_name"]
    return synonyms.split(";")[0].strip()


def product_ingredient_rows(product_id: str) -> list[dict]:
    """Every ingredient row for a product, with its nutrient name attached."""
    rows = product_ingredients[
        product_ingredients["product_id"] == product_id
    ].to_dict("records")
    for row in rows:
        row["nutrient_name"] = nutrient_name(row["ingredient_id"])
    return rows

