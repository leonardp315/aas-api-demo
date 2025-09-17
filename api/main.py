# api/main.py
import os
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Request, Header, Depends
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, ValidationError
import qrcode
from io import BytesIO

# -----------------------------------------------------------------------------
# Configuração básica
# -----------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"
DATA_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# URL pública usada nas páginas e QR (ajuste após o deploy)
PUBLIC_BASE = os.getenv("https://aas-api-demo.onrender.com/", "http://localhost:8000")
API_KEY_BACKEND = os.getenv("@senha123", "dev-key-change")
AAS_FILE = DATA_DIR / "aas_1.json"  # AAS do produto id=1 salvo localmente

app = FastAPI(title="AAS + DPP Demo API")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# -----------------------------------------------------------------------------
# Modelos Pydantic para submodelos mínimos
# -----------------------------------------------------------------------------
class Nameplate(BaseModel):
    manufacturer: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    serialNumber: str = Field(..., min_length=1)

class TechnicalData(BaseModel):
    power: Optional[str] = None
    weight: Optional[str] = None

class AASModel(BaseModel):
    id: str
    submodels: Dict[str, Dict[str, Any]]

# -----------------------------------------------------------------------------
# Utilidades de persistência simples em arquivo
# -----------------------------------------------------------------------------
def default_aas() -> AASModel:
    return AASModel(
        id="1",
        submodels={
            "nameplate": Nameplate(
                manufacturer="Desconhecido",
                model="Desconhecido",
                serialNumber="SN-0000"
            ).model_dump(),
            "technicalData": TechnicalData().model_dump(),
        },
    )

