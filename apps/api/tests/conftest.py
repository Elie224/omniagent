"""Fixtures pytest partagees."""
import sys
from pathlib import Path
import pytest

# Ajout du path src au sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def sample_invoice():
    return {
        "id": "inv1", "number": "F001", "debtor_id": "c1",
        "debtor_name": "ACME", "amount_due": 1500.0,
        "due_date": "2025-04-01",
    }


@pytest.fixture
def sample_offers():
    return [
        {"id": "o1", "title": "Data Scientist", "company": "ACME",
         "location": "Paris", "contract": "alternance", "url": "https://...",
         "posted_at": "2026-06-30", "description": "...", "source": "linkedin"},
        {"id": "o2", "title": "ML Engineer", "company": "DataCorp",
         "location": "Lyon", "contract": "emploi", "url": "https://...",
         "posted_at": "2026-06-29", "description": "...", "source": "indeed"},
    ]