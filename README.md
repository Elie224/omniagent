# OmniAgent

Plateforme SaaS agentique specialisee dans la recherche d''emploi et la candidature automatisee multi-sources.

## Modules (Vague B : focus Emploi)
- **Emploi** : recherche d''offres LinkedIn / Indeed / HelloWork, matching CV / offre, generation de CV (4 templates) et lettre de motivation, validation humaine avant envoi.
- **Transverse** (partage) : memory, knowledge, monitoring, planning, notification.

> Les modules Marketing et Recouvrement ont ete retires pour permettre un focus produit sur Emploi.
> Pour reactiver un domaine futur, voir `apps/api/src/omniagent/api/v1/router.py` (feature flag via `ACTIVE_MODULES` dans `.env`).

## Stack
- Backend : Python 3.11+ / FastAPI / orchestrateur multi-policy + planner deterministe
- Frontend : Next.js 14 / Tailwind
- DB : PostgreSQL 16 + pgvector (opt-in)
- Event backbone : EventBus unifie + EventStore SQLite (opt-in) + dedupe + replay
- Observabilite : cout + business value + causal graph + replay engine
- LLM : GPT-4o + Claude Sonnet (fallback mock deterministe en dev)

## Quickstart
```bash
# Windows
scripts\bootstrap.bat
# ou PowerShell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
```

Puis :
- API  : http://localhost:8000/docs
- WEB  : http://localhost:3000/emploi

Voir [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).