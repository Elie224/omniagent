import Link from "next/link";

// Vague B : focus Emploi. Les modules marketing et recouvrement ont ete retires du repo.
const MODULES = [
  { href: "/emploi", title: "Emploi", description: "Recherche d'offres sur LinkedIn, Indeed, HelloWork, et plus. Candidature assistee par IA.", icon: "🎯" },
  { href: "/candidatures", title: "Candidatures", description: "Suis toutes tes candidatures : statut, contacts et relances automatiques.", icon: "💼" },
  { href: "/profil", title: "Mon profil", description: "Configure ton profil candidat : competences, experiences et postes cibles.", icon: "👤" },
  { href: "/business", title: "Business", description: "Tableau de bord observabilite : couts, latence et valeur metier.", icon: "📊" },
];

export default function Home() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-16">
      <header className="mb-12">
        <h1 className="text-4xl font-bold tracking-tight text-brand-700">OmniAgent</h1>
        <p className="mt-2 text-lg text-slate-600">Orchestrateur multi-plateformes pilote par l 'IA.</p>
      </header>
      <section className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {MODULES.map((m) => (
          <Link key={m.href} href={m.href} className="group rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition hover:border-brand-500 hover:shadow-md">
            <div className="mb-3 text-3xl">{m.icon}</div>
            <h2 className="text-xl font-semibold text-slate-900 group-hover:text-brand-700">{m.title}</h2>
            <p className="mt-2 text-sm text-slate-600">{m.description}</p>
          </Link>
        ))}
      </section>
    </main>
  );
}