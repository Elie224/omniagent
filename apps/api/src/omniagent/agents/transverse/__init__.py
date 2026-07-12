"""Agents transverses (non lies a un module metier).

Ces 5 agents sont partages par Emploi, Marketing et Recouvrement :
- memory_agent       : gere les 4 niveaux de memoire
- knowledge_agent    : recherche semantique dans CV / offres / factures
- monitoring_agent   : detecte les erreurs et relance les taches
- planning_agent     : planifie les taches futures (Celery beat)
- notification_agent : envoie des notifications multi-canal
"""