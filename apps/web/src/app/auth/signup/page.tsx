"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Mail, Lock, Building2, User as UserIcon, AlertTriangle, Loader2, ArrowRight, Sparkles } from "lucide-react";
import { signup } from "@/lib/auth";
import { PasswordStrengthMeter } from "@/components/PasswordStrengthMeter";
import { toast } from "@/components/Toast";
export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email || !password || !orgName) {
      setError("Email, mot de passe et nom de l organisation sont requis.");
      return;
    }
    if (password.length < 8) {
      setError("Le mot de passe doit faire au moins 8 caracteres.");
      return;
    }
    setLoading(true);
    try {
      await signup({ email, password, display_name: displayName, org_name: orgName });
      toast({ kind: "success", title: "Compte cree", message: "Bienvenue sur OmniAgent." });
      router.push("/profil");
    } catch (e: any) {
      setError(e?.message || "Inscription impossible.");
      toast({ kind: "error", title: "Inscription impossible", message: e?.message || "Reessaie avec un autre email." });
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="mb-6">
        <div className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-md">
          <Sparkles className="h-5 w-5" />
        </div>
        <h2 className="mt-3 text-xl font-semibold text-slate-900 dark:text-white">Creer mon compte</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Inscription gratuite, en moins d une minute.</p>
      </div>

      {error ? (
        <div role="alert" className="mb-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </div>
      ) : null}

      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Email" icon={<Mail className="h-4 w-4" />}>
          <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="alice@exemple.com" className="w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400 dark:text-white" />
        </Field>

        <div>
          <Field label="Mot de passe" icon={<Lock className="h-4 w-4" />}>
            <input type="password" autoComplete="new-password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="********" className="w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400 dark:text-white" />
          </Field>
          <PasswordStrengthMeter password={password} />
        </div>

        <Field label="Nom affiche (optionnel)" icon={<UserIcon className="h-4 w-4" />}>
          <input type="text" autoComplete="nickname" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Alice Martin" className="w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400 dark:text-white" />
        </Field>

        <Field label="Nom de l organisation" icon={<Building2 className="h-4 w-4" />}>
          <input type="text" required value={orgName} onChange={(e) => setOrgName(e.target.value)} placeholder="Mon espace candidat" className="w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400 dark:text-white" />
        </Field>

        <button type="submit" disabled={loading} className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-indigo-700 disabled:opacity-60">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Creer mon compte
          {!loading ? <ArrowRight className="h-4 w-4" /> : null}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-500 dark:text-slate-400">
        Deja un compte ?{" "}
        <Link href="/auth/login" className="font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">Se connecter</Link>
      </p>
    </div>
  );
}

function Field({ label, icon, children }: { label: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</span>
      <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 focus-within:border-indigo-400 focus-within:bg-white dark:border-slate-700 dark:bg-slate-800 dark:focus-within:bg-slate-800/80">
        {icon ? <span className="text-slate-400">{icon}</span> : null}
        {children}
      </div>
    </label>
  );
}