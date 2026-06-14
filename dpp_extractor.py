# dpp_extractor.py
# Extracts DPP fields from 3 sources:
# 1. PDF datasheet upload
# 2. Product name search (AI knowledge)
# 3. Manual input validation
# All using Groq LLaMA 3.3 70B

import json
import requests
import os

GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL    = "llama-3.3-70b-versatile"

# ── DPP field schema ───────────────────────────────────────────────────────────
DPP_FIELDS = {
    # General
    "manufacturer":              {"label": "Manufacturer",              "type": "str",   "required": True},
    "model":                     {"label": "Model Name",                "type": "str",   "required": True},
    "technology":                {"label": "Technology",                "type": "str",   "required": True},
    "power_wp":                  {"label": "Power (Wp)",                "type": "float", "required": True},
    "price_per_wp_eur":          {"label": "Price (€/Wp)",              "type": "float", "required": False},
    "cell_origin":               {"label": "Cell Manufacturing Origin", "type": "str",   "required": True},
    "assembly_origin":           {"label": "Assembly Origin",           "type": "str",   "required": False},
    # Carbon
    "carbon_per_wp":             {"label": "Carbon Footprint (kg CO₂/Wp)", "type": "float", "required": True},
    "carbon_class":              {"label": "Carbon Class (A+/A/B/C)",   "type": "str",   "required": True},
    "renewable_manufacturing":   {"label": "Renewable Energy in Mfg",  "type": "bool",  "required": False},
    "renewable_source":          {"label": "Renewable Source",         "type": "str",   "required": False},
    "carbon_payback_years":      {"label": "Carbon Payback (years)",   "type": "float", "required": False},
    # Materials
    "silicon_origin":            {"label": "Silicon Origin",           "type": "str",   "required": True},
    "silicon_risk":              {"label": "Silicon Risk (LOW/MEDIUM/HIGH)", "type": "str", "required": True},
    "silver_origin":             {"label": "Silver Origin",            "type": "str",   "required": False},
    "silver_risk":               {"label": "Silver Risk",              "type": "str",   "required": False},
    "lead_free":                 {"label": "Lead Free",                "type": "bool",  "required": True},
    "conflict_mineral_free":     {"label": "Conflict Mineral Free",    "type": "bool",  "required": False},
    # Compliance
    "compliance_status":         {"label": "EU Compliance Status",     "type": "str",   "required": True},
    "ce_marked":                 {"label": "CE Marked",                "type": "bool",  "required": True},
    "iec_61215":                 {"label": "IEC 61215 Certified",      "type": "bool",  "required": True},
    "iec_61730":                 {"label": "IEC 61730 Certified",      "type": "bool",  "required": True},
    "weee_compliant":            {"label": "WEEE Compliant",           "type": "bool",  "required": True},
    "rohs_compliant":            {"label": "RoHS Compliant",           "type": "bool",  "required": False},
    "notified_body":             {"label": "Notified Body",            "type": "str",   "required": False},
    "epd_available":             {"label": "EPD Available",            "type": "bool",  "required": False},
    # Performance
    "efficiency_pct":            {"label": "Efficiency (%)",           "type": "float", "required": True},
    "degradation_annual_pct":    {"label": "Annual Degradation (%)",   "type": "float", "required": False},
    "performance_warranty_years":{"label": "Performance Warranty (yr)","type": "int",   "required": False},
    # EOL
    "recyclability_pct":         {"label": "Recyclability (%)",        "type": "float", "required": False},
    "second_life_eligible":      {"label": "Second Life Eligible",     "type": "bool",  "required": False},
    "eol_value_eur":             {"label": "EOL Value (€)",            "type": "float", "required": False},
    # Supplier
    "supplier_name":             {"label": "Supplier / Company Name",  "type": "str",   "required": True},
    "ethics_score":              {"label": "Ethics Score (0-100)",     "type": "int",   "required": True},
    "forced_labour_risk":        {"label": "Forced Labour Risk",       "type": "str",   "required": True},
    "third_party_audited":       {"label": "Third-Party Audited",      "type": "bool",  "required": False},
    "audit_standard":            {"label": "Audit Standard",           "type": "str",   "required": False},
}

