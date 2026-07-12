"""Value Objects partages (immuables, valides a la construction).

Convention :
- frozen=True (immuable)
- __post_init__ valide (pas d etat invalide)
- comparaison par valeur (eq/hash auto via dataclass)
- factories from_* pour parser les inputs bruts (str, float, int)
- helpers ergonomiques (to_dict, to_cents, etc.)

Utilise par les modules metier (Emploi, Marketing, Recouvrement) et
eventuellement par les connecteurs tiers.
"""
from omniagent.domain.shared.money import Money, Currency
from omniagent.domain.shared.email import Email
from omniagent.domain.shared.phone import PhoneNumber
from omniagent.domain.shared.date_range import DateRange
from omniagent.domain.shared.identifier import Identifier

__all__ = [
    "Money", "Currency",
    "Email", "PhoneNumber", "DateRange", "Identifier",
]
