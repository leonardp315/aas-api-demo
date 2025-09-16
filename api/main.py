from fastapi import FastAPI, HTTPException, Body  # FastAPI básico [251]
from fastapi.responses import JSONResponse, StreamingResponse  # respostas JSON e imagem [251]
from pathlib import Path  # manipular caminhos de arquivos [251]
from pydantic import BaseModel, Field  # modelos e validação [292]
from typing import Any  # adicione
import json  # ler/gravar JSON [251]
import io  # buffer de bytes para PNG [251]
import qrcode  # gerar QR code [251]

app = FastAPI(title="AAS Minimal API + DPP", version="0.2.0")  # app FastAPI [251]

# Caminho do arquivo AAS (POC: único produto id=1) [251]
AAS_FILE = Path(__file__).resolve().parent.parent / "aas" / "artifacts" / "aas_1.json"  # [251]

# URL pública base da API (ajuste para seu domínio onrender) [251]
# Ex.: PUBLIC_BASE = "https://aas-api-demo.onrender.com" [251]
PUBLIC_BASE = "https://dashboard.render.com/"  # troque pela sua URL pública do Render [251]


# -------------------------
# Utilitários AAS [251]
# -------------------------
def load_aas() -> dict:
    if not AAS_FILE.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {AAS_FILE}")  # [251]
    with open(AAS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)  # [251]

def save_aas(data: dict) -> None:
    AAS_FILE.parent.mkdir(parents=True, exist_ok=True)  # [251]
    with open(AAS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)  # [251]


# -------------------------
# Modelos (DPP) [292]
# -------------------------
class DPP(BaseModel):
    productId: str
    nameplate: dict[str, Any]          # antes: Dict[str, str]
    technicalData: dict[str, Any]      # antes: Dict[str, Optional[str]]
    evidences: list[str] = []

def build_dpp_from_aas(aas: dict) -> DPP:
    nameplate = aas.get("submodels", {}).get("nameplate", {}) or {}  # [251]
    technical = aas.get("submodels", {}).get("technicalData", {}) or {}  # [251]
    return DPP(
        productId=str(aas.get("id", "1")),  # [292]
        nameplate=nameplate,  # [292]
        technicalData=technical,  # [292]
        evidences=[],  # preencher futuramente com links/arquivos [292]
    )  # [292]


# -------------------------
# Endpoints básicos [251]
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
    }  # [251]

@app.get("/aas/{id}")
def get_aas(id: str):
    if id != "1":
        raise HTTPException(status_code=404, detail="AAS não encontrado para este id (use 1 no POC).")  # [251]
    try:
        data = load_aas()  # [251]
        return JSONResponse(content=data)  # [251]
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo AAS não encontrado.")  # [251]

@app.put("/aas/{id}/submodel/{name}")
def update_submodel(id: str, name: str, body: dict = Body(...)):
    if id != "1":
        raise HTTPException(status_code=404, detail="AAS não encontrado para este id (use 1 no POC).")  # [251]
    try:
        data = load_aas()  # [251]
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo AAS não encontrado.")  # [251]

    data.setdefault("submodels", {})  # [251]
    data["submodels"][name] = body  # [251]
    save_aas(data)  # [251]
    return {"status": "ok", "updatedSubmodel": name}  # [251]


# -------------------------
# DPP em tempo real [251][292]
# -------------------------
@app.get("/dpp/{id}", response_model=DPP)
def get_dpp(id: str):
    if id != "1":
        raise HTTPException(status_code=404, detail="DPP não disponível para este id (use 1 no POC).")  # [251]
    try:
        aas = load_aas()  # [251]
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo AAS não encontrado.")  # [251]
    dpp = build_dpp_from_aas(aas)  # [292]
    return dpp  # [251][292]


# -------------------------
# QRCodes [251]
# -------------------------
@app.get("/qrcode")
def get_qrcode():
    """
    Gera um QR que aponta para o DPP do produto 1 (GET /dpp/1).  # [251]
    """
    dpp_url = f"{PUBLIC_BASE}/dpp/1"  # [251]
    qr = qrcode.QRCode(version=1, box_size=10, border=2)  # [251]
    qr.add_data(dpp_url)  # [251]
    qr.make(fit=True)  # [251]
    img = qr.make_image(fill_color="black", back_color="white")  # [251]

    buf = io.BytesIO()  # [251]
    img.save(buf, format="PNG")  # [251]
    buf.seek(0)  # [251]
    return StreamingResponse(buf, media_type="image/png")  # [251]

@app.get("/qrcode/docs")
def get_qrcode_docs():
    """
    Gera um QR para a página Swagger (/docs).  # [251]
    """
    docs_url = f"{PUBLIC_BASE}/docs"  # [251]
    qr = qrcode.QRCode(version=1, box_size=10, border=2)  # [251]
    qr.add_data(docs_url)  # [251]
    qr.make(fit=True)  # [251]
    img = qr.make_image(fill_color="black", back_color="white")  # [251]

    buf = io.BytesIO()  # [251]
    img.save(buf, format="PNG")  # [251]
    buf.seek(0)  # [251]
    return StreamingResponse(buf, media_type="image/png")  # [251]
