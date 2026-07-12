# Architecture OmniAgent V2

> Documentation complete dans `docs/FEUILLE_DE_ROUTE.md`.

## Cles du refactoring V2

1. **BrowserService** : seule couche qui parle a Playwright
2. **ConnectorManager** : seul point d''entree pour les API tierces
3. **AgentManager** : gere le cycle de vie des 14 agents
4. **MemoryStack** : 4 memoires (session / user / vector / domain)
5. **ModelRouter** : selection du LLM selon tache + quotas
6. **Orchestrateur decompose** : Planner / Router / Graph LangGraph
7. **RBAC** : 4 roles, permissions par module/agent
8. **Observabilite** : tracer / metrics / audit log des le core
9. **API versionnee** : `/api/v1/...`
10. **Modules desactivables** : `active_modules` dans config