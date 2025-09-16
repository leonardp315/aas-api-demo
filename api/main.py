from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import JSONResponse
from pathlib import Path
import json

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
