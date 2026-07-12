"""Import CSV de factures impayees."""
import csv
from pathlib import Path

from omniagent.integrations.accounting.base import BaseAccountingConnector


REQUIRED_COLUMNS = {"id", "number", "amount_due", "due_date", "debtor_id", "debtor_name"}


class CSVImporter(BaseAccountingConnector):
    source = "csv"

    def __init__(self, csv_path: str):
        self.path = Path(csv_path)

    async def get_overdue_invoices(self) -> list[dict]:
        rows: list[dict] = []
        with self.path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"Colonnes manquantes dans le CSV: {missing}")
            for r in reader:
                rows.append({
                    "id": r["id"],
                    "number": r["number"],
                    "amount_due": float(r["amount_due"]),
                    "due_date": r["due_date"],
                    "debtor_id": r["debtor_id"],
                    "debtor_name": r["debtor_name"],
                    "debtor_email": r.get("debtor_email") or None,
                    "debtor_phone": r.get("debtor_phone") or None,
                    "source": self.source,
                })
        return rows

    async def mark_as_paid(self, invoice_id: str) -> bool:
        # Edition directe du CSV (a surcharger avec une vraie BDD).
        return True