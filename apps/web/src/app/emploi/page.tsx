"use client";

import Link from "next/link";
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  Briefcase, MapPin, Sparkles, CheckCircle2, Circle, XCircle, Loader2,
  FileText, Zap, Building2, AlertTriangle, ShieldCheck,
  Linkedin, Globe, Filter, ExternalLink,
} from "lucide-react";
import { API, devAuthHeaders } from "@/lib/api";

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

interface OrchestratorResponse {
  intent?: string;
  plan?: string;
  plan_name?: string;
  plan_version?: string;
  policy?: string;
  status?: string;
  results?: Record<string, WorkflowResult>;
}

const SOURCES: { id: string; label: string; disabled?: boolean; badge?: string }[] = [
  { id: "adzuna",          label: "Adzuna",            badge: "Premium" },
  { id: "france_travail",  label: "France Travail",    badge: "Officiel" },
  { id: "wttj",            label: "Welcome to the Jungle" },
  { id: "linkedin",        label: "LinkedIn" },
  { id: "indeed",          label: "Indeed" },
  { id: "hellowork",       label: "HelloWork" },
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
  recency: "24h",
  sources: ["adzuna", "france_travail", "wttj", "linkedin", "indeed", "hellowork"] as string[],
  max: 20,
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
  if (s.includes("apec")) return <span className="inline-block w-2 h-2 rounded-full bg-violet-500" title="APEC" />;
  if (s.includes("themuse") || s.includes("muse")) return <span className="inline-block w-2 h-2 rounded-full bg-pink-500" title="The Muse" />;
  return <Globe className="w-3.5 h-3.5" />;
}

function sourceLabel(source?: string) {
  const s = (source || "").toLowerCase();
  if (s.includes("adzuna")) return "Adzuna";
  if (s.includes("france_travail")) return "France Travail";
  if (s.includes("wttj")) return "WTTJ";
  if (s.includes("apec")) return "APEC";
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
    const o = (r && (r as any).offers) as Offer[] | undefined;
    if (Array.isArray(o)) out.push(...o);
  }
  return out;
}

export default function EmploiPage() {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [steps, setSteps] = useState<PipelineStep[]>(PIPELINE_TEMPLATE);
  const [running, setRunning] = useState(false);
  const [correlationId, setCorrelationId] = useState<string | null>(null);
  const [orchestrator, setOrchestrator] = useState<OrchestratorResponse | null>(null);
  const [offers, setOffers] = useState<Offer[]>([]);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Offer | null>(null);
  const [templateChoice, setTemplateChoice] = useState<string>("moderne");
  const [approved, setApproved] = useState(false);
  const [counters, setCounters] = useState({ found: 0, kept: 0, cv: 0, sent: 0, pending: 0 });
  const [pendingApplication, setPendingApplication] = useState<{ company: string; position: string; location?: string; url?: string; source?: string } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

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
    return [...offers].sort((a, b) => {
      const sa = a.match_score ?? a.score ?? 0;
      const sb = b.match_score ?? b.score ?? 0;
      return sb - sa;
    });
  }, [offers]);

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
    const sourcesLabel = form.sources.length > 0 ? form.sources.join("/") : "linkedin";
    const userMessage = "Trouver " + form.query + " a " + form.location +
      " (rayon " + radiusLabel + ", publie dans les " + recencyHours + "h, sources " + sourcesLabel +
      ", max " + form.max + ") et lancer une candidature";

    const newCorr = "emp-" + Date.now() + "-" + Math.floor(Math.random() * 1000);
    setCorrelationId(newCorr);

    try {
      setSteps((s) => s.map((x) => x.name === "intent" ? { ...x, status: "running" } : x));

      const resp = await fetch(API.employment.workflow, {
        method: "POST",
        headers: devAuthHeaders("admin"),
        body: JSON.stringify({
          message: userMessage,
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
      setOffers(extracted);

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

      setCounters((c) => ({ ...c, found: extracted.length, kept: extracted.length }));
    } catch (err: any) {
      setGlobalError(err?.message || String(err));
      setSteps((cur) => cur.map((s) => s.status === "running" ? { ...s, status: "failed", detail: err?.message } : s));
    } finally {
      setRunning(false);
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    }
  }, [form, running]);

  function onGenerateCV(o: Offer) {
    setSelected(o);
    setApproved(false);
    setCounters((c) => ({ ...c, cv: c.cv + 1 }));
  }

  function onApprove() {
    setApproved(true);
    setCounters((c) => ({ ...c, sent: c.sent + 1 }));
    // Auto-enregistre la candidature cote backend (visible sur /candidatures)
    if (selected) {
      const payload = {
        company: selected.company || "",
        position: selected.title || "",
        location: selected.location || "",
        url: selected.url || "",
        source: selected.source || "",
        status: "sent",
      };
      setPendingApplication(payload);
      fetch(API.applications.create, {
        method: "POST",
        headers: devAuthHeaders("user"),
        body: JSON.stringify(payload),
      }).catch(() => { /* best-effort */ });
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
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

          <div className="mt-6 flex items-center justify-between gap-4">
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Nombre maximum</span>
              <input type="number" min={1} max={100} value={form.max}
                onChange={(e) => setForm({ ...form, max: Math.max(1, Math.min(100, Number(e.target.value) || 1)) })}
                className="mt-1 w-24 px-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400" />
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

          {matchedOffers.length === 0 ? (
            <p className="text-sm text-slate-400">Aucune offre. Lance une mission pour demarrer.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {matchedOffers.map((o, i) => {
                const score = o.match_score ?? o.score ?? 0;
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
                      <span className="inline-flex items-center gap-1">{sourceBadge(o.source)} {o.source || "-"}</span>
                    </div>
                    <div className="mt-3 flex items-center gap-2">
                      <button type="button" onClick={() => onGenerateCV(o)} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-500"><FileText className="w-3.5 h-3.5" /> Adapter mon CV</button>
                      {o.url ? (<a href={o.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-slate-200 text-xs font-medium text-slate-700 hover:border-slate-300"><ExternalLink className="w-3.5 h-3.5" /> Voir l 'offre</a>) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        {selected ? (
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
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
              {!approved ? (
                <button type="button" onClick={onApprove} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-500"><ShieldCheck className="w-4 h-4" /> Valider et preparer la candidature</button>
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

      </div>
    </main>
  );
}