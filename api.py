import json
import re
from datetime import date
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from lagomy.crew import Lagomy
from guardrails import find_banned_phrases

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

app = FastAPI(
    title="Lagomy Evidence API",
    description="Sourced UK supplement evidence. Records, never advises.",
    version="0.1.0",
)  

@app.get("/health")
def health():
    return {"status": "ok"}

def extract_json(text: str) -> dict:
    """Pull the JSON object out of the crew's prose + JSON output."""
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        match = re.search(r"(\{.*\})", text, re.DOTALL)
    if not match:
        raise HTTPException(status_code=502, detail="Crew returned no JSON block")
    return json.loads(match.group(1))


@app.post("/evidence", response_model=EvidenceResponse)
def evidence(request: EvidenceRequest):
    """Run the crew for one ingredient and return sourced evidence."""
    result = Lagomy().crew().kickoff(inputs={
        "ingredient": request.ingredient,
        "probe": request.probe,
    })
    text = str(result)
    data = extract_json(text)

    today = date.today()
    for field in ["role", "food_sources", "reference_intake",
                  "upper_limit", "regulatory_flags"]:
        for statement in data.get(field, []):
            statement["retrieval_date"] = today

    prose = text.split("```json")[0].strip()

    hits = find_banned_phrases(prose)
    if hits:
        print(f"GUARDRAIL: prose withheld, matched {hits}")
        prose = None

    return EvidenceResponse(
        ingredient=request.ingredient,
        evidence=IngredientEvidence(**data),
        prose=prose,
        guardrail_triggered=bool(hits),
    )
