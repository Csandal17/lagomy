from datetime import date, datetime
from pydantic import BaseModel
from fastapi import FastAPI

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

app = FastAPI(
    title="Lagomy Evidence API",
    description="Sourced UK supplement evidence. Records, never advises.",
    version="0.1.0",
)  

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/evidence", response_model=EvidenceResponse)
def evidence(request: EvidenceRequest):
    """Placeholder: returns a hand-built response so the schema can be seen."""
    return EvidenceResponse(
        ingredient=request.ingredient,
        evidence=IngredientEvidence(
            canonical_name=request.ingredient,
            reference_intake=[
                EvidenceStatement(
                    text="Adults aged 19 to 64 need about 1.5 micrograms a day of vitamin B12.",
                    source_url="https://www.nhs.uk/conditions/vitamins-and-minerals/vitamin-b",
                    source_authority="NHS",
                    retrieval_date=date.today(),
                )
            ],
        ),
        prose="Placeholder prose. The crew is not wired in yet.",
    )
