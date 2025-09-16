from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import JSONResponse
from pathlib import Path
import json

from pydantic import BaseModel, Field
from typing import Optional, Dict, List

class DPP(BaseModel):
    productId: str = Field(..., description="Identificador do produto")
    nameplate: Dict[str, str]
    technicalData: Dict[str, Optional[str]]
    evidences: List[str] = []

app = FastAPI(title="AAS Minimal API", version="0.1.0")

# Caminho para o arquivo AAS (produto id=1)
AAS_FILE = Path(__file__).resolve().parent.parent / "aas" / "artifacts" / "aas_1.json"

def load_aas():
    if not AAS_FILE.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {AAS_FILE}")
    with open(AAS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_aas(data: dict):
    AAS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AAS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
def build_dpp_from_aas(aas: dict) -> DPP:
    nameplate = aas.get("submodels", {}).get("nameplate", {}) or {}
    technical = aas.get("submodels", {}).get("technicalData", {}) or {}
    return DPP(
        productId=str(aas.get("id", "1")),
        nameplate=nameplate,
        technicalData=technical,
        evidences=[],  # pode preencher com links de PDFs quando quiser
    )

@app.get("/aas/{id}")
def get_aas(id: str):
    # Para POC, usamos sempre o arquivo do id=1
    if id != "1":
        raise HTTPException(status_code=404, detail="AAS não encontrado para este id (use 1 no POC).")
    try:
        data = load_aas()
        return JSONResponse(content=data)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo AAS não encontrado.")

@app.put("/aas/{id}/submodel/{name}")
def update_submodel(id: str, name: str, body: dict = Body(...)):
    # POC simples: permite atualizar submodelo por nome
    if id != "1":
        raise HTTPException(status_code=404, detail="AAS não encontrado para este id (use 1 no POC).")
    try:
        data = load_aas()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo AAS não encontrado.")

    # Garante estrutura de submodels
    data.setdefault("submodels", {})

    # Atualiza submodelo
    data["submodels"][name] = body

    # Salva arquivo
    save_aas(data)
    return {"status": "ok", "updatedSubmodel": name}

# Rota simples para ver status
@app.get("/")
def root():
    return {"status": "running", "endpoints": ["/aas/1", "/aas/1/submodel/nameplate (PUT)"]}

@app.get("/dpp/{id}")
def get_dpp(id: str):
    if id != "1":
        raise HTTPException(status_code=404, detail="DPP não disponível para este id (use 1 no POC).")
    try:
        aas = load_aas()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo AAS não encontrado.")
    dpp = build_dpp_from_aas(aas)
    return JSONResponse(content=dpp.model_dump())

