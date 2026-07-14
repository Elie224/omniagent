"""Module Emploi (V1) : recherche d''offres et candidature automatisee.

Agents exposes :
- agent_emploi       : coordinateur
- agent_adzuna       : agregateur API Adzuna
- agent_france_travail: API officielle France Travail
- agent_themuse      : source API The Muse
- agent_cv           : generation LaTeX -> PDF
- agent_lettre       : lettre de motivation

Note conformite:
- Les agents de scraping (LinkedIn/Indeed/HelloWork/WTTJ) sont volontairement
	desactives au niveau registre/RBAC et ne font plus partie de l architecture
	active par defaut.
"""