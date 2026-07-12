"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Mail, Lock, Building2, User as UserIcon, AlertTriangle, Loader2, ArrowRight } from "lucide-react";
import { signup } from "@/lib/auth";

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
      router.push("/profil");
    } catch (e: any) {
      setError(e?.message || "Inscription impossible.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-slate-900">Creer mon compte</h2>
        <p className="mt-1 text-sm text-slate-500">Inscription gratuite, en moins d'une minute.</p>
      </div>

      {error ? (
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </div>
      ) : null}

      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Email" icon={<Mail className="h-4 w-4" />}>
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="alice@exemple.com"
            className="w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
          />
        </Field>

        <Field label="Mot de passe (min. 8 caracteres)" icon={<Lock className="h-4 w-4" />}>
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="********"
            className="w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
          />
        </Field>

        <Field label="Nom affiche (optionnel)" icon={<UserIcon className="h-4 w-4" />}>
          <input
            type="text"
            autoComplete="nickname"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Alice Martin"
            className="w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
          />
        </Field>

        <Field label="Nom de l organisation" icon={<Building2 className="h-4 w-4" />}>
          <input
            type="text"
            required
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
            placeholder="Mon espace candidat"
            className="w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
          />
        </Field>

        <button
          type="submit"
          disabled={loading}
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 disabled:opacity-60"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Creer mon compte
          {!loading ? <ArrowRight className="h-4 w-4" /> : null}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-500">
        Deja un compte ?{" "}
        <Link href="/auth/login" className="font-medium text-indigo-600 hover:text-indigo-700">
          Se connecter
        </Link>
      </p>
    </div>
  );
}

function Field({ label, icon, children }: { label: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">{label}</span>
      <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 focus-within:border-indigo-400 focus-within:bg-white">
        {icon ? <span className="text-slate-400">{icon}</span> : null}
        {children}
      </div>
    </label>
  );
}