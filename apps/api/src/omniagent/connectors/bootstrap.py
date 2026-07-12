"""Bootstrap : enregistre les connecteurs dans le registre au demarrage.

Vague B (focus Emploi) : seuls les connecteurs plateformes (recherche d'offres,
recherche emails RH) et storage sont enregistres. Les connecteurs comptabilite
et messagerie ont ete retires car lies a d'autres modules (recouvrement,
marketing) desactives en Vague B.
"""
from omniagent.core.config import settings
from omniagent.core.registry.connector_registry import ConnectorSpec
from omniagent.connectors.manager import connector_manager
from omniagent.connectors.plateformes.hunter import HunterConnector
from omniagent.connectors.plateformes.adzuna import AdzunaConnector
from omniagent.connectors.plateformes.france_travail import FranceTravailConnector
from omniagent.connectors.plateformes.wttj import WTTJConnector
from omniagent.connectors.plateformes.apec import APECConnector
from omniagent.connectors.plateformes.themuse import TheMuseConnector
from omniagent.connectors.storage.local import LocalStorageConnector


def register_all() -> None:
    """Appele au demarrage de l app."""
    specs = [
        # Recherche d offres d emploi (Vague B : 6 plateformes + Hunter pour les emails RH)
        ConnectorSpec("hunter", "plateformes",
                      lambda: HunterConnector(settings.hunter_api_key),
                      requires_env=["hunter_api_key"],
                      description="Hunter.io recherche emails RH"),
        ConnectorSpec("adzuna", "plateformes",
                      lambda: AdzunaConnector(),
                      requires_env=["adzuna_api_key", "adzuna_app_id"],
                      description="Adzuna agregateur offres FR+UK+US"),
        ConnectorSpec("france_travail", "plateformes",
                      lambda: FranceTravailConnector(),
                      requires_env=["ft_client_id", "ft_client_secret"],
                      description="France Travail (ex Pole Emploi) API officielle"),
        ConnectorSpec("wttj", "plateformes",
                      lambda: WTTJConnector(),
                      requires_env=[],
                      description="Welcome to the Jungle (startups FR)"),
        ConnectorSpec("apec", "plateformes",
                      lambda: APECConnector(),
                      requires_env=["apec_client_id", "apec_client_secret"],
                      description="APEC (cadres FR) - API officielle"),
        ConnectorSpec("themuse", "plateformes",
                      lambda: TheMuseConnector(),
                      requires_env=[],
                      description="The Muse (US/global tech jobs)"),

        # Stockage local (CV generes, lettres, exports)
        ConnectorSpec("local_storage", "storage",
                      lambda: LocalStorageConnector(),
                      requires_env=[],
                      description="Stockage local FS"),
    ]
    for s in specs:
        connector_manager.register(s)