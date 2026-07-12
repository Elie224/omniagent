import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-[60vh] max-w-2xl flex-col items-center justify-center px-4 py-16 text-center sm:px-6 lg:px-8">
      <p className="text-sm font-semibold uppercase tracking-wider text-indigo-600">404</p>
      <h1 className="mt-3 text-4xl font-bold tracking-tight text-slate-900 dark:text-white">Page introuvable</h1>
      <p className="mt-3 text-base text-slate-600 dark:text-slate-300">
        Cette page n existe pas ou a ete deplacee. Verifie l URL ou reviens a l accueil.
      </p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700"
        >
          Retour a l accueil
        </Link>
        <Link
          href="/emploi"
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:border-indigo-300 hover:text-indigo-700"
        >
          Lancer une recherche
        </Link>
      </div>
    </main>
  );
}