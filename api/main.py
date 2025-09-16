from fastapi import FastAPI, HTTPException, Body, Request  # FastAPI e Request para templates [3]
from fastapi.responses import JSONResponse, StreamingResponse  # JSON e imagem 
from fastapi.staticfiles import StaticFiles  # servir /static [2]
from fastapi.templating import Jinja2Templates  # renderizar templates Jinja2 [3]
from pathlib import Path  # caminho de arquivos [2]
from pydantic import BaseModel, Field  # modelos/validação [4]
from typing import Any, Dict, List, Optional  # tipos auxiliares [4]
import json  # ler/gravar JSON 
import io   # buffer PNG 
import qrcode  # gerar QR code 

app = FastAPI(title="AAS + DPP + View", version="0.3.0")  # app FastAPI 

# Caminhos de pastas relativas a este arquivo
HERE = Path(__file__).resolve().parent  # api/ [2]
AAS_FILE = HERE.parent / "aas" / "artifacts" / "aas_1.json"  # aas/artifacts/aas_1.json 

# URL pública base da sua API (troque para a URL onrender do seu serviço)
PUBLIC_BASE = "https://dashboard.render.com/"  # ex.: https://aas-api-demo.onrender.com 

# Montar arquivos estáticos e templates
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")  # serve api/static em /static [2]
templates = Jinja2Templates(directory=str(HERE / "templates"))  # templates Jinja em api/templates [3]

# =========================
# Utilitários do AAS
# =========================
def load_aas() -> dict:
    if not AAS_FILE.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {AAS_FILE}")  # 
    with open(AAS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)  # 

def save_aas(data: dict) -> None:
    AAS_FILE.parent.mkdir(parents=True, exist_ok=True)  # 
    with open(AAS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)  # 

# =========================
# Modelo do DPP
# =========================
class DPP(BaseModel):
    productId: str = Field(..., description="Identificador do produto")  # [4]
    # Flexível para não quebrar com valores não-string do AAS (POC)
    nameplate: Dict[str, Any]  # antes poderia ser Dict[str, str] [4]
    technicalData: Dict[str, Any]  # antes poderia ser Dict[str, Optional[str]] [4]
    evidences: List[str] = []  # [4]

def build_dpp_from_aas(aas: dict) -> DPP:
    nameplate = aas.get("submodels", {}).get("nameplate", {}) or {}  # 
    technical = aas.get("submodels", {}).get("technicalData", {}) or {}  # 
    return DPP(
        productId=str(aas.get("id", "1")),  # [4]
        nameplate=nameplate,
        technicalData=technical,
        evidences=[],
    )  # [4]

# =========================
# Endpoints principais
# =========================
@app.get("/")
def root():
    return {
        "status": "running",
        "endpoints": [
            "/aas/1",
            "/aas/1/submodel/nameplate (PUT)",
            "/aas/1/submodel/technicalData (PUT)",
            "/dpp/1",
            "/view/dpp/1",
            "/qrcode",
            "/qrcode/docs",
            "/docs",
        ],
    }  # 

@app.get("/aas/{id}")
def get_aas(id: str):
    if id != "1":
        raise HTTPException(status_code=404, detail="AAS não encontrado para este id (use 1 no POC).")  # 
    try:
        data = load_aas()  # 
        return JSONResponse(content=data)  # 
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo AAS não encontrado.")  # 

@app.put("/aas/{id}/submodel/{name}")
def update_submodel(id: str, name: str, body: dict = Body(...)):
    if id != "1":
        raise HTTPException(status_code=404, detail="AAS não encontrado para este id (use 1 no POC).")  # 
    try:
        data = load_aas()  # 
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo AAS não encontrado.")  # 
    data.setdefault("submodels", {})  # 
    data["submodels"][name] = body  # 
    save_aas(data)  # 
    return {"status": "ok", "updatedSubmodel": name}  # 

# =========================
# DPP em tempo real (JSON)
# =========================
@app.get("/dpp/{id}", response_model=DPP)
def get_dpp(id: str):
    if id != "1":
        raise HTTPException(status_code=404, detail="DPP não disponível para este id (use 1 no POC).")  # 
    try:
        aas = load_aas()  # 
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo AAS não encontrado.")  # 
    dpp = build_dpp_from_aas(aas)  # [4]
    return dpp  # 

# =========================
# Página HTML para visualizar o DPP
# =========================
@app.get("/view/dpp/{id}")
def view_dpp(id: str, request: Request):
    if id != "1":
        raise HTTPException(status_code=404, detail="DPP não disponível para este id (use 1 no POC).")  # [3]
    try:
        aas = load_aas()  # 
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Arquivo AAS não encontrado.")  # 
    dpp = build_dpp_from_aas(aas)  # [4]

    # Preparar exibição “bonita”
    nameplate_pretty = json.dumps(dpp.nameplate, ensure_ascii=False, indent=2)  # [3]
    technical_pretty = json.dumps(dpp.technicalData, ensure_ascii=False, indent=2)  # [3]
    dpp_url = f"{PUBLIC_BASE}/dpp/{id}"  # 
    qrcode_url = f"{PUBLIC_BASE}/qrcode"  # 

    return templates.TemplateResponse(
        "view.html",
        {
            "request": request,
            "dpp": dpp.model_dump(),
            "nameplate_pretty": nameplate_pretty,
            "technical_pretty": technical_pretty,
            "dpp_url": dpp_url,
            "qrcode_url": qrcode_url,
        },
    )  # [3]

# =========================
# QRCodes
# =========================
@app.get("/qrcode")
def get_qrcode():
    """QR que aponta para /dpp/1"""  # 
    dpp_url = f"{PUBLIC_BASE}/dpp/1"  # 
    qr = qrcode.QRCode(version=1, box_size=10, border=2)  # 
    qr.add_data(dpp_url)  # 
    qr.make(fit=True)  # 
    img = qr.make_image(fill_color="black", back_color="white")  # 
    buf = io.BytesIO()  # 
    img.save(buf, format="PNG")  # 
    buf.seek(0)  # 
    return StreamingResponse(buf, media_type="image/png")  # 

@app.get("/qrcode/docs")
def get_qrcode_docs():
    """QR para a página Swagger (/docs)"""  # 
    docs_url = f"{PUBLIC_BASE}/docs"  # 
    qr = qrcode.QRCode(version=1, box_size=10, border=2)  # 
    qr.add_data(docs_url)  # 
    qr.make(fit=True)  # 
    img = qr.make_image(fill_color="black", back_color="white")  # 
    buf = io.BytesIO()  # 
    img.save(buf, format="PNG")  # 
    buf.seek(0)  # 
    return StreamingResponse(buf, media_type="image/png")  # 
