# Feuille de route - OmniAgent (V2)

> Architecture refactoree suite a la revue du 04/07/2026 : separation des responsabilites, modules independants, observabilite, RBAC, quotas LLM.

---

## 1. Vision produit

OmniAgent est un SaaS multi-plateformes pilote par 14 agents specialises (1 orchestrateur + 13 metier), coordonnes via LangGraph, avec une architecture modulaire ou chaque module (Emploi, Marketing, Recouvrement) est independant.

**Principe directeur** : demarrer par le module Emploi, ajouter les autres progressivement.

---

## 2. Les 14 agents (correction : 14, pas 15, l''orchestrateur est separe)

| # | Agent | Module | Role |
|---|-------|--------|------|
| 0 | **Orchestrateur** | meta | Planifie, route, gere la memoire partagee |
| 1 | Agent Emploi | emploi | Coordinateur |
| 2 | Agent LinkedIn | emploi | Recherche d''offres |
| 3 | Agent Indeed | emploi | Recherche d''offres |
| 4 | Agent HelloWork | emploi | Recherche d''offres |
| 5 | Agent CV | emploi | Generation / adaptation CV |
| 6 | Agent Lettre | emploi | Lettres de motivation |
| 7 | Agent Marketing | marketing | Coordinateur |
| 8 | Agent Instagram | marketing | Contenu Instagram |
| 9 | Agent X | marketing | Contenu X |
| 10 | Agent TikTok | marketing | Scripts videos |
| 11 | Agent Recouvrement | recouvrement | Coordinateur |
| 12 | Agent Analyse Impayes | recouvrement | Scoring |
| 13 | Agent Communication | recouvrement | Messages email/SMS/WhatsApp |
| 14 | Agent Vocal | recouvrement | Scripts appels IA |

