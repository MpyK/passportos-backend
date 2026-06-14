from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json, os, requests as _requests

import sys
sys.path.append(os.path.dirname(__file__))
from weclapp_client import WeclappClient
from dpp_data import get_dpp_by_weclapp_id, get_all_dpp, score_panel, DPP_DATABASE
from dpp_extractor import extract_from_pdf_text, extract_from_product_name, validate_dpp, DPP_FIELDS

WECLAPP_URL   = os.environ.get("WECLAPP_URL",   "https://fdhlqfdrdeamywv.weclapp.com/webapp/api/v1")
WECLAPP_TOKEN = os.environ.get("WECLAPP_TOKEN", "dccfb19c-2f88-4a48-b42d-7a7cdbe09457")
GROQ_KEY      = os.environ.get("GROQ_KEY",      "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")
GROQ_URL      = "https://api.groq.com/openai/v1/chat/completions"

app = FastAPI(title="PassportOS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_client(request: Request):
    url   = request.headers.get("X-Weclapp-URL",   WECLAPP_URL)
    token = request.headers.get("X-Weclapp-Token", WECLAPP_TOKEN)
    return WeclappClient(url, token)

class PushDPPRequest(BaseModel):
    weclapp_id: str

class ProductNameRequest(BaseModel):
    product_name: str

class ChatRequest(BaseModel):
    messages: list

class ManualDPPRequest(BaseModel):
    weclapp_id: str
    dpp: dict

@app.get("/")
def root():
    return {"status": "PassportOS API running", "version": "1.0.0"}

@app.get("/api/dashboard")
def get_dashboard(request: Request):
    all_dpp = get_all_dpp()
    result = []
    for dpp in all_dpp:
        d = dict(dpp)
        d["score"] = score_panel(dpp)
        result.append(d)
    compliant  = sum(1 for d in all_dpp if d.get("compliance_status") == "COMPLIANT")
    avg_carbon = round(sum(d.get("carbon_per_wp", 0) for d in all_dpp) / len(all_dpp), 2)
    avg_score  = round(sum(score_panel(d) for d in all_dpp) / len(all_dpp), 1)
    return {
        "products": result,
        "kpis": {"total": len(all_dpp), "compliant": compliant,
                 "avg_carbon": avg_carbon, "avg_score": avg_score}
    } 

""" 
@app.get("/api/dashboard")
def get_dashboard(request: Request):
    from weclapp_sync import get_merged_articles, get_kpis
    url   = request.headers.get("X-Weclapp-URL",   WECLAPP_URL)
    token = request.headers.get("X-Weclapp-Token", WECLAPP_TOKEN)
    try:
        articles = get_merged_articles(url, token)
        kpis = get_kpis(articles)
        return {"products": articles, "kpis": kpis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
""" 

@app.get("/api/weclapp/articles")
def get_weclapp_articles(request: Request):
    client = get_client(request)
    try:
        articles = client.get_articles(limit=50)
        return {"articles": articles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/weclapp/push")
def push_dpp_to_weclapp(req: PushDPPRequest, request: Request):
    client = get_client(request)
    dpp = get_dpp_by_weclapp_id(req.weclapp_id)
    if not dpp:
        raise HTTPException(status_code=404, detail=f"No DPP found for {req.weclapp_id}")
    try:
        client.push_dpp_to_description(req.weclapp_id, dpp)
        return {"success": True, "message": f"DPP pushed to weclapp article {req.weclapp_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/procurement")
def get_procurement():
    all_dpp = get_all_dpp()
    ranked = sorted(all_dpp, key=lambda d: score_panel(d), reverse=True)
    result = []
    for i, dpp in enumerate(ranked):
        d = dict(dpp)
        d["score"] = score_panel(dpp)
        d["rank"] = i + 1
        result.append(d)
    return {"ranked": result}

@app.get("/api/eol")
def get_eol():
    all_dpp = get_all_dpp()
    result = []
    for dpp in all_dpp:
        rec    = dpp.get("recyclability_pct", 0)
        second = dpp.get("second_life_eligible", False)
        if second:       decision, color = "SECOND LIFE", "teal"
        elif rec >= 90:  decision, color = "RECYCLE", "green"
        elif rec >= 75:  decision, color = "RECYCLE", "yellow"
        else:            decision, color = "DISPOSE", "red"
        result.append({**dpp, "eol_decision": decision, "decision_color": color})
    return {"products": result}

@app.get("/api/esg")
def get_esg():
    all_dpp  = get_all_dpp()
    avg_co2  = sum(d.get("carbon_per_wp", 0) for d in all_dpp) / len(all_dpp)
    avg_rec  = sum(d.get("recyclability_pct", 0) for d in all_dpp) / len(all_dpp)
    renv     = sum(1 for d in all_dpp if d.get("renewable_manufacturing"))
    avg_eth  = sum(d.get("ethics_score", 0) for d in all_dpp) / len(all_dpp)
    flv      = sum(1 for d in all_dpp if d.get("forced_labour_risk") in ["MEDIUM","HIGH"])
    audv     = sum(1 for d in all_dpp if d.get("third_party_audited"))
    cp       = sum(1 for d in all_dpp if d.get("compliance_status") == "COMPLIANT") / len(all_dpp) * 100
    e = round(max(0, 100 - avg_co2 * 40 + (renv/len(all_dpp)) * 20 + avg_rec * 0.3))
    s = round(avg_eth * 0.7 + (1 - flv/len(all_dpp)) * 30)
    g = round(cp * 0.7 + (audv/len(all_dpp)) * 30)
    return {
        "scores": {"E": min(100,e), "S": min(100,s), "G": min(100,g)},
        "details": {"avg_carbon": round(avg_co2,2), "avg_recyclability": round(avg_rec,1),
                    "renewable_count": renv, "avg_ethics": round(avg_eth,1),
                    "forced_labour_flags": flv, "audited_count": audv,
                    "compliance_pct": round(cp,1), "total": len(all_dpp)}
    }

@app.post("/api/extract/pdf")
async def extract_from_pdf(file: UploadFile = File(...)):
    try:
        import pdfplumber, io
        content = await file.read()
        text = ""
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        dpp, missing, warnings = extract_from_pdf_text(text)
        if not dpp:
            raise HTTPException(status_code=400, detail="Could not extract DPP from PDF")
        return {"dpp": dpp, "missing": missing, "warnings": warnings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/extract/name")
def extract_from_name(req: ProductNameRequest):
    dpp, missing, warnings = extract_from_product_name(req.product_name)
    if not dpp:
        raise HTTPException(status_code=400, detail="Could not extract DPP")
    return {"dpp": dpp, "missing": missing, "warnings": warnings}

@app.post("/api/extract/push")
def push_extracted_dpp(req: ManualDPPRequest, request: Request):
    client = get_client(request)
    try:
        client.push_dpp_to_description(req.weclapp_id, req.dpp)
        return {"success": True, "message": f"DPP pushed to weclapp article {req.weclapp_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
def chat(req: ChatRequest):
    all_dpp = get_all_dpp()
    ctx = "\n".join([
        f"PANEL {d['weclapp_id']}: {d['manufacturer']} {d.get('model','')} | "
        f"{d['power_wp']}Wp @€{d['price_per_wp_eur']}/Wp | "
        f"Carbon: {d['carbon_per_wp']} kg/Wp ({d['carbon_class']}) | "
        f"Compliance: {d['compliance_status']} | Ethics: {d['ethics_score']}/100 | "
        f"Silicon: {d.get('silicon_origin','?')} ({d.get('silicon_risk','?')} risk) | "
        f"Labour: {d.get('forced_labour_risk','?')}"
        for d in all_dpp
    ])
    SYS = f"""You are PassportOS AI — expert in EU Digital Product Passports integrated with weclapp ERP.
Answer procurement, ESG, compliance, EOL, and geopolitical risk questions using real DPP data.
Be direct, cite real numbers. Under 200 words.
PANEL DATA:\n{ctx}
GEOPOLITICAL: China controls ~85% global silicon. Jinko most exposed. Meyer Burger safest."""
    try:
        r = _requests.post(GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "max_tokens": 800,
                  "messages": [{"role": "system", "content": SYS}, *req.messages]},
            timeout=30)
        r.raise_for_status()
        return {"reply": r.json()["choices"][0]["message"]["content"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))