EXTRACTION_PROMPT = """You are a DPP (Digital Product Passport) data extraction expert for EU energy products including solar panels, EV batteries, and industrial battery packs.

Extract DPP fields from the document. Return ONLY a valid JSON object.
Use your training knowledge to fill fields not explicitly in the document.
Only use null if you genuinely have no knowledge at all.

PRODUCT TYPE DETECTION:
- If the document mentions kWh, Ah, NMC, LFP, BMS, cell chemistry → it's a BATTERY
- If the document mentions Wp, solar module, photovoltaic, IEC 61215 → it's a SOLAR PANEL
- Adapt your extraction accordingly

FOR BATTERIES — key field mappings:
- technology = cell chemistry (NMC, LFP, NCA, etc.)
- power_wp = energy capacity in kWh × 1000 (e.g. 75kWh → 75000)
- efficiency_pct = round-trip efficiency or charge efficiency (typically 92-97% for NMC)
- carbon_per_wp = carbon per kWh (EU Battery Reg: typically 60-100 kg CO2e/kWh for NMC)
- carbon_class = "A" for <65 kg/kWh, "B" for 65-85, "C" for >85
- silicon_origin = lithium origin (main critical mineral for batteries)
- silicon_risk = lithium supply risk (Chile/Australia = LOW, China = MEDIUM, DRC cobalt = HIGH)
- iec_61215 = false for batteries (solar cert), use ce_marked and weee_compliant
- For NMC batteries: cobalt origin matters most for ethics score
- ECE R100 certification = equivalent to ce_marked for vehicle batteries

KNOWN FACTS:
- Ampherr AG: German company (Neuss), NMC battery packs, IATF 16949 certified, ethics_score ~78, forced_labour_risk "LOW"
- Northvolt: Swedish, LFP/NMC, renewable manufacturing in Sweden, ethics_score ~88
- CATL: Chinese, NMC/LFP, ethics_score ~62, forced_labour_risk "MEDIUM"
- Samsung SDI: Korean, NMC, ethics_score ~80, forced_labour_risk "LOW"
- Meyer Burger: German HJT panels, carbon 0.47 kg/Wp, ethics 96, silicon from Wacker Chemie Germany
- LONGi: Chinese HPBC panels, carbon 0.72 kg/Wp, silicon from China MEDIUM risk
- Jinko Solar: Chinese TOPCon, carbon 1.17 kg/Wp, silicon+silver from China MEDIUM risk

Extract these fields:
- manufacturer (string — company name from document)
- model (string — product model/part number)
- technology (string — cell chemistry or panel type)
- power_wp (number — kWh×1000 for batteries, Wp for panels)
- price_per_wp_eur (number or null)
- cell_origin (string — where cells/modules are made)
- assembly_origin (string — where pack/module assembled)
- carbon_per_wp (number — kg CO2e per kWh for batteries, per Wp for panels)
- carbon_class (string: "A+","A","B","C")
- renewable_manufacturing (boolean)
- renewable_source (string or null)
- carbon_payback_years (number or null)
- silicon_origin (string — lithium origin for batteries, silicon origin for panels)
- silicon_risk (string: "LOW","MEDIUM","HIGH")
- silver_origin (string or null — cobalt origin for batteries)
- silver_risk (string or null — cobalt risk for batteries)
- lead_free (boolean)
- conflict_mineral_free (boolean — false if cobalt from DRC unaudited)
- compliance_status (string: "COMPLIANT" or "NON-COMPLIANT")
- ce_marked (boolean — true if CE, ECE R100, or equivalent)
- iec_61215 (boolean — true only for solar panels)
- iec_61730 (boolean — true only for solar panels)
- weee_compliant (boolean)
- rohs_compliant (boolean)
- notified_body (string or null)
- epd_available (boolean)
- efficiency_pct (number — round-trip efficiency for batteries, module efficiency for panels)
- degradation_annual_pct (number — capacity fade %/year for batteries)
- performance_warranty_years (integer — warranty years)
- recyclability_pct (number — estimated % recyclable by mass)
- second_life_eligible (boolean — true if SoH > 70% after primary use)
- eol_value_eur (number or null — estimated scrap/recycling value)
- supplier_name (string — full legal company name)
- ethics_score (integer 0-100)
- forced_labour_risk (string: "NONE","LOW","MEDIUM","HIGH")
- third_party_audited (boolean)
- audit_standard (string or null)

RULES:
1. ALWAYS extract manufacturer and model — they are always in the document
2. For batteries: compliance_status = "COMPLIANT" if ECE R100 or equivalent present
3. Return ONLY the JSON object, no markdown, no explanation
4. Never return null for manufacturer, model, technology, supplier_name"""


