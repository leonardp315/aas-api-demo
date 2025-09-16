from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import JSONResponse, StreamingResponse
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import json
import io
import qrcode

app = FastAPI(title="AAS Minimal API + DPP", version="0.2.0")

# Caminho do arquivo AAS (POC: um único produto id=1)
AAS_FILE = Path(__file__).resolve().parent.parent / "aas" / "artifacts" / "aas_1.json"

# URL pública base da API (ajuste para seu domínio onrender)
# Ex.: PUBLIC_BASE = "https://aas-api-demo.onrender.com"
PUBLIC_BASE = "https://aas-api-demo.onrender.com/"


# -------------------------
# Utils para ler/gravar AAS
# -------------------------
def load_aas() -> dict:
    if not AAS_FILE.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {AAS_FILE}")
    with open(AAS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_aas(data: dict) -> None:
    AAS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AAS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# -------------------------
# Modelos Pydantic (DPP)
# -------------------------
class DPP(BaseModel):
    productId: str = Field(..., description="Identificador do produto")
    nameplate: Dict[str, str]
    technicalData: Dict[str, Optional[str]]
    evidences: List[str] = []


def build_dpp_from_aas(aas: dict) -> DPP:
    nameplate = aas.get("submodels", {}).get("nameplate", {}) or {}
    technical = aas.get("submodels", {}).get("technicalData", {}) or {}
    return DPP(
        productId=str(aas.get("id", "1")),
        nameplate=nameplate,
        technicalData=technical,
        evidences=[],  # Adicione links/nomes de PDFs quando quiser
    )


# -------------------------
# Endpoints básicos
# -------------------------
@app.get("/")
def root():
    return {
        "status": "running",
        "endpoints": [
            "/aas/1",
            "/aas/1/submodel/nameplate (PUT)",
            "/aas/1/submodel/technicalData (PUT)",
            "/dpp/1",
            "/qrcode",
            "/qrcode/docs",
            "/docs",
        ],
    }

@app.get("/aas/{id}")
def get_aas(id: str):
    # POC: apenas id=1
    if id != "1":
        raise HTTPException(status_code=404, detail="AAS não encontrado para este id (use 1 no POC).")
    try:
        data = load_aas()
        return JSONResponse(content=data)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo AAS não encontrado.")

@app.put("/aas/{id}/submodel/{name}")
def update_submodel(id: str, name: str, body: dict = Body(...)):
    if id != "1":
        raise HTTPException(status_code=404, detail="AAS não encontrado para este id (use 1 no POC).")
    try:
        data = load_aas()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo AAS não encontrado.")

    # Garante estrutura
    data.setdefault("submodels", {})
    # Atualiza/insere o submodelo
    data["submodels"][name] = body

    save_aas(data)
    return {"status": "ok", "updatedSubmodel": name}


# -------------------------
# DPP (montado em tempo real)
# -------------------------
@app.get("/dpp/{id}", response_model=DPP)
def get_dpp(id: str):
    if id != "1":
        raise HTTPException(status_code=404, detail="DPP não disponível para este id (use 1 no POC).")
    try:
        aas = load_aas()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo AAS não encontrado.")
    dpp = build_dpp_from_aas(aas)
    return dpp


# -------------------------
# QRCodes
# -------------------------
@app.get("/qrcode")
def get_qrcode():
    """
    Gera um QR que aponta para o DPP do produto 1 (GET /dpp/1).
    """
    dpp_url = f"{PUBLIC_BASE}/dpp/1"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(dpp_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

@app.get("/qrcode/docs")
def get_qrcode_docs():
    """
    Gera um QR para a página Swagger (/docs).
    """
    docs_url = f"{PUBLIC_BASE}/docs"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(docs_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")
