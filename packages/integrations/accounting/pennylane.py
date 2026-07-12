"""Connecteur Pennylane (API publique)."""
import httpx

from omniagent.integrations.accounting.base import BaseAccountingConnector


class PennylaneConnector(BaseAccountingConnector):
    source = "pennylane"
    BASE_URL = "https://app.pennylane.com/api/external/v1"

    def __init__(self, api_key: str):
        self.headers = {"Authorization": f"Bearer {api_key}"}

    async def get_overdue_invoices(self) -> list[dict]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.BASE_URL}/customer_invoices",
                headers=self.headers,
                params={"status": "overdue"},
            )
            r.raise_for_status()
            return [self._normalize(i) for i in r.json().get("invoices", [])]

    async def mark_as_paid(self, invoice_id: str) -> bool:
        async with httpx.AsyncClient() as client:
            r = await client.patch(
                f"{self.BASE_URL}/customer_invoices/{invoice_id}",
                headers=self.headers,
                json={"status": "paid"},
            )
            return r.status_code == 200

    def _normalize(self, raw: dict) -> dict:
        return {
            "id": str(raw.get("id")),
            "number": raw.get("invoice_number", "?"),
            "amount_due": float(raw.get("remaining_amount", 0)),
            "due_date": raw.get("deadline"),
            "debtor_id": str(raw.get("customer", {}).get("id", "")),
            "debtor_name": raw.get("customer", {}).get("name", ""),
            "debtor_email": raw.get("customer", {}).get("email"),
            "debtor_phone": raw.get("customer", {}).get("phone"),
            "source": self.source,
        }