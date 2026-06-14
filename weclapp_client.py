import requests
import json

class WeclappClient:
    def __init__(self, base_url, api_token):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "AuthenticationToken": api_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _get(self, endpoint, params=None):
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def _put(self, endpoint, data):
        url = f"{self.base_url}/{endpoint}"
        response = requests.put(url, headers=self.headers, data=json.dumps(data))
        if not response.ok:
            raise Exception(f"{response.status_code}: {response.text[:500]}")
        return response.json()

    def _post(self, endpoint, data):
        url = f"{self.base_url}/{endpoint}"
        response = requests.post(url, headers=self.headers, data=json.dumps(data))
        response.raise_for_status()
        return response.json()

    def get_articles(self, limit=50):
        result = self._get("article", params={"pageSize": limit})
        return result.get("result", [])

    def get_article_by_id(self, article_id):
        result = self._get(f"article/id/{article_id}")
        return result

    def get_suppliers(self, limit=50):
        result = self._get("supplier", params={"pageSize": limit})
        return result.get("result", [])

    def update_article(self, article_id, data):
        """Update any fields on an article."""
        data["id"] = article_id
        data["version"] = "0"
        result = self._put(f"article/id/{article_id}", data)
        return result

    def push_dpp_to_description(self, article_id, dpp):
        """
        Write DPP data into weclapp article description.
        Fetches full article first then sends it back with updated description.
        """
        from datetime import datetime

        # Get the FULL current article
        current = self._get(f"article/id/{article_id}")

        lines = [
            "=== DIGITAL PRODUCT PASSPORT (PassportOS) ===",
            f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "--- COMPLIANCE ---",
            f"Status: {dpp.get('compliance_status','N/A')}",
            f"CE Marked: {dpp.get('ce_marked','N/A')}",
            f"IEC 61215: {dpp.get('iec_61215','N/A')}",
            f"IEC 61730: {dpp.get('iec_61730','N/A')}",
            f"WEEE Compliant: {dpp.get('weee_compliant','N/A')}",
            f"Notified Body: {dpp.get('notified_body','N/A')}",
            "",
            "--- CARBON FOOTPRINT ---",
            f"Carbon per Wp: {dpp.get('carbon_per_wp','N/A')} kg CO2e/Wp",
            f"Carbon Class: {dpp.get('carbon_class','N/A')}",
            f"Renewable Manufacturing: {dpp.get('renewable_manufacturing','N/A')}",
            f"Renewable Source: {dpp.get('renewable_source','N/A')}",
            "",
            "--- MATERIALS & SUPPLY CHAIN ---",
            f"Silicon Origin: {dpp.get('silicon_origin','N/A')}",
            f"Silicon Risk: {dpp.get('silicon_risk','N/A')}",
            f"Lead Free: {dpp.get('lead_free','N/A')}",
            f"Conflict Mineral Free: {dpp.get('conflict_mineral_free','N/A')}",
            "",
            "--- SUPPLIER ETHICS ---",
            f"Supplier: {dpp.get('supplier_name','N/A')}",
            f"Ethics Score: {dpp.get('ethics_score','N/A')}/100",
            f"Forced Labour Risk: {dpp.get('forced_labour_risk','N/A')}",
            f"Third-Party Audited: {dpp.get('third_party_audited','N/A')}",
            f"Audit Standard: {dpp.get('audit_standard','N/A')}",
            "",
            "--- PERFORMANCE ---",
            f"Efficiency: {dpp.get('efficiency_pct','N/A')}%",
            f"Annual Degradation: {dpp.get('degradation_annual_pct','N/A')}%/year",
            f"Performance Warranty: {dpp.get('performance_warranty_years','N/A')} years",
            "",
            "--- END OF LIFE ---",
            f"Recyclability: {dpp.get('recyclability_pct','N/A')}%",
            f"Second Life Eligible: {dpp.get('second_life_eligible','N/A')}",
            f"EOL Value: EUR {dpp.get('eol_value_eur','N/A')}",
            "",
            "=== END DPP DATA ===",
        ]

        # Merge description into the full existing article
        current["description"] = "\n".join(lines)

        # Remove read-only fields that weclapp rejects on PUT
        for field in ["createdDate", "lastModifiedDate", "lastModifiedByUserId"]:
            current.pop(field, None)

        return self._put(f"article/id/{article_id}", current)

    def create_purchase_order(self, supplier_id, items, note=""):
        """Create a purchase order in weclapp."""
        data = {
            "supplierId": supplier_id,
            "purchaseOrderItems": items,
            "note": note
        }
        result = self._post("purchaseOrder", data)
        return result

    def test_connection(self):
        result = self._get("user/currentUser")
        user = result.get("result", {})
        return user.get("firstName", ""), user.get("email", "")
