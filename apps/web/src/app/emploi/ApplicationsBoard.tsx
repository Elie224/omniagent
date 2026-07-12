"use client";

import { useEffect, useState, useCallback } from "react";
import { Briefcase, Building2, MapPin, Mail, Phone, ExternalLink, Trash2, Save, Loader2, AlertTriangle, Plus, ChevronDown, CalendarDays, MessageSquare } from "lucide-react";
import { API, devAuthHeaders } from "@/lib/api";

export interface Application {
  application_id: string;
  company: string;
  position: string;
  location: string;
  email: string;
  phone: string;
  url: string;
  source: string;
  contract: string;
  status: string;
  sent_at: string;
  updated_at: string;
  notes: string;
  contact_name: string;
}

const STATUS_LABELS: Record<string, { label: string; color: string; dot: string }> = {
  draft:     { label: "Brouillon",       color: "bg-slate-100 text-slate-700 border-slate-200",     dot: "bg-slate-400" },
  sent:      { label: "Envoyee",         color: "bg-indigo-50 text-indigo-700 border-indigo-200",   dot: "bg-indigo-500" },
  viewed:    { label: "Vue",             color: "bg-sky-50 text-sky-700 border-sky-200",            dot: "bg-sky-500" },
  interview: { label: "En entretien",    color: "bg-amber-50 text-amber-700 border-amber-200",      dot: "bg-amber-500" },
  accepted:  { label: "Acceptee",        color: "bg-emerald-50 text-emerald-700 border-emerald-200", dot: "bg-emerald-500" },
  rejected:  { label: "Refusee",         color: "bg-rose-50 text-rose-700 border-rose-200",          dot: "bg-rose-500" },
  withdrawn: { label: "Retiree",         color: "bg-slate-100 text-slate-600 border-slate-200",      dot: "bg-slate-500" },
};

const STATUS_KEYS = Object.keys(STATUS_LABELS);

