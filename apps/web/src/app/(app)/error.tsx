"use client";

import Link from "next/link";
import { AlertTriangle, RefreshCcw, Home } from "lucide-react";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto max-w-2xl px-4 py-16 sm:px-6 lg:px-8">
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-8 shadow-sm dark:border-rose-500/40 dark:bg-rose-500/10">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-6 w-6 shrink-0 text-rose-600" />
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-semibold text-rose-800 dark:text-rose-200">Une erreur est survenue</h1>
            <p className="mt-2 text-sm text-rose-700 dark:text-rose-300">
              {error?.message || "Erreur inattendue cote client."}
            </p>
            {error?.digest ? (
              <p className="mt-1 text-xs text-rose-600/70">Reference : {error.digest}</p>
            ) : null}
            <div className="mt-5 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={reset}
                className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-700"
              >
                <RefreshCcw className="h-4 w-4" /> Reessayer
              </button>
              <Link
                href="/"
                className="inline-flex items-center gap-2 rounded-lg border border-rose-300 bg-white px-3 py-1.5 text-sm font-medium text-rose-700 hover:bg-rose-50"
              >
                <Home className="h-4 w-4" /> Retour a l accueil
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}