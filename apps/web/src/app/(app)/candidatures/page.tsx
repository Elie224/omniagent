"use client";

import Link from "next/link";
import { ArrowLeft, Briefcase } from "lucide-react";
import { ApplicationsBoard } from "../emploi/ApplicationsBoard";

export default function CandidaturesPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-10 space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700">
          <ArrowLeft className="w-4 h-4" /> Accueil
        </Link>
        <Link href="/emploi" className="text-sm text-slate-500 hover:text-slate-700">
          Lancer une mission
        </Link>
      </div>

      <header>
        <div className="flex items-center gap-3">
          <Briefcase className="w-7 h-7 text-indigo-500" />
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Mes candidatures</h1>
        </div>
        <p className="mt-2 text-sm text-slate-600">
          Suivi de toutes les candidatures que tu as envoyees ou ajoutees manuellement.
          Tu peux filtrer par statut, modifier une fiche ou en ajouter une nouvelle.
        </p>
      </header>

      <ApplicationsBoard />
    </div>
  );
}