function fmtDate(iso: string): string {
  if (!iso) return "-";
  try { return new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" }); }
  catch { return iso.slice(0, 10); }
}

export interface ApplicationsBoardProps {
  // Quand'une offre est validee dans le pipeline Emploi, on peut l injecter ici.
  pendingFromPipeline?: { company: string; position: string; location?: string; url?: string; source?: string } | null;
  onPendingConsumed?: () => void;
}

export function ApplicationsBoard(props: ApplicationsBoardProps) {
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editNotes, setEditNotes] = useState<string>("");
  const [editStatus, setEditStatus] = useState<string>("sent");
  const [saving, setSaving] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>("all");

  const reload = useCallback(async () => {
    try {
      const r = await fetch(API.applications.list, { headers: devAuthHeaders("user"), cache: "no-store" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setApps(data.applications || []);
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Erreur lors du chargement des candidatures");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  // Quand le pipeline Emploi signale qu'une candidature a ete validee
  useEffect(() => {
    if (!props.pendingFromPipeline) return;
    (async () => {
      try {
        const r = await fetch(API.applications.create, {
          method: "POST",
          headers: devAuthHeaders("user"),
          body: JSON.stringify({
            company: props.pendingFromPipeline!.company,
            position: props.pendingFromPipeline!.position,
            location: props.pendingFromPipeline!.location || "",
            url: props.pendingFromPipeline!.url || "",
            source: props.pendingFromPipeline!.source || "",
            status: "sent",
          }),
        });
        if (r.ok) {
          await reload();
          props.onPendingConsumed?.();
        }
      } catch {}
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.pendingFromPipeline]);

  async function onDelete(id: string) {
    if (!confirm("Supprimer cette candidature du suivi ? Cette action'est irreversible.")) return;
    try {
      await fetch(API.applications.remove(id), { method: "DELETE", headers: devAuthHeaders("user") });
      setApps((cur) => cur.filter((a) => a.application_id !== id));
    } catch (e: any) {
      setError(e?.message || "Erreur lors de la suppression");
    }
  }

  function startEdit(a: Application) {
    setEditingId(a.application_id);
    setEditNotes(a.notes || "");
    setEditStatus(a.status || "sent");
  }

  async function saveEdit(id: string) {
    setSaving(true);
    try {
      const r = await fetch(API.applications.patch(id), {
        method: "PATCH",
        headers: devAuthHeaders("user"),
        body: JSON.stringify({ status: editStatus, notes: editNotes }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setApps((cur) => cur.map((a) => (a.application_id === id ? data.application : a)));
      setEditingId(null);
    } catch (e: any) {
      setError(e?.message || "Erreur de sauvegarde");
    } finally {
      setSaving(false);
    }
  }

  // Compteurs par statut
  const stats: Record<string, number> = {};
  STATUS_KEYS.forEach((k) => { stats[k] = 0; });
  apps.forEach((a) => { if (stats[a.status] !== undefined) stats[a.status] += 1; });

  const filtered = filterStatus === "all" ? apps : apps.filter((a) => a.status === filterStatus);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <Briefcase className="w-4 h-4 text-indigo-500" />
        <h2 className="text-lg font-medium">Mes candidatures</h2>
        <span className="text-xs text-slate-500">{apps.length} suivie{apps.length > 1 ? "s" : ""}</span>
        <div className="ml-auto flex items-center gap-2">
          <button type="button" onClick={() => setShowAdd((v) => !v)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-slate-200 text-sm font-medium text-slate-700 hover:border-indigo-400 hover:text-indigo-700">
            <Plus className="w-4 h-4" /> Ajouter manuellement
          </button>
        </div>
      </div>

      {/* Mini-stats */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-2 mb-5">
        {STATUS_KEYS.map((k) => {
          const meta = STATUS_LABELS[k];
          return (
            <button key={k} type="button" onClick={() => setFilterStatus((cur) => cur === k ? "all" : k)}
                    className={"rounded-lg border p-2 text-left transition " + (filterStatus === k ? "border-indigo-400 bg-indigo-50" : "border-slate-200 hover:border-slate-300")}>
              <div className="flex items-center gap-1.5 text-xs text-slate-600">
                <span className={"inline-block w-1.5 h-1.5 rounded-full " + meta.dot} />
                {meta.label}
              </div>
              <div className="text-xl font-semibold mt-1 text-slate-900">{stats[k]}</div>
            </button>
          );
        })}
      </div>

      {error ? (
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" /> {error}
        </div>
      ) : null}

      {showAdd ? (
        <AddApplicationForm onCancel={() => setShowAdd(false)} onCreated={async (a) => { setShowAdd(false); await reload(); setApps((cur) => [a, ...cur]); }} />
      ) : null}

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-slate-500 py-8 justify-center">
          <Loader2 className="w-4 h-4 animate-spin" /> Chargement...
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-10 text-sm text-slate-500">
          {apps.length === 0
            ? "Aucune candidature suivie pour le moment. Valide une offre depuis le pipeline ou ajoute-en une manuellement."
            : "Aucune candidature avec ce statut."}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {filtered.map((a) => {
            const meta = STATUS_LABELS[a.status] || STATUS_LABELS.sent;
            const isEditing = editingId === a.application_id;
            return (
              <article key={a.application_id} className="rounded-xl border border-slate-200 p-4 hover:shadow-sm transition">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="font-medium text-slate-900 truncate">{a.position || "Poste"}</h3>
                    <p className="text-sm text-slate-600 inline-flex items-center gap-1 mt-0.5">
                      <Building2 className="w-3.5 h-3.5" /> {a.company || "-"}
                    </p>
                  </div>
                  <span className={"shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border " + meta.color}>
                    <span className={"inline-block w-1.5 h-1.5 rounded-full " + meta.dot} />
                    {meta.label}
                  </span>
                </div>

                <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-600">
                  {a.location ? <span className="inline-flex items-center gap-1"><MapPin className="w-3 h-3" />{a.location}</span> : null}
                  <span className="inline-flex items-center gap-1"><CalendarDays className="w-3 h-3" />Envoyee le {fmtDate(a.sent_at)}</span>
                  {a.email ? <a href={"mailto:" + a.email} className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-700 truncate"><Mail className="w-3 h-3" />{a.email}</a> : null}
                  {a.phone ? <a href={"tel:" + a.phone} className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-700"><Phone className="w-3 h-3" />{a.phone}</a> : null}
                  {a.url ? <a href={a.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-700 truncate"><ExternalLink className="w-3 h-3" />Voir l 'offre</a> : null}
                  {a.contact_name ? <span className="inline-flex items-center gap-1"><MessageSquare className="w-3 h-3" />{a.contact_name}</span> : null}
                  {a.source ? <span className="inline-flex items-center gap-1 text-slate-500">Source: {a.source}</span> : null}
                </div>

                {isEditing ? (
                  <div className="mt-3 space-y-2 border-t border-slate-100 pt-3">
                    <div className="flex items-center gap-2">
                      <label className="text-xs font-medium text-slate-600">Statut:</label>
                      <select value={editStatus} onChange={(e) => setEditStatus(e.target.value)}
                              className="px-2 py-1 border border-slate-200 rounded-md text-xs">
                        {STATUS_KEYS.map((k) => <option key={k} value={k}>{STATUS_LABELS[k].label}</option>)}
                      </select>
                    </div>
                    <textarea value={editNotes} onChange={(e) => setEditNotes(e.target.value)} rows={2}
                              placeholder="Notes (relance, retour, etc.)"
                              className="w-full px-2 py-1.5 border border-slate-200 rounded-md text-xs" />
                    <div className="flex items-center justify-end gap-2">
                      <button type="button" onClick={() => setEditingId(null)} className="px-3 py-1 text-xs text-slate-600">Annuler</button>
                      <button type="button" onClick={() => saveEdit(a.application_id)} disabled={saving}
                              className="inline-flex items-center gap-1 px-3 py-1 rounded-md bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-500 disabled:opacity-50">
                        {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />} Sauver
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    {a.notes ? <p className="mt-3 text-xs text-slate-600 italic border-l-2 border-slate-200 pl-2">{a.notes}</p> : null}
                    <div className="mt-3 flex items-center justify-end gap-1">
                      <button type="button" onClick={() => startEdit(a)} className="px-2 py-1 text-xs text-slate-600 hover:text-indigo-700">Modifier</button>
                      <button type="button" onClick={() => onDelete(a.application_id)} className="inline-flex items-center gap-1 px-2 py-1 text-xs text-rose-600 hover:text-rose-700">
                        <Trash2 className="w-3 h-3" /> Supprimer
                      </button>
                    </div>
                  </>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

function AddApplicationForm(props: { onCancel: () => void; onCreated: (a: Application) => void }) {
  const [company, setCompany] = useState("");
  const [position, setPosition] = useState("");
  const [location, setLocation] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [url, setUrl] = useState("");
  const [source, setSource] = useState("");
  const [status, setStatus] = useState("sent");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onSubmit() {
    setErr(null);
    if (!company.trim()) { setErr("Le nom de l'entreprise est obligatoire."); return; }
    if (!position.trim()) { setErr("L intitule du poste est obligatoire."); return; }
    setSaving(true);
    try {
      const r = await fetch(API.applications.create, {
        method: "POST",
        headers: devAuthHeaders("user"),
        body: JSON.stringify({ company, position, location, email, phone, url, source, status, notes }),
      });
      if (!r.ok) {
        const t = await r.text();
        throw new Error(`HTTP ${r.status} - ${t || "echec de la creation"}`);
      }
      const data = await r.json();
      props.onCreated(data.application);
    } catch (e: any) {
      setErr(e?.message || "Erreur");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mb-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Mini label="Entreprise *" value={company} setValue={setCompany} placeholder="Google France" />
        <Mini label="Poste *" value={position} setValue={setPosition} placeholder="Data Scientist Senior" />
        <Mini label="Localisation" value={location} setValue={setLocation} placeholder="Paris" />
        <Mini label="Source" value={source} setValue={setSource} placeholder="linkedin, indeed..." />
        <Mini label="Email RH" value={email} setValue={setEmail} placeholder="rh@entreprise.com" type="email" />
        <Mini label="Telephone" value={phone} setValue={setPhone} placeholder="+33 ..." />
        <Mini label="URL offre" value={url} setValue={setUrl} placeholder="https://..." />
        <div className="flex flex-col">
          <label className="text-xs font-medium text-slate-600 mb-1">Statut</label>
          <select value={status} onChange={(e) => setStatus(e.target.value)}
                  className="px-3 py-2 border border-slate-200 rounded-md text-sm bg-white">
            {STATUS_KEYS.map((k) => <option key={k} value={k}>{STATUS_LABELS[k].label}</option>)}
          </select>
        </div>
      </div>
      <div className="mt-3">
        <label className="text-xs font-medium text-slate-600 mb-1 block">Notes</label>
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2}
                  placeholder="Canal, contexte, prochain contact..."
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm" />
      </div>
      {err ? <div className="mt-2 text-xs text-rose-600">{err}</div> : null}
      <div className="mt-3 flex items-center justify-end gap-2">
        <button type="button" onClick={props.onCancel} className="px-3 py-1.5 text-sm text-slate-600">Annuler</button>
        <button type="button" onClick={onSubmit} disabled={saving}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 disabled:opacity-50">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Ajouter
        </button>
      </div>
    </div>
  );
}

function Mini(props: { label: string; value: string; setValue: (v: string) => void; placeholder?: string; type?: string }) {
  return (
    <div className="flex flex-col">
      <label className="text-xs font-medium text-slate-600 mb-1">{props.label}</label>
      <input type={props.type || "text"} value={props.value} onChange={(e) => props.setValue(e.target.value)}
             placeholder={props.placeholder}
             className="px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:border-indigo-500" />
    </div>
  );
}
