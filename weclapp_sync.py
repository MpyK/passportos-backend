from weclapp_client import WeclappClient
from dpp_data import get_dpp_by_weclapp_id, score_panel

def get_merged_articles(weclapp_url, weclapp_token):
    """
    Pull real articles from weclapp, merge with DPP data where available.
    Returns list of articles enriched with DPP data.
    """
    client = WeclappClient(weclapp_url, weclapp_token)
    
    try:
        articles = client.get_articles(limit=50)
    except Exception as e:
        raise Exception(f"Failed to connect to weclapp: {str(e)}")

    result = []
    for article in articles:
        article_id = article.get("id")
        name = article.get("name", "Unknown")
        number = article.get("articleNumber", "")

        # Try to match with hardcoded DPP data
        dpp = get_dpp_by_weclapp_id(article_id)

        if dpp:
            # We have DPP data for this article
            d = dict(dpp)
            d["score"] = score_panel(dpp)
            d["has_dpp"] = True
            d["weclapp_name"] = name
            d["article_number"] = number
        else:
            # No DPP data yet — return basic article info
            d = {
                "weclapp_id": article_id,
                "article_number": number,
                "manufacturer": name,
                "model": "",
                "technology": "Unknown",
                "has_dpp": False,
                "score": 0,
                "compliance_status": "NO DPP YET",
                "carbon_class": "—",
                "carbon_per_wp": 0,
                "efficiency_pct": 0,
                "ethics_score": 0,
                "power_wp": 0,
                "weclapp_name": name,
            }
        result.append(d)

    return result


def get_kpis(articles):
    """Compute KPIs from merged article list."""
    total = len(articles)
    if total == 0:
        return {"total": 0, "compliant": 0, "avg_carbon": 0, "avg_score": 0}
    
    with_dpp = [a for a in articles if a.get("has_dpp")]
    compliant = sum(1 for a in with_dpp if a.get("compliance_status") == "COMPLIANT")
    avg_carbon = round(sum(a.get("carbon_per_wp", 0) for a in with_dpp) / len(with_dpp), 2) if with_dpp else 0
    avg_score = round(sum(a.get("score", 0) for a in with_dpp) / len(with_dpp), 1) if with_dpp else 0

    return {
        "total": total,
        "with_dpp": len(with_dpp),
        "compliant": compliant,
        "avg_carbon": avg_carbon,
        "avg_score": avg_score,
    }