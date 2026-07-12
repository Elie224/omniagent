"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { UserCircle2, Mail, Phone, MapPin, GraduationCap, Sparkles, Briefcase, Trash2, Save, CheckCircle2, Loader2, AlertTriangle, ArrowLeft } from "lucide-react";
import { API, devAuthHeaders } from "@/lib/api";
import CVUpload from "./CVUpload";

interface ExperienceItem {
  title: string;
  company: string;
  years: number | string;
  description: string;
}

interface ProfilePayload {
  full_name: string;
  email: string;
  phone: string;
  city: string;
  formation: string;
  skills: string[];
  target_roles: string[];
  experiences: ExperienceItem[];
  cv_url: string;
}

const EMPTY: ProfilePayload = {
  full_name: "",
  email: "",
  phone: "",
  city: "",
  formation: "",
  skills: [],
  target_roles: [],
  experiences: [],
  cv_url: "",
};

function splitCsv(s: string): string[] {
  return s.split(/[\n,;]+/).map((x) => x.trim()).filter(Boolean);
}

export default function ProfilPage() {
  const router = useRouter();
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [city, setCity] = useState("");
  const [formation, setFormation] = useState("");
  const [skillsCsv, setSkillsCsv] = useState("");
  const [rolesCsv, setRolesCsv] = useState("");
  const [experiences, setExperiences] = useState<ExperienceItem[]>([]);
  const [cvUrl, setCvUrl] = useState("");

  // Charger le profil existant au montage
  useEffect(() => {
    let abort = false;
    (async () => {
      try {
        const r = await fetch(API.profile.get, { headers: devAuthHeaders("user"), cache: "no-store" });
        if (r.status === 404) { if (!abort) setLoaded(true); return; }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        if (abort) return;
        setFullName(data.full_name || "");
        setEmail(data.email || "");
        setPhone(data.phone || "");
        setCity(data.city || "");
        setFormation(data.formation || "");
        setSkillsCsv((data.skills || []).join(", "));
        setRolesCsv((data.target_roles || []).join(", "));
        setExperiences(Array.isArray(data.experiences) ? data.experiences : []);
        setCvUrl(data.cv_url || "");
        setSavedAt(data.updated_at || null);
      } catch (e: any) {
        if (!abort) setError(e?.message || "Erreur lors du chargement du profil");
      } finally {
        if (!abort) setLoaded(true);
      }
    })();
    return () => { abort = true; };
  }, []);

  const addExperience = () => {
    setExperiences((prev) => [...prev, { title: "", company: "", years: "", description: "" }]);
  };

  const removeExperience = (idx: number) => {
    setExperiences((prev) => prev.filter((_, i) => i !== idx));
  };

  const updateExperience = (idx: number, patch: Partial<ExperienceItem>) => {
    setExperiences((prev) => prev.map((e, i) => (i === idx ? { ...e, ...patch } : e)));
  };

  const onSave = async () => {
    setError(null);
    if (!fullName.trim()) { setError("Le nom complet est obligatoire."); return; }
    if (splitCsv(skillsCsv).length === 0) { setError("Ajoute au moins une competence."); return; }
    setSaving(true);
    const payload: ProfilePayload = {
      full_name: fullName.trim(),
      email: email.trim(),
      phone: phone.trim(),
      city: city.trim(),
      formation: formation.trim(),
      skills: splitCsv(skillsCsv),
      target_roles: splitCsv(rolesCsv),
      experiences: experiences
        .filter((e) => (e.title || "").trim() || (e.company || "").trim())
        .map((e) => ({
          title: (e.title || "").trim(),
          company: (e.company || "").trim(),
          years: typeof e.years === "string" ? (Number(e.years) || 0) : e.years,
          description: (e.description || "").trim(),
        })),
      cv_url: cvUrl.trim(),
    };
    try {
      const r = await fetch(API.profile.save, {
        method: "POST",
        headers: devAuthHeaders("user"),
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const txt = await r.text();
        throw new Error(`HTTP ${r.status} - ${txt || "echec de l'enregistrement"}`);
      }
      const data = await r.json();
      setSavedAt(data?.profile?.updated_at || new Date().toISOString());
      // Petit delai pour montrer le check vert puis rediriger
      setTimeout(() => router.push("/emploi"), 600);
    } catch (e: any) {
      setError(e?.message || "Erreur lors de l'enregistrement du profil");
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async () => {
    if (!confirm("Supprimer definitivement ton profil candidat ?")) return;
    setDeleting(true);
    setError(null);
    try {
      const r = await fetch(API.profile.remove, { method: "DELETE", headers: devAuthHeaders("user") });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      // Reset form
      setFullName(""); setEmail(""); setPhone(""); setCity("");
      setFormation(""); setSkillsCsv(""); setRolesCsv("");
      setExperiences([]); setCvUrl(""); setSavedAt(null);
    } catch (e: any) {
      setError(e?.message || "Erreur lors de la suppression");
    } finally {
      setDeleting(false);
    }
  };

  if (!loaded) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <div className="flex items-center gap-2 text-slate-500"><Loader2 className="w-4 h-4 animate-spin" /> Chargement du profil...</div>
      </main>
    );
  }

  const skillCount = splitCsv(skillsCsv).length;
  const roleCount = splitCsv(rolesCsv).length;

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <div className="mb-6 flex items-center gap-3">
        <Link href="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"><ArrowLeft className="w-4 h-4" /> Accueil</Link>
      </div>

      <header className="mb-8">
        <div className="flex items-center gap-3">
          <UserCircle2 className="w-7 h-7 text-indigo-500" />
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Mon profil candidat</h1>
        </div>
        <p className="mt-2 text-sm text-slate-600">
          Ces informations alimentent automatiquement le pipeline Emploi pour faire matcher tes competences avec les offres et generer un CV adapte.
        </p>
        {savedAt ? (
          <div className="mt-3 inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5" /> Profil sauvegarde - {new Date(savedAt).toLocaleString("fr-FR")}
          </div>
        ) : null}
      </header>

      {error ? (
        <div className="mb-6 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <div>{error}</div>
        </div>
      ) : null}

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-5">
        <h2 className="text-lg font-medium text-slate-900">Identite</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Nom complet *" icon={<UserCircle2 className="w-4 h-4" />}>
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Alice Martin"
                   className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-indigo-500" />
          </Field>
          <Field label="Email" icon={<Mail className="w-4 h-4" />}>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="alice@exemple.com"
                   className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-indigo-500" />
          </Field>
          <Field label="Telephone" icon={<Phone className="w-4 h-4" />}>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+33 6 12 34 56 78"
                   className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-indigo-500" />
          </Field>
          <Field label="Ville" icon={<MapPin className="w-4 h-4" />}>
            <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="Paris"
                   className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-indigo-500" />
          </Field>
        </div>
      </section>

      <div className="mt-6"><CVUpload /></div>

        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-5">
        <h2 className="text-lg font-medium text-slate-900">Formation et objectifs</h2>
        <Field label="Formation" icon={<GraduationCap className="w-4 h-4" />}>
          <input value={formation} onChange={(e) => setFormation(e.target.value)} placeholder="M2 Data Science - Universite Paris-Saclay"
                 className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-indigo-500" />
        </Field>
        <Field label="Postes recherches (separes par virgule)" icon={<Briefcase className="w-4 h-4" />} hint={roleCount > 0 ? `${roleCount} poste${roleCount > 1 ? "s" : ""}` : "Ex : Data Scientist, ML Engineer"}>
          <textarea value={rolesCsv} onChange={(e) => setRolesCsv(e.target.value)} rows={2}
                    placeholder="Data Scientist, ML Engineer, Data Analyst"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-indigo-500" />
        </Field>
        <Field label="Competences (separees par virgule) *" icon={<Sparkles className="w-4 h-4" />} hint={skillCount > 0 ? `${skillCount} competence${skillCount > 1 ? "s" : ""}` : "Ex : Python, SQL, TensorFlow, Docker, AWS"}>
          <textarea value={skillsCsv} onChange={(e) => setSkillsCsv(e.target.value)} rows={3}
                    placeholder="Python, SQL, TensorFlow, Docker, AWS"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-indigo-500" />
        </Field>
        <Field label="Lien vers ton CV en ligne (optionnel)" icon={<Sparkles className="w-4 h-4" />}>
          <input value={cvUrl} onChange={(e) => setCvUrl(e.target.value)} placeholder="https://..."
                 className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-indigo-500" />
        </Field>
      </section>

      <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-slate-900">Experiences</h2>
          <button type="button" onClick={addExperience}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-slate-200 text-sm font-medium text-slate-700 hover:border-indigo-400 hover:text-indigo-700">
            + Ajouter une experience
          </button>
        </div>
        {experiences.length === 0 ? (
          <p className="text-sm text-slate-500">Aucune experience renseignee pour l instant. Clique sur Ajouter une experience pour en creer une.</p>
        ) : (
          <div className="space-y-3">
            {experiences.map((exp, idx) => (
              <div key={idx} className="rounded-xl border border-slate-200 p-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <input value={exp.title} onChange={(e) => updateExperience(idx, { title: e.target.value })}
                         placeholder="Poste (ex : Data Scientist Junior)"
                         className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-indigo-500" />
                  <input value={exp.company} onChange={(e) => updateExperience(idx, { company: e.target.value })}
                         placeholder="Entreprise"
                         className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-indigo-500" />
                  <input type="number" min={0} value={exp.years} onChange={(e) => updateExperience(idx, { years: e.target.value })}
                         placeholder="Annees"
                         className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-indigo-500" />
                </div>
                <textarea value={exp.description} onChange={(e) => updateExperience(idx, { description: e.target.value })}
                          rows={2} placeholder="Decris brievement tes realisations, outils utilises et contexte du poste."
                          className="mt-3 w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-indigo-500" />
                <div className="mt-2 flex justify-end">
                  <button type="button" onClick={() => removeExperience(idx)}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs text-rose-600 hover:text-rose-700">
                    <Trash2 className="w-3.5 h-3.5" /> Retirer
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="mt-8 flex items-center justify-between gap-3">
        <button type="button" onClick={onDelete} disabled={deleting}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-rose-200 text-rose-700 text-sm font-medium hover:bg-rose-50 disabled:opacity-50">
          <Trash2 className="w-4 h-4" /> {deleting ? "Suppression en cours..." : "Supprimer mon profil"}
        </button>
        <button type="button" onClick={onSave} disabled={saving}
                className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 disabled:opacity-50">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? "Enregistrement..." : "Enregistrer et utiliser ce profil"}
        </button>
      </div>
    </main>
  );
}

function Field(props: { label: string; icon?: React.ReactNode; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="flex items-center justify-between mb-1.5">
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600">{props.icon}{props.label}</span>
        {props.hint ? <span className="text-xs text-slate-400">{props.hint}</span> : null}
      </div>
      {props.children}
    </label>
  );
}