Total : **14 agents** (l''orchestrateur est l''agent #0, distinct).

---

## 3. Architecture cible (refactoree V2)

```
                   Utilisateur
                        |
                        v
              [0] Orchestrateur
              - IntentRouter
              - Planner (templates)
              - MemoryStack
                        |
       +----------------+----------------+
       |                |                |
       v                v                v
  Module Emploi    Module Marketing  Module Recouvrement
  (6 agents)       (4 agents)        (4 agents)
       |                |                |
       +------- BrowserService ---------+
       |     (abstraction Playwright)   |
       |                                |
       +------ ConnectorManager --------+
       |     (compta, messagerie, ...)  |
       |                                |
       +------ AgentManager ------------+
       |     (start, monitor, retry)    |
       |                                |
       +------ ModelRouter -------------+
       |  (OpenAI / Anthropic, quotas)  |
       |                                |
       +------ Observability -----------+
             (traces, metrics, audit)
```

### Couches transverses

- **BrowserService** : abstraction unique au-dessus de Playwright (les agents ne connaissent pas Playwright)
- **ConnectorManager** : tous les connecteurs tiers (Pennylane, Stripe, WhatsApp, Twilio, Vapi, Hunter, ...) avec cycle de vie, semaphores, healthchecks
- **AgentManager** : start / monitor / retry / cancel de tous les agents
- **MemoryStack** : 4 memoires (session, user, vector, domain)
- **ModelRouter** : selection du modele selon tache (reasoning/writing/classification/extraction) + quotas LLM par utilisateur
- **Observability** : traces (OpenTelemetry), metriques, audit log RGPD
- **RBAC** : 4 roles (admin, recruiter, marketer, finance) avec permissions par module/agent

---

## 4. Module Emploi (V1 - prioritaire)

### Agents
- **agent_emploi** (coordinateur) : lance les 3 recherches en parallele
- **agent_linkedin / agent_indeed / agent_hellowork** (specialistes) : utilisent `browser_service.SearchJobTool`
- **agent_cv** : generation LaTeX -> PDF
- **agent_lettre** : generation lettre de motivation

### Stack
- Recherche : `BrowserService` + Playwright + stealth
- Contact RH : `HunterConnector` / `ApolloConnector`
- Generation : Claude Sonnet 4.5 (writing) + GPT-4o (reasoning)
- Stockage : `LocalStorageConnector` puis S3

### Critere d''acceptation V1
- L''utilisateur cherche "alternance data Paris"
- Le systeme retourne 10+ offres scorees depuis les 3 plateformes
- Genere 1 CV adapte + 1 lettre par offre retenue
- Trouve l''email RH et envoie la candidature (dry-run par defaut)

---

## 5. Module Marketing (V2 - apres Emploi)

### Agents
- **agent_marketing** (coordinateur) : plan editorial
- **agent_instagram / agent_x / agent_tiktok** (specialistes) : generation de contenu

### Stack
- Idees : Claude Sonnet 4.5
- Generation visuels : Canva API (V2)
- Publication : Buffer / Make (V3)

---

## 6. Module Recouvrement (V3)

### Agents
- **agent_recouvrement** (coordinateur) : plan de relance 60j
- **agent_analyse_impayes** : scoring composite (age + montant + historique)
- **agent_communication** : generation messages multicanal
- **agent_vocal** : scripts Vapi/Retell

### Stack
- Factures : Pennylane / Stripe / CSV (via `ConnectorManager`)
- Envoi : WhatsApp Business / Twilio / SendGrid (via `ConnectorManager`)
- Vocal : Vapi.ai / Retell (via `ConnectorManager`)

---

## 7. Phases revisees

### Phase 0 - Socle (FAIT ✅)
- [x] Monorepo + structure V2 (apps/, packages/, core/, agents/, connectors/)
- [x] Couche core : config, memory multi-niveaux, model router, RBAC, observability
- [x] BrowserService abstrait
- [x] ConnectorManager + 9 connecteurs
- [x] AgentManager (start/monitor/retry)
- [x] Orchestrateur decompose (Router + Planner + Graph)
- [x] 14 agents implementes (stubs pour les specialistes en V1)
- [x] Tests unitaires + integration + workflows
- [x] API v1 avec versionnage

### Phase 1 - Module Emploi V1 (EN COURS, 6 sem.)
- [ ] Brancher Playwright dans `BrowserService`
- [ ] Implementer `SearchJobTool._parse` avec extraction LLM
- [ ] Implementer `CV` (LaTeX -> PDF reellement compile)
- [ ] Implementer `Lettre` avec personalisation LLM reelle
- [ ] Integrer Hunter.io pour emails RH
- [ ] Auth (Clerk) + gestion utilisateur
- [ ] Dashboard Emploi
- [ ] Test E2E Playwright

### Phase 2 - Module Recouvrement V1 (6 sem.)
- [ ] Connecteurs reels (Pennylane, Stripe)
- [ ] WhatsApp Business integration
- [ ] Templates enrichis + variations par secteur
- [ ] Dashboard recouvrement (KPIs, taux de recuperation)
- [ ] Opt-in RGPD + preuve de consentement

### Phase 3 - Module Marketing V1 (4 sem.)
- [ ] Recherche tendances (scraping public)
- [ ] Generation de contenu (Instagram, X, TikTok)
- [ ] Planification publication
- [ ] Dashboard marketing

### Phase 4 - Production (4 sem.)
- [ ] CI/CD GitHub Actions
- [ ] Tests E2E (Playwright + HTTP)
- [ ] Deploiement Railway / Fly.io
- [ ] Monitoring (Sentry + LangSmith)
- [ ] Billing Stripe (4 plans)

---

## 8. Variables d''environnement mises a jour

```bash
# Core
APP_NAME=OmniAgent
ENV=development
DATABASE_URL=postgresql+asyncpg://omniagent:omniagent@localhost:5432/omniagent
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=...

# LLM
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
LANGSMITH_API_KEY=lsv2-...
MONTHLY_LLM_QUOTA_USD=5.0

# Modules actifs (modularite)
ACTIVE_MODULES=["emploi", "marketing", "recouvrement"]

# Connecteurs Emploi
HUNTER_API_KEY=...

# Connecteurs Recouvrement
PENNYLANE_API_KEY=...
STRIPE_SECRET_KEY=...
WHATSAPP_PHONE_ID=...
WHATSAPP_TOKEN=...
SENDGRID_API_KEY=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
```

---

## 9. Definition of Done (par agent)

Un agent est considere "shippe" quand :
1. Code ecrit + tests unitaires > 80% coverage
2. Integre au registre + visible dans `/api/v1/modules`
3. Route API exposee + documentee dans OpenAPI
4. Au moins un connecteur reel branche (ou mock documente)
5. Logs structures emis + span dans tracer
6. Gestion d''erreurs explicite (retry via AgentManager)
7. Permissions RBAC verifiees
8. Quota LLM respecte
9. Deploye en staging

---

## 10. Risques et mitigations (mis a jour)

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Trop de fonctionnalites | Eleve | Demarrer par Emploi uniquement, modules desactivables via `active_modules` |
| Scraping casse par MAJ plateformes | Eleve | BrowserService + tools haut niveau + extension Chrome en repli |
| Couplage Playwright partout | Moyen | BrowserService abstrait, changeable sans toucher aux agents |
| LangGraph trop charge | Moyen | Decomposition Planner / Router / Memory / AgentManager |
| Memoire mal geree | Moyen | 4 memoires specialisees (session / user / vector / domain) |
| Couts LLM explosifs | Moyen | ModelRouter + quotas par utilisateur + cache semantique |
| Pas de permissions | Moyen | RBAC 4 roles des le depart |
| Pas d''observabilite | Moyen | Tracer + metrics + audit log integres au core |
| Pas de tests | Eleve | Tests unitaires + integration + workflows des le debut |
| Modules trop couples | Moyen | `active_modules` permet d''isoler/desactiver chaque module |

---

## 11. Comment lancer les tests

```bash
cd C:\Users\KOURO\omniagent
pytest apps/api/tests/ -v
```

Resultat attendu : ~25 tests passants.

## 12. Comment lancer l''API

```bash
cd C:\Users\KOURO\omniagent
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1

cd apps\api
.venv\Scripts\Activate.ps1
uvicorn omniagent.main:app --reload
```

API : http://localhost:8000/docs
Modules : http://localhost:8000/modules
Metriques : http://localhost:8000/metrics