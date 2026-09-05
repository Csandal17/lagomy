import json
from datetime import date
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path

from guardrails import find_banned_phrases
import dataset

load_dotenv()

class EvidenceRequest(BaseModel):
    """What a caller sends us."""
    ingredient: str
    probe: str = "What do published UK sources say about this ingredient?"


class EvidenceStatement(BaseModel):
    """One sourced claim. The provenance unit of the whole API."""
    text: str
    source_url: str
    source_authority: str   # e.g. "NHS", "NICE", "BNF"
    retrieval_date: date


class IngredientEvidence(BaseModel):
    """The structured record for one ingredient, field by field."""
    canonical_name: str
    role: list[EvidenceStatement] = []
    food_sources: list[EvidenceStatement] = []
    reference_intake: list[EvidenceStatement] = []
    upper_limit: list[EvidenceStatement] = []
    regulatory_flags: list[EvidenceStatement] = []


class EvidenceResponse(BaseModel):
    """What we return. prose is None when the guardrail gate strips it."""
    ingredient: str
    evidence: IngredientEvidence
    prose: str | None = None
    guardrail_triggered: bool = False

class ProductIngredientEvidence(BaseModel):
    """One ingredient in a product, with evidence if we have any."""
    ingredient_id: str
    canonical_name: str
    matched_key: str | None = None
    match_type: str          # exact | alias | modifier | none
    evidence: IngredientEvidence | None = None

class ProductResponse(BaseModel):
    """Every ingredient in a product, with per-ingredient provenance."""
    product_id: str
    ingredients: list[ProductIngredientEvidence]
    matched_count: int
    unmatched_count: int

app = FastAPI(
    title="Lagomy Evidence API",
    description="Sourced UK supplement evidence. Records, never advises.",
    version="0.1.0",
)  

@app.get("/health")
def health():
    return {"status": "ok"}


STORE = Path("evidence_store.json")

try:
    STORE_DATA: dict = json.loads(STORE.read_text())
except FileNotFoundError:
    STORE_DATA = {}

STORE_KEYS = list(STORE_DATA)

def lookup_store(ingredient: str) -> dict | None:
    """Return a precomputed entry if we have one."""
    return STORE_DATA.get(ingredient)

@app.post(
    "/evidence",
    response_model=EvidenceResponse,
    responses={404: {"description": "No precomputed evidence for this ingredient."}},
)
def evidence(request: EvidenceRequest):
    """Return stored evidence if we have it, otherwise run the crew."""
    default_probe = EvidenceRequest.model_fields["probe"].default
    if request.probe == default_probe:
        stored = lookup_store(request.ingredient)
        if stored:
            print(f"STORE HIT: {request.ingredient} — no crew run")
            stored_prose = stored["prose"]
            hits = find_banned_phrases(stored_prose)
            if hits:
                stored_prose = None
            return EvidenceResponse(
                ingredient=request.ingredient,
                evidence=IngredientEvidence(**stored["evidence"]),
                prose=stored_prose,
                guardrail_triggered=bool(hits),
            )

    raise HTTPException(
        status_code=404,
        detail=(
            f"No precomputed evidence for '{request.ingredient}'. "
            "This API serves evidence generated in advance; "
            "it does not run live searches."
        ),
    )

@app.get(
    "/product/{product_id}",
    response_model=ProductResponse,
    responses={404: {"description": "No product found with this id."}},
)
def product(product_id: str):
    """Every ingredient in a product, with stored evidence where we have it."""
    rows = dataset.product_ingredient_rows(product_id)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No product found with id '{product_id}'.",
        )

    results = []
    for row in rows:
        ingredient_id = row["ingredient_id"]
        key, how = dataset.match_store_key(ingredient_id, STORE_KEYS)
        stored = lookup_store(key) if key else None
        results.append(
            ProductIngredientEvidence(
                ingredient_id=ingredient_id,
                canonical_name=dataset.canonical_name(ingredient_id),
                matched_key=key,
                match_type=how,
                evidence=IngredientEvidence(**stored["evidence"]) if stored else None,
            )
        )

    matched = sum(1 for r in results if r.evidence is not None)
    return ProductResponse(
        product_id=product_id,
        ingredients=results,
        matched_count=matched,
        unmatched_count=len(results) - matched,
    )
