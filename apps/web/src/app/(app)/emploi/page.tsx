"use client";

import Link from "next/link";
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  Briefcase, MapPin, Sparkles, CheckCircle2, Circle, XCircle, Loader2,
  FileText, Zap, Building2, AlertTriangle, ShieldCheck,
  Linkedin, Globe, Filter, ExternalLink,
} from "lucide-react";
import { API, devAuthHeaders } from "@/lib/api";
import { toSafeExternalUrl } from "@/lib/urlSafety";
import {
  notifyCvGeneratedPdf,
  notifyCvGeneratedTexOnly,
  notifyCvGenerateError,
  notifyGeneratedCvDownloadStarted,
  notifyGeneratedCvDownloadError,
} from "@/lib/cvToasts";

type StepStatus = "pending" | "running" | "done" | "failed" | "skipped";

interface PipelineStep {
  name: string;
  label: string;
  status: StepStatus;
  detail?: string;
}

interface Offer {
  offer_id?: string;
  id?: string;
  title: string;
  company: string;
  location?: string;
  url?: string;
  description?: string;
  source?: string;
  posted_at?: string;
  contract?: string;
  match_score?: number;
  score?: number;
}

interface WorkflowResult {
  status?: string;
  output?: any;
  offers?: Offer[];
}

interface ConnectorHealth {
  source: string;
  available: boolean;
  configured: boolean;
  mode?: string;
  token_ok?: boolean;
  token_cached?: boolean;
  token_expires_in_s?: number;
}

interface OrchestratorResponse {
  intent?: string;
  plan?: string;
  plan_name?: string;
  plan_version?: string;
  policy?: string;
  status?: string;
  results?: Record<string, WorkflowResult>;
}

interface OfferContactEnrichment {
  company?: string;
  company_domain?: string;
  emails?: string[];
  phones?: string[];
  primary_email?: string | null;
  primary_phone?: string | null;
  scanned_urls?: string[];
  sources?: string[];
}

interface OfferLettreAuto {
  required?: boolean;
  reason?: string;
  contract?: string;
  letter?: {
    subject?: string;
    body?: string;
  } | null;
}

interface OfferApplicationSend {
  sent?: boolean;
  mode?: string;
  recipient?: string | null;
  subject?: string | null;
  attachment_used?: boolean;
  error?: string;
}

interface OfferValidationState {
  offerApproved?: boolean;
  cvApproved?: boolean;
  contactApproved?: boolean;
}

interface TrackedApplication {
  application_id: string;
  company: string;
  position: string;
  status: string;
  sent_at?: string;
  email?: string;
  source?: string;
}

const SOURCES: { id: string; label: string; disabled?: boolean; badge?: string }[] = [
  { id: "adzuna",          label: "Adzuna",            badge: "Premium" },
  { id: "france_travail",  label: "France Travail",    badge: "Officiel" },
];

const RADII: { id: string; label: string; km?: number }[] = [
  { id: "city",   label: "Ville uniquement" },
  { id: "20km",   label: "20 km",     km: 20 },
  { id: "50km",   label: "50 km",     km: 50 },
  { id: "france", label: "Toute la France" },
];

const RECENCY: { id: string; label: string; hours?: number }[] = [
  { id: "1h",  label: "1 h",   hours: 1 },
  { id: "2h",  label: "2 h",   hours: 2 },
  { id: "6h",  label: "6 h",   hours: 6 },
  { id: "24h", label: "24 h",  hours: 24 },
  { id: "48h", label: "48 h",  hours: 48 },
  { id: "3j",  label: "3 j",   hours: 72 },
  { id: "7j",  label: "7 j",   hours: 168 },
  { id: "30j", label: "30 j",  hours: 720 },
];

const CONTRACTS: { id: "all" | "emploi" | "alternance" | "stage"; label: string }[] = [
  { id: "all", label: "Tous" },
  { id: "emploi", label: "Emploi" },
  { id: "alternance", label: "Alternance" },
  { id: "stage", label: "Stage" },
];

const PIPELINE_TEMPLATE: PipelineStep[] = [
  { name: "intent",      label: "Analyse de la requete",        status: "pending" },
  { name: "discovery",   label: "Recherche des offres",     status: "pending" },
  { name: "filter",      label: "Filtrage",                status: "pending" },
  { name: "enrichment",  label: "Enrichissement des contacts", status: "pending" },
  { name: "matching",    label: "Adequation profil / offre",     status: "pending" },
  { name: "generation",  label: "Generation du CV adapte",           status: "pending" },
  { name: "application", label: "Envoi de la candidature",             status: "pending" },
];

const DEFAULT_FORM = {
  query: "Data Scientist IA",
  location: "Paris",
  radius: "city",
  contract: "all" as "all" | "emploi" | "alternance" | "stage",
  recency: "24h",
  sources: ["france_travail", "adzuna"] as string[],
  max: 20,
  scoreThreshold: 0.45,
};

function chipClass(active: boolean, disabled?: boolean): string {
  const base = "px-3 py-1.5 text-sm rounded-full border transition select-none";
  if (disabled) return base + " border-slate-200 bg-slate-50 text-slate-400 cursor-not-allowed";
  if (active)   return base + " border-indigo-500 bg-indigo-50 text-indigo-700 font-medium";
  return            base + " border-slate-200 bg-white text-slate-700 hover:border-slate-300";
}

function statusBadge(status: StepStatus) {
  if (status === "done")    return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
  if (status === "running") return <Loader2 className="w-4 h-4 text-indigo-500 animate-spin" />;
  if (status === "failed")  return <XCircle className="w-4 h-4 text-rose-500" />;
  return <Circle className="w-4 h-4 text-slate-300" />;
}

