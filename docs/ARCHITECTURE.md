# Architecture OmniAgent

## Vue d''ensemble
OmniAgent orchestre plusieurs agents specialises par plateforme, avec une couche LLM commune.

## Modules

### 1. Emploi (LinkedIn, Indeed, HelloWork)
- Recherche d''offres selon criteres
- Scoring et tri
- Recherche contacts RH (Hunter.io, Apollo)
- Generation CV + lettre
- Envoi automatise

### 2. Marketing (Instagram, X/Twitter)
- Detection tendances par niche
- Analyse contenus viraux
- Recommandations (formats, hooks, horaires)
- Sentiment analysis

### 3. Recouvrement (WhatsApp, SMS, Email, Voice)
- Connecteurs Pennylane / Stripe / Sage / CSV
- Scoring debiteurs (priorite, ton, canal)
- Sequence de relance 60 jours
- Templates multilingues
- Conformite RGPD

## Stack
- **Backend** : Python 3.11+ / FastAPI / LangGraph
- **Frontend** : Next.js 14 / Tailwind
- **DB** : PostgreSQL 16 + pgvector
- **Queue** : Celery + Redis
- **Browser** : Playwright + stealth
- **LLM** : GPT-4o + Claude Sonnet

## Arborescence
```
omniagent/
+- apps/
|  +- api/        # FastAPI
|  +- web/        # Next.js
+- packages/
|  +- agents/     # Recouvrement, Emploi, Marketing
|  +- browser/    # Couche Playwright
|  +- integrations/
|  +- llm/
|  +- memory/
+- infrastructure/
|  +- docker/
+- docs/
+- scripts/
```

## Demarrage rapide
```bash
scripts\bootstrap.bat        # Windows
bash scripts/bootstrap.sh   # macOS / Linux
```

API : http://localhost:8000/docs
WEB : http://localhost:3000