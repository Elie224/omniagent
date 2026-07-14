// Centralisation des URLs API cote frontend.
//
// Convention de routage (voir apps/web/next.config.js) :
//   - Le rewrite Next `/api/:path*` strip le premier `/api` et forwarde `:path*` au backend.
//   - Le backend FastAPI est monte sur `/api/v1/...` (apps/api/src/omniagent/api/v1/router.py)
//     ET sur `/orchestrator/...` (apps/api/src/omniagent/main.py) au niveau root.
//   - Donc, pour atteindre un endpoint backend `X`, le frontend doit appeler `/api/X`
//     (le 1er `/api` est absorbe par le rewrite).
//
// Toute nouvelle page doit importer depuis ce fichier plutot que d hardcoder des URLs.
//
// Vague B : focus Emploi. Les URLs marketing et recouvrement ont ete retirees.

export const API = {
  employment: {
    // Recherche directe (offres brutes via /api/v1/employment/search)
    search: "/api/api/v1/employment/search",
    // Workflow complet via l'orchestrateur V3 (point d entree canonique).
    // Note: le rewrite Next strip `/api`, donc `/api/orchestrator/run` est transmis au backend sur `/orchestrator/run`.
    workflow: "/api/orchestrator/run",
    // Lecture des evenements du pipeline (par correlation_id) via EventStore.
    events: (correlationId: string) =>
      `/api/api/v1/shared/events/query?correlation_id=${encodeURIComponent(correlationId)}`,
    business: "/api/api/v1/shared/business-dashboard",
  },
  shared: {
    connectorHealth: (source: string) => `/api/api/v1/shared/connectors/${encodeURIComponent(source)}/health`,
  },
  // Profil candidat (Vague B) : sert au matching CV <-> offres.
  profile: {
    get:        "/api/api/v1/employment/profile",
    save:       "/api/api/v1/employment/profile",
    remove:     "/api/api/v1/employment/profile",
    summary:    "/api/api/v1/employment/profile/summary",
  },
  // Suivi des candidatures (Vague B) : CRUD sur les candidatures envoyees.
  applications: {
    list:   "/api/api/v1/employment/applications",
    create: "/api/api/v1/employment/applications",
    patch:  (id: string) => `/api/api/v1/employment/applications/${id}`,
    remove: (id: string) => `/api/api/v1/employment/applications/${id}`,
  },
  contact: {
    enrich: "/api/api/v1/employment/contact/enrich",
  },
  filteringMatching: {
    run: "/api/api/v1/employment/offers/filter-match",
  },
  missionController: {
    run: "/api/api/v1/employment/mission/run",
  },
  lettre: {
    auto: "/api/api/v1/employment/lettre/auto",
  },
  applicationSender: {
    send: "/api/api/v1/employment/application/send",
  },
  // Upload / telechargement du CV candidat (PDF, max 5 Mo)
  cv: {
    upload:   "/api/api/v1/employment/cv/upload",
    get:      "/api/api/v1/employment/cv",
    remove:   "/api/api/v1/employment/cv",
    download: "/api/api/v1/employment/cv/download",
    generate: "/api/api/v1/employment/cv/generate",
    generatedDownload: "/api/api/v1/employment/cv/generated/download",
  },
};

// En-tetes d'authentification par defaut pour le mode dev (legacy).
// En prod, remplacer par un vrai flux JWT (login -> access_token -> Bearer).
export function devAuthHeaders(role: "admin" | "recruiter" | "marketer" | "finance" | "user" = "admin") {
  return {
    "Content-Type": "application/json",
    "X-User": "demo",
    "X-Role": role,
  };
}