function PendingApplicationNotice(props: {
  pending: { company: string; position: string } | null;
  onDismiss: () => void;
}) {
  if (!props.pending) return null;
  const p = props.pending;
  return (
    <section className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex items-center gap-3">
      <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-emerald-800">
          Candidature ajoutee a ton suivi : : {p.position} chez {p.company}
        </div>
        <div className="text-xs text-emerald-700 mt-0.5">
          Suis son statut, ajoute des notes ou prepare une relance depuis la page, ajouter des notes ou la mettre a jour depuis la page Candidatures.
        </div>
      </div>
      <Link href="/candidatures" className="shrink-0 inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-500">
        Voir le suivi
      </Link>
      <button type="button" onClick={props.onDismiss} className="shrink-0 text-emerald-700 hover:text-emerald-900 text-xs">
        OK
      </button>
    </section>
  );
}

function matchColor(score: number): string {
  if (score >= 0.8) return "text-emerald-600";
  if (score >= 0.5) return "text-amber-600";
  return "text-slate-500";
}

function sourceBadge(source?: string) {
  const s = (source || "").toLowerCase();
  if (s.includes("linkedin")) return <Linkedin className="w-3.5 h-3.5" />;
  if (s.includes("adzuna")) return <span className="inline-block w-2 h-2 rounded-full bg-amber-500" title="Adzuna" />;
  if (s.includes("france_travail")) return <span className="inline-block w-2 h-2 rounded-full bg-blue-600" title="France Travail" />;
  if (s.includes("wttj") || s.includes("jungle")) return <span className="inline-block w-2 h-2 rounded-full bg-emerald-500" title="Welcome to the Jungle" />;
  if (s.includes("themuse") || s.includes("muse")) return <span className="inline-block w-2 h-2 rounded-full bg-pink-500" title="The Muse" />;
  return <Globe className="w-3.5 h-3.5" />;
}

function sourceLabel(source?: string) {
  const s = (source || "").toLowerCase();
  if (s.includes("adzuna")) return "Adzuna";
  if (s.includes("france_travail")) return "France Travail";
  if (s.includes("wttj")) return "WTTJ";
  if (s.includes("themuse")) return "The Muse";
  if (s.includes("linkedin")) return "LinkedIn";
  if (s.includes("indeed")) return "Indeed";
  if (s.includes("hellowork")) return "HelloWork";
  return source || "-";
}

function extractOffers(payload: OrchestratorResponse | null): Offer[] {
  if (!payload || !payload.results) return [];
  const out: Offer[] = [];
  for (const r of Object.values(payload.results)) {
    const rr = r as any;
    const candidates = [
      rr?.offers,
      rr?.output?.offers,
      rr?.output?.result?.offers,
      rr?.output?.data?.offers,
      rr?.result?.offers,
    ];
    for (const c of candidates) {
      if (Array.isArray(c)) out.push(...(c as Offer[]));
    }
  }
  const seen = new Set<string>();
  const dedup: Offer[] = [];
  const norm = (v?: string) => (v || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, " ").trim();
  for (const o of out) {
    const key = [norm(o.title), norm(o.company), norm(o.location)].join("|");
    if (seen.has(key)) continue;
    seen.add(key);
    dedup.push(o);
  }
  return dedup;
}

function getFranceTravailResultMode(offers: Offer[]): "live" | "mock" | null {
  const franceTravailOffers = offers.filter((offer) => (offer.source || "").toLowerCase().includes("france_travail"));
  if (franceTravailOffers.length === 0) return null;
  const allMock = franceTravailOffers.every((offer) => {
    const identifier = offer.offer_id || offer.id || "";
    return identifier.startsWith("FT-MOCK-");
  });
  return allMock ? "mock" : "live";
}

function connectorTone(health: ConnectorHealth | null): string {
  if (!health) return "border-slate-200 bg-slate-50 text-slate-600";
  if (health.token_ok) return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (health.configured) return "border-amber-200 bg-amber-50 text-amber-800";
  return "border-slate-200 bg-slate-50 text-slate-600";
}

