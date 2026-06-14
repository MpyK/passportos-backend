# dpp_data.py
# Real DPP data for our 3 weclapp articles
# Keyed by weclapp article ID

DPP_DATABASE = {
    "4555": {  # LONGi Solar
        "weclapp_id": "4555",
        "article_number": "PV-001",
        "manufacturer": "LONGi Solar",
        "model": "Hi-MO 6 Explorer LR5-72HIH-580M",
        "technology": "HPBC Monocrystalline",
        "power_wp": 580,
        "price_per_wp_eur": 0.28,
        "cell_origin": "Xi'an, China",
        "assembly_origin": "Salzburg, Austria",
        # Carbon
        "carbon_per_wp": 0.72,
        "carbon_class": "A",
        "renewable_manufacturing": True,
        "renewable_source": "Hydropower (Austria)",
        "carbon_payback_years": 1.2,
        # Materials
        "silicon_origin": "China",
        "silicon_risk": "MEDIUM",
        "silver_origin": "Mexico",
        "silver_risk": "LOW",
        "lead_free": True,
        "conflict_mineral_free": True,
        # Compliance
        "compliance_status": "COMPLIANT",
        "ce_marked": True,
        "iec_61215": True,
        "iec_61730": True,
        "weee_compliant": True,
        "rohs_compliant": True,
        "notified_body": "TUV Rheinland",
        "epd_available": True,
        # Performance
        "efficiency_pct": 22.8,
        "degradation_annual_pct": 0.4,
        "performance_warranty_years": 30,
        "recyclability_pct": 92,
        "second_life_eligible": False,
        "eol_value_eur": 45,
        # Supplier
        "supplier_name": "LONGi Green Energy Technology",
        "ethics_score": 72,
        "forced_labour_risk": "LOW",
        "third_party_audited": True,
        "audit_standard": "RBA (Responsible Business Alliance)",
    },
    "4547": {  # Meyer Burger
        "weclapp_id": "4547",
        "article_number": "PV-002",
        "manufacturer": "Meyer Burger Technology",
        "model": "Meyer Burger White 395W HJT",
        "technology": "Heterojunction (HJT)",
        "power_wp": 395,
        "price_per_wp_eur": 0.52,
        "cell_origin": "Freiberg, Germany",
        "assembly_origin": "Freiberg, Germany",
        # Carbon
        "carbon_per_wp": 0.47,
        "carbon_class": "A+",
        "renewable_manufacturing": True,
        "renewable_source": "100% German Renewables",
        "carbon_payback_years": 0.7,
        # Materials
        "silicon_origin": "Germany (Wacker Chemie)",
        "silicon_risk": "LOW",
        "silver_origin": "EU Recycled",
        "silver_risk": "LOW",
        "lead_free": True,
        "conflict_mineral_free": True,
        # Compliance
        "compliance_status": "COMPLIANT",
        "ce_marked": True,
        "iec_61215": True,
        "iec_61730": True,
        "weee_compliant": True,
        "rohs_compliant": True,
        "notified_body": "TUV SUD",
        "epd_available": True,
        # Performance
        "efficiency_pct": 21.5,
        "degradation_annual_pct": 0.25,
        "performance_warranty_years": 40,
        "recyclability_pct": 96,
        "second_life_eligible": True,
        "eol_value_eur": 68,
        # Supplier
        "supplier_name": "Meyer Burger Technology AG",
        "ethics_score": 96,
        "forced_labour_risk": "NONE",
        "third_party_audited": True,
        "audit_standard": "EcoVadis Platinum",
    },
    "4551": {  # Jinko Solar
        "weclapp_id": "4551",
        "article_number": "PV-003",
        "manufacturer": "Jinko Solar",
        "model": "Tiger Neo N-type 72HL4-V 580W",
        "technology": "TOPCon Monocrystalline",
        "power_wp": 580,
        "price_per_wp_eur": 0.22,
        "cell_origin": "Shanxi, China",
        "assembly_origin": "Shanxi, China",
        # Carbon
        "carbon_per_wp": 1.17,
        "carbon_class": "B",
        "renewable_manufacturing": False,
        "renewable_source": None,
        "carbon_payback_years": 2.1,
        # Materials
        "silicon_origin": "China",
        "silicon_risk": "MEDIUM",
        "silver_origin": "China",
        "silver_risk": "MEDIUM",
        "lead_free": True,
        "conflict_mineral_free": True,
        # Compliance
        "compliance_status": "COMPLIANT",
        "ce_marked": True,
        "iec_61215": True,
        "iec_61730": True,
        "weee_compliant": True,
        "rohs_compliant": True,
        "notified_body": "TUV Rheinland",
        "epd_available": False,
        # Performance
        "efficiency_pct": 22.3,
        "degradation_annual_pct": 0.4,
        "performance_warranty_years": 25,
        "recyclability_pct": 88,
        "second_life_eligible": False,
        "eol_value_eur": 38,
        # Supplier
        "supplier_name": "Jinko Solar Co. Ltd",
        "ethics_score": 61,
        "forced_labour_risk": "MEDIUM",
        "third_party_audited": True,
        "audit_standard": "SMETA (Sedex)",
    }
}


def get_dpp_by_weclapp_id(weclapp_id):
    return DPP_DATABASE.get(str(weclapp_id))


def get_all_dpp():
    return list(DPP_DATABASE.values())


def score_panel(dpp):
    """Compute a DPP procurement score 0-100."""
    score = 0

    # Compliance (25 points)
    if dpp["compliance_status"] == "COMPLIANT" and dpp["ce_marked"] and dpp["iec_61215"]:
        score += 25

    # Ethics (20 points)
    risk_map = {"NONE": 20, "LOW": 16, "MEDIUM": 10, "HIGH": 3, "UNKNOWN": 0}
    ethics_pts = (dpp["ethics_score"] / 100 * 10) + risk_map.get(dpp["forced_labour_risk"], 0)
    score += min(20, ethics_pts)

    # Carbon (25 points)
    co2 = dpp["carbon_per_wp"]
    if co2 <= 0.5:   score += 25
    elif co2 <= 0.75: score += 20
    elif co2 <= 1.0:  score += 13
    else:             score += 5
    if dpp["renewable_manufacturing"]: score += 3

    # Performance (20 points)
    eff = dpp["efficiency_pct"]
    deg = dpp["degradation_annual_pct"]
    warr = dpp["performance_warranty_years"]
    perf = (min(eff, 25) / 25 * 10) + (max(0, 1 - deg) * 5) + (min(warr, 40) / 40 * 5)
    score += min(20, perf)

    # Price (10 points)
    price = dpp.get("price_per_wp_eur") or 0.0
    try:
        price = float(price)
    except (TypeError, ValueError):
        price = 0.0
    if price <= 0.0:    score += 5  # unknown price gets neutral score
    elif price <= 0.25: score += 10
    elif price <= 0.35: score += 8
    elif price <= 0.50: score += 6
    elif price <= 0.65: score += 4
    else:               score += 2

    return round(min(100, score), 1)