def load_aas() -> AASModel:
    if not AAS_FILE.exists():
        save_aas(default_aas())
    with open(AAS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    try:
        return AASModel(**data)
    except ValidationError:
        # Recria caso esteja corrompido
        aas = default_aas()
        save_aas(aas)
        return aas

def save_aas(aas: AASModel) -> None:
    with open(AAS_FILE, "w", encoding="utf-8") as f:
        json.dump(aas.model_dump(), f, ensure_ascii=False, indent=2)

# -----------------------------------------------------------------------------
# Dependência de autenticação para rotas de escrita
# -----------------------------------------------------------------------------
def require_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    if API_KEY_BACKEND and x_api_key != API_KEY_BACKEND:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-KEY")

# -----------------------------------------------------------------------------
# Normalização leve de unidades (exemplo)
# -----------------------------------------------------------------------------
def normalize_units(tech: TechnicalData) -> TechnicalData:
    p = tech.power
    w = tech.weight
    if p:
        p = p.replace("Watt", "W").replace("watts", "W").replace("Watts", "W")
        p = re.sub(r"\s+", " ", p).strip()
    if w:
        w = w.replace("kgs", "kg").replace("KG", "kg")
        w = re.sub(r"\s+", " ", w).strip()
    return TechnicalData(power=p, weight=w)

# -----------------------------------------------------------------------------
# Rotas AAS
# -----------------------------------------------------------------------------
@app.get("/aas/{asset_id}", response_class=JSONResponse)
def get_aas(asset_id: str):
    aas = load_aas()
    if aas.id != asset_id:
        raise HTTPException(status_code=404, detail="AAS not found")
    return aas.model_dump()

@app.put("/aas/{asset_id}/submodel/{name}", dependencies=[Depends(require_api_key)])
def put_submodel(asset_id: str, name: str, payload: Dict[str, Any]):
    aas = load_aas()
    if aas.id != asset_id:
        raise HTTPException(status_code=404, detail="AAS not found")
    # validação por submodelo
    if name == "nameplate":
        obj = Nameplate(**payload)
        aas.submodels[name] = obj.model_dump()
    elif name == "technicalData":
        obj = TechnicalData(**payload)
        obj = normalize_units(obj)
        aas.submodels[name] = obj.model_dump()
    else:
        # permitir submodelos livres no POC, mantendo dicionário
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Payload must be a JSON object")
        aas.submodels[name] = payload
    save_aas(aas)
    return {"ok": True, "submodel": name}

# -----------------------------------------------------------------------------
# Composição simples do DPP a partir do AAS
# -----------------------------------------------------------------------------
def build_dpp_from_aas(aas: AASModel) -> Dict[str, Any]:
    nameplate = aas.submodels.get("nameplate", {})
    tech = aas.submodels.get("technicalData", {})
    dpp = {
        "productId": aas.id,
        "nameplate": {
            "manufacturer": nameplate.get("manufacturer"),
            "model": nameplate.get("model"),
            "serialNumber": nameplate.get("serialNumber"),
        },
        "technicalData": {
            "power": tech.get("power"),
            "weight": tech.get("weight"),
        },
        "links": {
            "aas": f"{PUBLIC_BASE}/aas/{aas.id}",
            "self": f"{PUBLIC_BASE}/dpp/{aas.id}",
        },
        "meta": {
            "schema": "DPP-minimal-v0",
        },
    }
    return dpp

@app.get("/dpp/{asset_id}", response_class=JSONResponse)
def get_dpp(asset_id: str):
    aas = load_aas()
    if aas.id != asset_id:
        raise HTTPException(status_code=404, detail="DPP not found")
    return build_dpp_from_aas(aas)

# -----------------------------------------------------------------------------
# Páginas de visualização (Jinja2)
# -----------------------------------------------------------------------------
@app.get("/view/dpp/{asset_id}", response_class=HTMLResponse)
def view_dpp(asset_id: str, request: Request):
    aas = load_aas()
    if aas.id != asset_id:
        raise HTTPException(status_code=404, detail="Not found")
    dpp = build_dpp_from_aas(aas)
    qrcode_url = f"{PUBLIC_BASE}/qrcode?target={PUBLIC_BASE}/dpp/{asset_id}"
    return templates.TemplateResponse(
        "dpp.html",
        {
            "request": request,
            "dpp": dpp,
            "qrcode_url": qrcode_url,
            "public_base": PUBLIC_BASE,
        },
    )

@app.get("/view/label/{asset_id}", response_class=HTMLResponse)
def view_label(asset_id: str, request: Request):
    aas = load_aas()
    if aas.id != asset_id:
        raise HTTPException(status_code=404, detail="Not found")
    np = aas.submodels.get("nameplate", {})
    qrcode_url = f"{PUBLIC_BASE}/qrcode?target={PUBLIC_BASE}/dpp/{asset_id}"
    return templates.TemplateResponse(
        "label.html",
        {
            "request": request,
            "nameplate": np,
            "qrcode_url": qrcode_url,
        },
    )

# -----------------------------------------------------------------------------
# QR code
# -----------------------------------------------------------------------------
@app.get("/qrcode")
def get_qrcode(target: str):
    if not target or not target.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid target")
    img = qrcode.make(target)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")

# -----------------------------------------------------------------------------
# Bootstrap de templates básicos se não existirem
# -----------------------------------------------------------------------------
DPP_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><title>DPP</title>
<link rel="stylesheet" href="{{ public_base }}/static/style.css">
<style>
body { font-family: Arial, sans-serif; margin: 24px; }
.card { border: 1px solid #ddd; border-radius: 8px; padding: 16px; max-width: 720px; }
h1 { margin: 0 0 12px 0; font-size: 20px; }
h2 { font-size: 16px; margin-top: 18px; }
.row { display: flex; gap: 24px; align-items: flex-start; }
.meta { color: #666; font-size: 12px; margin-top: 12px; }
.kv { margin: 4px 0; }
.kv span { color: #333; }
.qr { margin-top: 12px; }
</style>
</head><body>
<div class="card">
  <h1>Digital Product Passport — ID {{ dpp.productId }}</h1>
  <div class="row">
    <div style="flex:1">
      <h2>Nameplate</h2>
      <div class="kv">Manufacturer: <span>{{ dpp.nameplate.manufacturer }}</span></div>
      <div class="kv">Model: <span>{{ dpp.nameplate.model }}</span></div>
      <div class="kv">Serial: <span>{{ dpp.nameplate.serialNumber }}</span></div>

      <h2>Technical Data</h2>
      <div class="kv">Power: <span>{{ dpp.technicalData.power }}</span></div>
      <div class="kv">Weight: <span>{{ dpp.technicalData.weight }}</span></div>

      <h2>Links</h2>
      <div class="kv"><a href="{{ dpp.links.aas }}" target="_blank">AAS JSON</a></div>
      <div class="kv"><a href="{{ dpp.links.self }}" target="_blank">DPP JSON</a></div>

      <div class="meta">Schema: {{ dpp.meta.schema }}</div>
    </div>
    <div class="qr">
      <img src="{{ qrcode_url }}" width="180" />
    </div>
  </div>
</div>
</body></html>
"""

LABEL_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><title>Etiqueta</title>
<style>
body { font-family: Arial, sans-serif; margin: 24px; }
.big { font-size: 20px; margin: 6px 0; }
.qr { margin-top: 12px; }
</style>
</head><body>
<div class="big">{{ nameplate.get('manufacturer', '') }}</div>
<div class="big">{{ nameplate.get('model', '') }}</div>
<div>SN: {{ nameplate.get('serialNumber', '') }}</div>
<div class="qr"><img src="{{ qrcode_url }}" width="220" /></div>
</body></html>
"""

STYLE_CSS = """body { background: #fff; } a { color: #0b5bd3; text-decoration: none; } a:hover { text-decoration: underline; }"""

def ensure_templates():
    dpp_path = TEMPLATES_DIR / "dpp.html"
    label_path = TEMPLATES_DIR / "label.html"
    css_path = STATIC_DIR / "style.css"
    if not dpp_path.exists():
        dpp_path.write_text(DPP_HTML, encoding="utf-8")
    if not label_path.exists():
        label_path.write_text(LABEL_HTML, encoding="utf-8")
    if not css_path.exists():
        css_path.write_text(STYLE_CSS, encoding="utf-8")

ensure_templates()

# -----------------------------------------------------------------------------
# Raiz
# -----------------------------------------------------------------------------
@app.get("/", response_class=JSONResponse)
def root():
    return {
        "service": "AAS + DPP Demo",
        "endpoints": [
            "/aas/1",
            "/aas/1/submodel/nameplate [PUT]",
            "/aas/1/submodel/technicalData [PUT]",
            "/dpp/1",
            "/view/dpp/1",
            "/view/label/1",
            "/qrcode?target=<url>",
        ],
        "public_base": PUBLIC_BASE,
    }