export default function EmploiPage() {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [steps, setSteps] = useState<PipelineStep[]>(PIPELINE_TEMPLATE);
  const [running, setRunning] = useState(false);
  const [correlationId, setCorrelationId] = useState<string | null>(null);
  const [orchestrator, setOrchestrator] = useState<OrchestratorResponse | null>(null);
  const [offers, setOffers] = useState<Offer[]>([]);
  const [franceTravailHealth, setFranceTravailHealth] = useState<ConnectorHealth | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Offer | null>(null);
  const [templateChoice, setTemplateChoice] = useState<string>("moderne");
  const [approved, setApproved] = useState(false);
  const [counters, setCounters] = useState({ found: 0, kept: 0, cv: 0, sent: 0, pending: 0 });
  const [pendingApplication, setPendingApplication] = useState<{ company: string; position: string; location?: string; url?: string; source?: string } | null>(null);
  const [cvGenerating, setCvGenerating] = useState(false);
  const [cvDownloading, setCvDownloading] = useState(false);
  const [contactLoadingByOffer, setContactLoadingByOffer] = useState<Record<string, boolean>>({});
  const [contactsByOffer, setContactsByOffer] = useState<Record<string, OfferContactEnrichment>>({});
  const [contactErrorByOffer, setContactErrorByOffer] = useState<Record<string, string>>({});
  const [lettreLoadingByOffer, setLettreLoadingByOffer] = useState<Record<string, boolean>>({});
  const [lettreByOffer, setLettreByOffer] = useState<Record<string, OfferLettreAuto>>({});
  const [lettreErrorByOffer, setLettreErrorByOffer] = useState<Record<string, string>>({});
  const [sendLoadingByOffer, setSendLoadingByOffer] = useState<Record<string, boolean>>({});
  const [sendByOffer, setSendByOffer] = useState<Record<string, OfferApplicationSend>>({});
  const [sendErrorByOffer, setSendErrorByOffer] = useState<Record<string, string>>({});
  const [validationByOffer, setValidationByOffer] = useState<Record<string, OfferValidationState>>({});
  const [confirmPhraseByOffer, setConfirmPhraseByOffer] = useState<Record<string, string>>({});
  const [applications, setApplications] = useState<TrackedApplication[]>([]);
  const [applicationsLoading, setApplicationsLoading] = useState(false);
  const cvBusy = cvGenerating || cvDownloading;
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const refreshFranceTravailHealth = useCallback(async () => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 4000);
    try {
      const resp = await fetch(API.shared.connectorHealth("france_travail"), {
        method: "GET",
        headers: devAuthHeaders("admin"),
        signal: controller.signal,
      });
      if (!resp.ok) return;
      const data: ConnectorHealth = await resp.json();
      setFranceTravailHealth(data);
    } catch {
      // best effort only
    } finally {
      window.clearTimeout(timeoutId);
    }
  }, []);

  useEffect(() => {
    refreshFranceTravailHealth();
  }, [refreshFranceTravailHealth]);

  const refreshApplications = useCallback(async () => {
    setApplicationsLoading(true);
    try {
      const r = await fetch(API.applications.list, {
        method: "GET",
        headers: devAuthHeaders("user"),
      });
      const data = await r.json().catch(() => ({}));
      if (r.ok && Array.isArray(data?.applications)) {
        setApplications(data.applications as TrackedApplication[]);
      }
    } finally {
      setApplicationsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshApplications();
  }, [refreshApplications]);

  function toggleSource(id: string, disabled?: boolean) {
    if (disabled) return;
    setForm((f) => ({
      ...f,
      sources: f.sources.includes(id)
        ? f.sources.filter((s) => s !== id)
        : [...f.sources, id],
    }));
  }

  const matchedOffers = useMemo(() => {
    const sorted = [...offers].sort((a, b) => {
      const sa = a.match_score ?? a.score ?? 0;
      const sb = b.match_score ?? b.score ?? 0;
      return sb - sa;
    });

    const selectedSources = new Set(form.sources.map((s) => s.toLowerCase()));
    const sourceFiltered = selectedSources.size > 0
      ? sorted.filter((o) => selectedSources.has((o.source || "").toLowerCase()))
      : sorted;

    const activeBuckets = new Map<string, Offer[]>();
    for (const o of sourceFiltered) {
      const src = (o.source || "").toLowerCase();
      if (!src || !selectedSources.has(src)) continue;
      if (!activeBuckets.has(src)) activeBuckets.set(src, []);
      activeBuckets.get(src)!.push(o);
    }

    // If only one source is selected or one bucket has results, keep score sort.
    const nonEmptyBuckets = [...activeBuckets.values()].filter((b) => b.length > 0);
    if (nonEmptyBuckets.length <= 1) return sourceFiltered.slice(0, form.max);

    // Round-robin by source so the UI shows selected sources simultaneously.
    const order = form.sources.map((s) => s.toLowerCase()).filter((s) => activeBuckets.has(s));
    const mixed: Offer[] = [];
    let remaining = nonEmptyBuckets.reduce((acc, b) => acc + b.length, 0);
    while (remaining > 0) {
      for (const src of order) {
        const bucket = activeBuckets.get(src);
        if (!bucket || bucket.length === 0) continue;
        mixed.push(bucket.shift()!);
        remaining -= 1;
      }
    }
    return mixed.slice(0, form.max);
  }, [offers, form.sources, form.max]);

  const onLaunch = useCallback(async () => {
    if (running) return;
    setRunning(true);
    setGlobalError(null);
    setOrchestrator(null);
    setOffers([]);
    setSelected(null);
    setApproved(false);
    setSteps(PIPELINE_TEMPLATE.map((s) => ({ ...s, status: "pending" as StepStatus, detail: undefined })));

    const radiusLabel = RADII.find((r) => r.id === form.radius)?.label || form.radius;
    const recencyHours = RECENCY.find((r) => r.id === form.recency)?.hours ?? 24;
    const sourcesLabel = form.sources.length > 0 ? form.sources.join("/") : "france_travail";
    const userMessage = "Trouver " + form.query + " a " + form.location +
      " (rayon " + radiusLabel + ", publie dans les " + recencyHours + "h, sources " + sourcesLabel +
      ", contrat " + form.contract + ", max " + form.max + ") et lancer une candidature";

    const newCorr = "emp-" + Date.now() + "-" + Math.floor(Math.random() * 1000);
    setCorrelationId(newCorr);

    try {
      setSteps((s) => s.map((x) => x.name === "intent" ? { ...x, status: "running" } : x));

      const resp = await fetch(API.employment.workflow, {
        method: "POST",
        headers: devAuthHeaders("admin"),
        body: JSON.stringify({
          message: userMessage,
          max_results: form.max,
          recency_hours: recencyHours,
          context: {
            query: form.query,
            location: form.location,
            radius: form.radius,
            recency_hours: recencyHours,
            sources: form.sources,
            max_results: form.max,
            correlation_id: newCorr,
          },
        }),
      });

      if (!resp.ok) {
        const text = await resp.text().catch(() => "");
        throw new Error("HTTP " + resp.status + (text ? " - " + text.slice(0, 200) : ""));
      }
      const data: OrchestratorResponse = await resp.json();
      setOrchestrator(data);

      const extracted = extractOffers(data);
      // Chaine manquante produit: filtrage mission + matching profil avant affichage.
      let filteredOffers = extracted;
      try {
        const fmResp = await fetch(API.filteringMatching.run, {
          method: "POST",
          headers: devAuthHeaders("user"),
          body: JSON.stringify({
            offers: extracted,
            city: form.location,
            radius: form.radius,
            contract: form.contract,
            recency_hours: recencyHours,
            score_threshold: form.scoreThreshold,
            max_results: form.max,
          }),
        });
        const fmData = await fmResp.json().catch(() => ({}));
        if (fmResp.ok && Array.isArray(fmData?.offers)) {
          filteredOffers = fmData.offers as Offer[];
        }
      } catch {
        // Fallback best-effort : on garde la liste brute si l agent est indisponible.
      }

      setOffers(filteredOffers);
      void refreshFranceTravailHealth();

      const stepMap: Record<string, StepStatus> = {};
      if (data.results) {
        for (const [k, v] of Object.entries(data.results)) {
          stepMap[k] = (v?.status === "success" ? "done" : "failed");
        }
      }
      setSteps((cur) => cur.map((s) => ({
        ...s,
        status: stepMap[s.name] ?? (data.status === "completed" ? "done" : "failed"),
        detail: data.results?.[s.name]?.status,
      })));

      setCounters((c) => ({ ...c, found: extracted.length, kept: Math.min(filteredOffers.length, form.max) }));
    } catch (err: any) {
      setGlobalError(err?.message || String(err));
      setSteps((cur) => cur.map((s) => s.status === "running" ? { ...s, status: "failed", detail: err?.message } : s));
    } finally {
      setRunning(false);
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    }
  }, [form, running, refreshFranceTravailHealth]);

  const franceTravailResultMode = useMemo(() => getFranceTravailResultMode(matchedOffers), [matchedOffers]);

  function onGenerateCV(o: Offer) {
    setSelected(o);
    setApproved(false);
  }

  function offerKey(o: Offer): string {
    return [o.offer_id || o.id || "", o.title || "", o.company || "", o.url || ""].join("|");
  }

  async function onFindContact(o: Offer) {
    const key = offerKey(o);
    setContactErrorByOffer((s) => ({ ...s, [key]: "" }));
    setContactLoadingByOffer((s) => ({ ...s, [key]: true }));
    try {
      const v = validationByOffer[key] || {};
      if (!v.contactApproved) {
        throw new Error("Validation legale requise: active d'abord 'Contact RH valide'.");
      }
      const r = await fetch(API.contact.enrich, {
        method: "POST",
        headers: devAuthHeaders("user"),
        body: JSON.stringify({
          offer: {
            title: o.title || "",
            company: o.company || "",
            location: o.location || "",
            url: o.url || "",
            description: o.description || "",
            source: o.source || "",
            contract: o.contract || "",
          },
          company: o.company || "",
          max_pages: 5,
          user_confirmation: true,
          legal_basis: "legitimate_interest",
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        throw new Error(data?.detail || ("HTTP " + r.status));
      }
      const enriched: OfferContactEnrichment = {
        company: data.company,
        company_domain: data.company_domain,
        emails: data.emails || [],
        phones: data.phones || [],
        primary_email: data.primary_email,
        primary_phone: data.primary_phone,
        scanned_urls: data.scanned_urls || [],
        sources: data.sources || [],
      };
      setContactsByOffer((s) => ({ ...s, [key]: enriched }));
    } catch (err: any) {
      setContactErrorByOffer((s) => ({ ...s, [key]: err?.message || String(err) }));
    } finally {
      setContactLoadingByOffer((s) => ({ ...s, [key]: false }));
    }
  }

  async function onGenerateLettreIfRequired(o: Offer) {
    const key = offerKey(o);
    setLettreErrorByOffer((s) => ({ ...s, [key]: "" }));
    setLettreLoadingByOffer((s) => ({ ...s, [key]: true }));
    try {
      const r = await fetch(API.lettre.auto, {
        method: "POST",
        headers: devAuthHeaders("user"),
        body: JSON.stringify({
          offer: {
            offer_id: o.offer_id || o.id || "",
            title: o.title || "",
            company: o.company || "",
            location: o.location || "",
            url: o.url || "",
            description: o.description || "",
            source: o.source || "",
            contract: o.contract || "",
          },
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        throw new Error(data?.detail || ("HTTP " + r.status));
      }
      const generated: OfferLettreAuto = {
        required: data.required,
        reason: data.reason,
        contract: data.contract,
        letter: data.letter || null,
      };
      setLettreByOffer((s) => ({ ...s, [key]: generated }));
    } catch (err: any) {
      setLettreErrorByOffer((s) => ({ ...s, [key]: err?.message || String(err) }));
    } finally {
      setLettreLoadingByOffer((s) => ({ ...s, [key]: false }));
    }
  }

  async function onSendApplication(o: Offer) {
    const key = offerKey(o);
    setSendErrorByOffer((s) => ({ ...s, [key]: "" }));
    setSendLoadingByOffer((s) => ({ ...s, [key]: true }));
    try {
      const v = validationByOffer[key] || {};
      if (!v.offerApproved || !v.cvApproved || !v.contactApproved) {
        throw new Error("Validation incomplete: confirme offre, CV et contact RH avant l'envoi.");
      }
      const phrase = (confirmPhraseByOffer[key] || "").trim();
      if (phrase.toUpperCase() !== "JE CONFIRME L ENVOI") {
        throw new Error("Confirmation explicite requise: ecris exactement JE CONFIRME L ENVOI.");
      }
      const contact = contactsByOffer[key];
      const recruiterEmail = contact?.primary_email || (contact?.emails && contact.emails[0]) || "";
      if (!recruiterEmail) {
        throw new Error("Aucun email recruteur. Clique d'abord sur Trouver contact RH.");
      }
      const lettre = lettreByOffer[key]?.letter || null;
      const r = await fetch(API.applicationSender.send, {
        method: "POST",
        headers: devAuthHeaders("user"),
        body: JSON.stringify({
          recruiter_email: recruiterEmail,
          offer: {
            offer_id: o.offer_id || o.id || "",
            title: o.title || "",
            company: o.company || "",
            location: o.location || "",
            url: o.url || "",
            description: o.description || "",
            source: o.source || "",
            contract: o.contract || "",
          },
          letter: lettre || {},
          confirm_phrase: phrase,
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        throw new Error(data?.detail || ("HTTP " + r.status));
      }
      const sent: OfferApplicationSend = {
        sent: data.sent,
        mode: data.mode,
        recipient: data.recipient,
        subject: data.subject,
        attachment_used: data.attachment_used,
        error: data.error,
      };
      setSendByOffer((s) => ({ ...s, [key]: sent }));
      if (sent.sent) {
        setCounters((c) => ({ ...c, sent: c.sent + 1 }));
      }
      void refreshApplications();
    } catch (err: any) {
      setSendErrorByOffer((s) => ({ ...s, [key]: err?.message || String(err) }));
    } finally {
      setSendLoadingByOffer((s) => ({ ...s, [key]: false }));
    }
  }

  async function onGenerateSelectedCV() {
    if (!selected || cvGenerating) return;
    setCvGenerating(true);
    try {
      const r = await fetch(API.cv.generate, {
        method: "POST",
        headers: devAuthHeaders("user"),
        body: JSON.stringify({
          template: templateChoice,
          offer: {
            offer_id: selected.offer_id || selected.id || "",
            title: selected.title || "",
            company: selected.company || "",
            location: selected.location || "",
            url: selected.url || "",
            description: selected.description || "",
            source: selected.source || "",
            contract: selected.contract || "",
          },
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        throw new Error(data?.detail || ("HTTP " + r.status));
      }
      setCounters((c) => ({ ...c, cv: c.cv + 1 }));
      const k = offerKey(selected);
      setValidationByOffer((s) => ({ ...s, [k]: { ...(s[k] || {}), cvApproved: false } }));
      if (data?.status === "pdf_generated") {
        notifyCvGeneratedPdf();
      } else {
        notifyCvGeneratedTexOnly();
      }
    } catch (err: any) {
      notifyCvGenerateError(err?.message);
    } finally {
      setCvGenerating(false);
    }
  }

  async function onUpdateApplicationStatus(applicationId: string, status: string) {
    try {
      await fetch(API.applications.patch(applicationId), {
        method: "PATCH",
        headers: devAuthHeaders("user"),
        body: JSON.stringify({ status }),
      });
      await refreshApplications();
    } catch {
      // best effort
    }
  }

  async function onDownloadGeneratedCV() {
    if (cvDownloading) return;
    setCvDownloading(true);
    try {
      const r = await fetch(API.cv.generatedDownload, {
        method: "GET",
        headers: devAuthHeaders("user"),
      });
      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        throw new Error(data?.detail || ("HTTP " + r.status));
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "cv_genere.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      notifyGeneratedCvDownloadStarted();
    } catch (err: any) {
      notifyGeneratedCvDownloadError(err?.message);
    } finally {
      setCvDownloading(false);
    }
  }

  function onApprove() {
    setApproved(true);
    setCounters((c) => ({ ...c, sent: c.sent + 1 }));
    // Auto-enregistre la candidature cote backend (visible sur /candidatures)
    if (selected) {
      const safeUrl = toSafeExternalUrl(selected.url);
      const payload = {
        company: selected.company || "",
        position: selected.title || "",
        location: selected.location || "",
        url: safeUrl || "",
        source: selected.source || "",
        status: "sent",
      };
      setPendingApplication(payload);
      fetch(API.applications.create, {
        method: "POST",
        headers: devAuthHeaders("user"),
        body: JSON.stringify(payload),
      }).then(() => refreshApplications()).catch(() => { /* best-effort */ });
    }
  }

  useEffect(() => {
    const pending = applications.filter((a) => ["draft", "sent", "viewed"].includes((a.status || "").toLowerCase())).length;
    setCounters((c) => ({ ...c, pending }));
  }, [applications]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="max-w-6xl mx-auto px-6 py-10 space-y-8">

        <header className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wider text-slate-500">Module Emploi</p>
            <h1 className="text-3xl font-semibold mt-1">Mission Emploi</h1>
            <p className="text-sm text-slate-500 mt-1">Recherche intelligente multi-sources, enrichissement et generation de CV.</p>
          </div>
          <div className="text-right text-xs text-slate-400">
            {correlationId ? <>correlation_id : <span className="font-mono">{correlationId}</span></> : null}
          </div>
        </header>

        {globalError ? (
          <div className="flex items-start gap-2 p-4 rounded-lg border border-rose-200 bg-rose-50 text-rose-800">
            <AlertTriangle className="w-5 h-5 flex-none mt-0.5" />
            <div className="text-sm">
              <div className="font-medium">La mission a echoue</div>
              <div className="text-rose-700">{globalError}</div>
            </div>
          </div>
        ) : null}

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-5">
            <Sparkles className="w-4 h-4 text-indigo-500" />
            <h2 className="text-lg font-medium">Nouvelle mission</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Poste recherche</span>
              <div className="mt-1 relative">
                <Briefcase className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
                  value={form.query}
                  onChange={(e) => setForm({ ...form, query: e.target.value })}
                  placeholder="Data Scientist IA" />
              </div>
            </label>

            <label className="block">
              <span className="text-sm font-medium text-slate-700">Ville</span>
              <div className="mt-1 relative">
                <MapPin className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
                  value={form.location}
                  onChange={(e) => setForm({ ...form, location: e.target.value })}
                  placeholder="Paris" />
              </div>
            </label>
          </div>

          <div className="mt-5">
            <div className="text-sm font-medium text-slate-700 mb-2">Rayon</div>
            <div className="flex flex-wrap gap-2">
              {RADII.map((r) => (
                <button key={r.id} type="button" onClick={() => setForm({ ...form, radius: r.id })} className={chipClass(form.radius === r.id)}>{r.label}</button>
              ))}
            </div>
          </div>

          <div className="mt-5">
            <div className="text-sm font-medium text-slate-700 mb-2">Sources</div>
            <div className="flex flex-wrap gap-2">
              {SOURCES.map((s) => (
                <button key={s.id} type="button" onClick={() => toggleSource(s.id, s.disabled)} disabled={s.disabled} className={chipClass(form.sources.includes(s.id), s.disabled)}>
                  <span className="inline-flex items-center gap-1.5">
                    {sourceBadge(s.id)}
                    {s.label}
                    {s.badge ? <span className={"ml-1 px-1.5 py-0.5 text-[10px] rounded-full font-medium " + (s.badge === "Officiel" ? "bg-blue-100 text-blue-700" : s.badge === "Cadres" ? "bg-violet-100 text-violet-700" : s.badge === "Global" ? "bg-pink-100 text-pink-700" : "bg-amber-100 text-amber-700")}>{s.badge}</span> : null}
                    {s.disabled ? <span className="ml-1 text-[10px] uppercase tracking-wider text-slate-400">bientot</span> : null}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="mt-5">
            <div className="text-sm font-medium text-slate-700 mb-2">Date de publication</div>
            <div className="flex flex-wrap gap-2">
              {RECENCY.map((r) => (
                <button key={r.id} type="button" onClick={() => setForm({ ...form, recency: r.id })} className={chipClass(form.recency === r.id)}>{r.label}</button>
              ))}
            </div>
          </div>

          <div className="mt-5">
            <div className="text-sm font-medium text-slate-700 mb-2">Type de contrat</div>
            <div className="flex flex-wrap gap-2">
              {CONTRACTS.map((c) => (
                <button key={c.id} type="button" onClick={() => setForm({ ...form, contract: c.id })} className={chipClass(form.contract === c.id)}>{c.label}</button>
              ))}
            </div>
          </div>

          <div className="mt-6 flex items-center justify-between gap-4">
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Nombre maximum</span>
              <input type="number" min={1} max={100} value={form.max}
                onChange={(e) => setForm({ ...form, max: Math.max(1, Math.min(100, Number(e.target.value) || 1)) })}
                className="mt-1 w-24 px-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400" />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Seuil de compatibilite</span>
              <input type="number" min={0} max={1} step={0.05} value={form.scoreThreshold}
                onChange={(e) => setForm({ ...form, scoreThreshold: Math.max(0, Math.min(1, Number(e.target.value) || 0)) })}
                className="mt-1 w-28 px-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400" />
            </label>
            <button type="button" onClick={onLaunch} disabled={running || !form.query.trim()} className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-500 disabled:bg-slate-300 disabled:cursor-not-allowed">
              {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />} Lancer la mission
            </button>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-5">
            <Filter className="w-4 h-4 text-indigo-500" />
            <h2 className="text-lg font-medium">Live pipeline</h2>
          </div>
          <ul className="space-y-2">
            {steps.map((s) => (
              <li key={s.name} className="flex items-center gap-3 text-sm">
                {statusBadge(s.status)}
                <span className={"flex-1 " + (s.status === "running" ? "font-medium text-slate-900" : "text-slate-700")}>{s.label}</span>
                {s.detail ? <span className="text-xs text-slate-400">{s.detail}</span> : null}
              </li>
            ))}
          </ul>
          {orchestrator ? (
            <div className="mt-4 text-xs text-slate-500 flex items-center gap-3 flex-wrap">
              <span>intent : <span className="font-mono">{orchestrator.intent || "-"}</span></span>
              <span>plan : <span className="font-mono">{orchestrator.plan || orchestrator.plan_name || "-"}</span></span>
              <span>policy : <span className="font-mono">{orchestrator.policy || "-"}</span></span>
              <span>status : <span className="font-mono">{orchestrator.status || "-"}</span></span>
            </div>
          ) : null}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-5">
            <Briefcase className="w-4 h-4 text-indigo-500" />
            <h2 className="text-lg font-medium">Resultats</h2>
            <span className="ml-auto text-sm text-slate-500">{matchedOffers.length} offre{matchedOffers.length > 1 ? "s" : ""}</span>
          </div>

          {(form.sources.includes("france_travail") || franceTravailResultMode) ? (
            <div className={"mb-5 rounded-xl border p-4 " + connectorTone(franceTravailHealth)}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium">France Travail</div>
                  <div className="mt-1 text-xs opacity-80">
                    {franceTravailHealth?.token_ok
                      ? "Connecteur live actif"
                      : franceTravailHealth?.configured
                        ? "Connecteur configure, verification token requise"
                        : "Connecteur non configure"}
                  </div>
                </div>
                <div className="text-right text-xs">
                  <div>
                    Etat API : <span className="font-medium">{franceTravailHealth?.token_ok ? "live" : franceTravailHealth?.configured ? "degrade" : "mock"}</span>
                  </div>
                  {franceTravailResultMode ? (
                    <div className="mt-1">
                      Derniere recherche : <span className="font-medium">{franceTravailResultMode === "live" ? "offres live" : "fallback mock"}</span>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}

          {matchedOffers.length === 0 ? (
            <p className="text-sm text-slate-400">Aucune offre. Lance une mission pour demarrer.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {matchedOffers.map((o, i) => {
                const score = o.match_score ?? o.score ?? 0;
                const safeOfferUrl = toSafeExternalUrl(o.url);
                const k = offerKey(o);
                const contactLoading = !!contactLoadingByOffer[k];
                const contactErr = contactErrorByOffer[k];
                const contact = contactsByOffer[k];
                const lettreLoading = !!lettreLoadingByOffer[k];
                const lettreErr = lettreErrorByOffer[k];
                const lettre = lettreByOffer[k];
                const sendLoading = !!sendLoadingByOffer[k];
                const sendErr = sendErrorByOffer[k];
                const sendRes = sendByOffer[k];
                const validation = validationByOffer[k] || {};
                const sendPhrase = confirmPhraseByOffer[k] || "";
                return (
                  <article key={(o.offer_id || o.id || "off") + "-" + i} className="rounded-xl border border-slate-200 p-4 hover:shadow-md transition">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="font-medium text-slate-900">{o.title || "Poste"}</h3>
                        <p className="text-sm text-slate-600 flex items-center gap-1 mt-0.5"><Building2 className="w-3.5 h-3.5" /> {o.company || "-"}</p>
                      </div>
                      <span className={"inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium " + matchColor(score)}>{Math.round((score || 0) * 100)}%</span>
                    </div>
                    <div className="mt-2 flex items-center gap-3 text-xs text-slate-500">
                      <span className="inline-flex items-center gap-1"><MapPin className="w-3 h-3" />{o.location || "-"}</span>
                      <span className="inline-flex items-center gap-1">{sourceBadge(o.source)} {sourceLabel(o.source)}</span>
                      {(o.source || "").toLowerCase().includes("france_travail") ? (
                        <span className={"inline-flex items-center rounded-full px-2 py-0.5 font-medium " + (franceTravailResultMode === "live" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700")}>
                          {franceTravailResultMode === "live" ? "live" : "mock"}
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-3 flex items-center gap-2">
                      <button type="button" onClick={() => onGenerateCV(o)} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-500"><FileText className="w-3.5 h-3.5" /> Adapter mon CV</button>
                      <button type="button" onClick={() => onGenerateLettreIfRequired(o)} disabled={lettreLoading} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-slate-200 text-xs font-medium text-slate-700 hover:border-slate-300 disabled:opacity-60">
                        {lettreLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5" />} Lettre auto (si requise)
                      </button>
                      <button type="button" onClick={() => onFindContact(o)} disabled={contactLoading} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-slate-200 text-xs font-medium text-slate-700 hover:border-slate-300 disabled:opacity-60">
                        {contactLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Globe className="w-3.5 h-3.5" />} Trouver contact RH
                      </button>
                      <button type="button" onClick={() => onSendApplication(o)} disabled={sendLoading} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-emerald-200 text-xs font-medium text-emerald-700 hover:border-emerald-300 disabled:opacity-60">
                        {sendLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />} Envoyer candidature
                      </button>
                      {safeOfferUrl ? (
                        <a href={safeOfferUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-slate-200 text-xs font-medium text-slate-700 hover:border-slate-300"><ExternalLink className="w-3.5 h-3.5" /> Voir l&apos;offre</a>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-slate-200 text-xs font-medium text-slate-400" title="Lien annonceur indisponible">Annonce non verifiable</span>
                      )}
                    </div>
                    <div className="mt-2 rounded-md border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700 space-y-2">
                      <div className="font-medium text-slate-800">Validation utilisateur (assistant sous controle)</div>
                      <div className="flex flex-wrap gap-2">
                        <button type="button" onClick={() => setValidationByOffer((s) => ({ ...s, [k]: { ...(s[k] || {}), offerApproved: !(s[k]?.offerApproved) } }))} className={"px-2 py-1 rounded border " + (validation.offerApproved ? "border-emerald-300 bg-emerald-50 text-emerald-700" : "border-slate-300 bg-white text-slate-700")}>Offre validee</button>
                        <button type="button" onClick={() => setValidationByOffer((s) => ({ ...s, [k]: { ...(s[k] || {}), cvApproved: !(s[k]?.cvApproved) } }))} className={"px-2 py-1 rounded border " + (validation.cvApproved ? "border-emerald-300 bg-emerald-50 text-emerald-700" : "border-slate-300 bg-white text-slate-700")}>CV valide</button>
                        <button type="button" onClick={() => setValidationByOffer((s) => ({ ...s, [k]: { ...(s[k] || {}), contactApproved: !(s[k]?.contactApproved) } }))} className={"px-2 py-1 rounded border " + (validation.contactApproved ? "border-emerald-300 bg-emerald-50 text-emerald-700" : "border-slate-300 bg-white text-slate-700")}>Contact RH valide</button>
                      </div>
                      <div>
                        <label className="block text-[11px] text-slate-600 mb-1">Confirmation explicite avant envoi (obligatoire)</label>
                        <input
                          className="w-full px-2 py-1.5 rounded border border-slate-300 bg-white"
                          value={sendPhrase}
                          onChange={(e) => setConfirmPhraseByOffer((s) => ({ ...s, [k]: e.target.value }))}
                          placeholder="JE CONFIRME L ENVOI"
                        />
                      </div>
                    </div>
                    {contactErr ? (
                      <div className="mt-2 text-xs text-rose-600">Contact indisponible: {contactErr}</div>
                    ) : null}
                    {lettreErr ? (
                      <div className="mt-2 text-xs text-rose-600">Lettre indisponible: {lettreErr}</div>
                    ) : null}
                    {sendErr ? (
                      <div className="mt-2 text-xs text-rose-600">Envoi indisponible: {sendErr}</div>
                    ) : null}
                    {contact ? (
                      <div className="mt-2 rounded-md border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700 space-y-1">
                        <div><span className="font-medium">Email:</span> {contact.primary_email || (contact.emails && contact.emails[0]) || "-"}</div>
                        <div><span className="font-medium">Telephone:</span> {contact.primary_phone || (contact.phones && contact.phones[0]) || "-"}</div>
                        {contact.company_domain ? <div><span className="font-medium">Domaine:</span> {contact.company_domain}</div> : null}
                      </div>
                    ) : null}
                    {lettre ? (
                      <div className="mt-2 rounded-md border border-indigo-200 bg-indigo-50 p-2 text-xs text-indigo-900 space-y-1">
                        <div>
                          <span className="font-medium">Lettre demandee:</span> {lettre.required ? "oui" : "non"}
                        </div>
                        {lettre.letter?.subject ? (
                          <div><span className="font-medium">Objet:</span> {lettre.letter.subject}</div>
                        ) : null}
                        {lettre.letter?.body ? (
                          <div className="whitespace-pre-wrap text-[11px] leading-relaxed max-h-40 overflow-auto border border-indigo-100 bg-white rounded p-2">
                            {lettre.letter.body}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                    {sendRes ? (
                      <div className="mt-2 rounded-md border border-emerald-200 bg-emerald-50 p-2 text-xs text-emerald-900 space-y-1">
                        <div><span className="font-medium">Envoi:</span> {sendRes.sent ? "envoye" : "brouillon"}</div>
                        {sendRes.recipient ? <div><span className="font-medium">Destinataire:</span> {sendRes.recipient}</div> : null}
                        {sendRes.subject ? <div><span className="font-medium">Objet:</span> {sendRes.subject}</div> : null}
                        {typeof sendRes.attachment_used === "boolean" ? <div><span className="font-medium">CV joint:</span> {sendRes.attachment_used ? "oui" : "non"}</div> : null}
                        {sendRes.error ? <div><span className="font-medium">Erreur:</span> {sendRes.error}</div> : null}
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          )}
        </section>

        {selected ? (
          <section className="relative rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" aria-busy={cvBusy}>
            {cvBusy ? (
              <div className="absolute inset-0 z-10 rounded-2xl bg-white/70 backdrop-blur-[1px] flex items-center justify-center">
                <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> Traitement du CV en cours...
                </div>
              </div>
            ) : null}
            <div className="flex items-center gap-2 mb-5">
              <FileText className="w-4 h-4 text-indigo-500" />
              <h2 className="text-lg font-medium">CV Studio</h2>
              <span className="ml-auto text-xs text-slate-500">Cible : {selected.title} - {selected.company}</span>
            </div>
            <p className="text-sm text-slate-600 mb-3">Choisis un modele de CV :</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[ { id: "moderne", label: "Moderne" }, { id: "classique", label: "Classique" }, { id: "minimaliste", label: "Minimaliste" }, { id: "executive", label: "Executive" } ].map((t) => (
                <button key={t.id} type="button" onClick={() => setTemplateChoice(t.id)} className={"px-3 py-3 rounded-lg border text-sm font-medium text-left " + (templateChoice === t.id ? "border-indigo-500 bg-indigo-50 text-indigo-700" : "border-slate-200 hover:border-slate-300")}>{t.label}</button>
              ))}
            </div>
            <div className="mt-6 flex items-center justify-end gap-2">
              <button type="button" onClick={onGenerateSelectedCV} disabled={cvBusy} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 disabled:bg-slate-300 disabled:cursor-not-allowed">
                {cvGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />} Generer mon CV
              </button>
              <button type="button" onClick={onDownloadGeneratedCV} disabled={cvBusy} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium hover:border-slate-400 disabled:opacity-50 disabled:cursor-not-allowed">
                {cvDownloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ExternalLink className="w-4 h-4" />} Telecharger le CV genere
              </button>
              {!approved ? (
                <button type="button" onClick={onApprove} disabled={cvBusy} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-500 disabled:bg-slate-300 disabled:cursor-not-allowed"><ShieldCheck className="w-4 h-4" /> Valider et preparer la candidature</button>
              ) : (
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-50 text-emerald-700 text-sm font-medium border border-emerald-200"><CheckCircle2 className="w-4 h-4" /> Candidature validee. Envoi simule.</div>
              )}
            </div>
          </section>
        ) : null}

        <PendingApplicationNotice
          pending={pendingApplication}
          onDismiss={() => setPendingApplication(null)}
        />

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-5">
            <Briefcase className="w-4 h-4 text-indigo-500" />
            <h2 className="text-lg font-medium">Tableau de bord</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[ { label: "Offres trouvees", value: counters.found }, { label: "Offres retenues", value: counters.kept }, { label: "CV generes", value: counters.cv }, { label: "Candidatures envoyees", value: counters.sent }, { label: "En attente", value: counters.pending } ].map((kpi) => (
              <div key={kpi.label} className="rounded-xl border border-slate-200 p-4">
                <div className="text-xs text-slate-500">{kpi.label}</div>
                <div className="text-2xl font-semibold mt-1 text-slate-900">{kpi.value}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-5">
            <ShieldCheck className="w-4 h-4 text-indigo-500" />
            <h2 className="text-lg font-medium">Tracking candidatures (mini-CRM)</h2>
            <span className="ml-auto text-xs text-slate-500">{applicationsLoading ? "chargement..." : `${applications.length} enregistrees`}</span>
          </div>
          {applications.length === 0 ? (
            <p className="text-sm text-slate-500">Aucune candidature suivie pour le moment.</p>
          ) : (
            <div className="space-y-3">
              {applications.slice(0, 10).map((a) => (
                <div key={a.application_id} className="rounded-lg border border-slate-200 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-slate-900">{a.position} - {a.company}</div>
                      <div className="text-xs text-slate-500">{a.email || "contact inconnu"} {a.source ? `- ${a.source}` : ""}</div>
                    </div>
                    <span className="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-700">{a.status}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs">
                    <button type="button" onClick={() => onUpdateApplicationStatus(a.application_id, "sent")} className="px-2 py-1 rounded border border-slate-300">Envoye</button>
                    <button type="button" onClick={() => onUpdateApplicationStatus(a.application_id, "interview")} className="px-2 py-1 rounded border border-slate-300">Relance/entretien</button>
                    <button type="button" onClick={() => onUpdateApplicationStatus(a.application_id, "viewed")} className="px-2 py-1 rounded border border-slate-300">Reponse recue</button>
                    <button type="button" onClick={() => onUpdateApplicationStatus(a.application_id, "rejected")} className="px-2 py-1 rounded border border-slate-300">Refus</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

      </div>
    </div>
  );
}