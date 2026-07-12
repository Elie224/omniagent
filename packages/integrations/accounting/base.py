"""Interface commune des connecteurs comptables."""
from abc import ABC, abstractmethod


class BaseAccountingConnector(ABC):
    source: str = "unknown"

    @abstractmethod
    async def get_overdue_invoices(self) -> list[dict]: ...

    @abstractmethod
    async def mark_as_paid(self, invoice_id: str) -> bool: ...