def call_groq(system_prompt, user_content, max_tokens=2000):
    """Call Groq API and return the response text."""
    if not GROQ_KEY:
        return None, "GROQ_API_KEY not set"
    try:
        r = requests.post(
            GROQ_URL,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {GROQ_KEY}"},
            json={"model": MODEL, "max_tokens": max_tokens,
                  "messages": [
                      {"role": "system", "content": system_prompt},
                      {"role": "user",   "content": user_content}
                  ]},
            timeout=30
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"], None
    except Exception as e:
        return None, str(e)


def clean_and_parse(raw):
    """Robustly extract JSON from AI response regardless of formatting."""
    if not raw:
        return None
    raw = raw.strip()
    # Remove markdown code blocks
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break
    # Find the JSON object
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    raw = raw[start:end]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try fixing common issues
        import re
        raw = re.sub(r',\s*}', '}', raw)   # trailing commas
        raw = re.sub(r',\s*]', ']', raw)
        try:
            return json.loads(raw)
        except:
            return None


def extract_from_pdf_text(pdf_text):
    truncated = pdf_text[:8000]
    user_msg = f"""Extract DPP data from this solar panel datasheet.
For fields NOT found in the document, use your training knowledge about this manufacturer/product.

Datasheet text:
{truncated}"""
    raw, err = call_groq(EXTRACTION_PROMPT, user_msg)
    if err:
        return None, [], [f"AI error: {err}"]
    dpp = clean_and_parse(raw)
    if not dpp:
        return None, [], ["Could not parse AI response — try manual entry"]
    missing, warnings = validate_dpp(dpp)
    return dpp, missing, warnings


def extract_from_product_name(product_name):
    user_msg = f"Extract DPP data for this solar panel product: {product_name}"
    raw, err = call_groq(EXTRACTION_PROMPT, user_msg)
    if err:
        return None, [], [f"AI error: {err}"]
    dpp = clean_and_parse(raw)
    if not dpp:
        return None, [], ["Could not parse AI response — try manual entry"]
    missing, warnings = validate_dpp(dpp)
    return dpp, missing, warnings


def validate_dpp(dpp):
    missing = []
    warnings = []

    # Only require truly universal fields
    universal_required = ["manufacturer", "model", "technology", "supplier_name", "compliance_status"]
    for key in universal_required:
        if not dpp.get(key):
            missing.append(DPP_FIELDS.get(key, {}).get("label", key))

    # Detect product type
    is_battery = any([
        dpp.get("technology","").upper() in ["NMC","LFP","NCA","LTO","LIFEPO4"],
        "kwh" in str(dpp.get("model","")).lower(),
        (dpp.get("power_wp") or 0) > 5000,
    ])

    # For non-batteries require solar fields
    if not is_battery:
        for key in ["carbon_per_wp","carbon_class","silicon_origin","silicon_risk","efficiency_pct"]:
            if dpp.get(key) is None:
                missing.append(DPP_FIELDS.get(key,{}).get("label", key))

    # Risk warnings
    silicon_risk = dpp.get("silicon_risk","")
    if silicon_risk == "HIGH":
        warnings.append("⚠️ HIGH supply chain risk — potential conflict mineral exposure")
    if dpp.get("forced_labour_risk") in ["MEDIUM","HIGH"]:
        warnings.append(f"⚠️ {dpp.get('forced_labour_risk')} forced labour risk flagged")
    if dpp.get("carbon_per_wp") and not is_battery and dpp["carbon_per_wp"] > 1.0:
        warnings.append(f"⚠️ High carbon: {dpp['carbon_per_wp']} kg CO₂/Wp — above Class B threshold")
    if not dpp.get("ce_marked"):
        warnings.append("⚠️ CE marking not confirmed")
    if dpp.get("silicon_origin") and "xinjiang" in str(dpp.get("silicon_origin","")).lower():
        warnings.append("🚨 CRITICAL: Xinjiang origin detected — forced labour sanctions may apply")

    # Auto compliance
    if dpp.get("ce_marked"):
        dpp["compliance_status"] = "COMPLIANT"
    elif not dpp.get("compliance_status"):
        dpp["compliance_status"] = "UNKNOWN"

    # Fill safe defaults for missing optional fields
    if dpp.get("efficiency_pct") is None and is_battery:
        dpp["efficiency_pct"] = 95.0  # typical NMC round-trip

    return missing, warnings


def prepare_for_weclapp(dpp, weclapp_id):
    """Convert DPP dict to weclapp custom attributes format."""
    dpp["weclapp_id"] = weclapp_id

    # Only include non-null values
    attrs = []
    field_map = {
        "compliance_status":      "dpp_compliance_status",
        "carbon_per_wp":          "dpp_carbon_per_wp",
        "carbon_class":           "dpp_carbon_class",
        "ethics_score":           "dpp_ethics_score",
        "silicon_origin":         "dpp_silicon_origin",
        "silicon_risk":           "dpp_silicon_risk",
        "recyclability_pct":      "dpp_recyclability_pct",
        "ce_marked":              "dpp_ce_marked",
        "iec_61215":              "dpp_iec_61215",
        "iec_61730":              "dpp_iec_61730",
        "weee_compliant":         "dpp_weee_compliant",
        "forced_labour_risk":     "dpp_forced_labour_risk",
        "efficiency_pct":         "dpp_efficiency_pct",
        "manufacturer":           "dpp_manufacturer",
        "model":                  "dpp_model",
        "cell_origin":            "dpp_cell_origin",
        "renewable_manufacturing":"dpp_renewable_manufacturing",
    }

    from datetime import datetime
    attrs.append({"attributeName": "dpp_last_updated",
                  "stringValue": datetime.now().strftime("%Y-%m-%d %H:%M")})

    for field, attr_name in field_map.items():
        val = dpp.get(field)
        if val is not None:
            attrs.append({"attributeName": attr_name, "stringValue": str(val)})

    return attrs
