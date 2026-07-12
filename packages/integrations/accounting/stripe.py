"""Connecteur Stripe (factures impayees)."""
import httpx

from omniagent.integrations.accounting.base import BaseAccountingConnector


class StripeConnector(BaseAccountingConnector):
    source = "stripe"
    BASE_URL = "https://api.stripe.com/v1"

    def __init__(self, secret_key: str):
        self.headers = {"Authorization": f"Bearer {secret_key}"}

    async def get_overdue_invoices(self) -> list[dict]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.BASE_URL}/invoices",
                headers=self.headers,
                params={"status": "open"},
            )
            r.raise_for_status()
            out = []
            for inv in r.json().get("data", []):
                if not inv.get("paid", False):
                    out.append(self._normalize(inv))
            return out

    async def mark_as_paid(self, invoice_id: str) -> bool:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.BASE_URL}/invoices/{invoice_id}/pay",
                headers=self.headers,
            )
            return r.status_code == 200

    def _normalize(self, raw: dict) -> dict:
        customer = raw.get("customer", {}) or {}
        return {
            "id": raw.get("id", ""),
            "number": raw.get("number", "?"),
            "amount_due": float(raw.get("amount_due", 0)) / 100,
            "due_date": raw.get("due_date"),
            "debtor_id": customer.get("id", customer if isinstance(customer, str) else ""),
            "debtor_name": customer.get("name", "") if isinstance(customer, dict) else "",
            "debtor_email": customer.get("email") if isinstance(customer, dict) else None,
            "source": self.source,
        }