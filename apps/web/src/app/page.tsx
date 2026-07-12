import Link from "next/link";
import {
  Briefcase, ClipboardList, User, LayoutDashboard, ArrowRight,
  Sparkles, ShieldCheck, Zap, Target, Globe, CheckCircle2,
} from "lucide-react";

const MODULES = [
  { href: "/emploi", title: "Recherche emploi", icon: Briefcase, tone: "from-indigo-500 to-violet-600", description: "Orchestrateur multi-sources (LinkedIn, Indeed, HelloWork, WTTJ, France Travail, Adzuna) avec filtrage intelligent et matching profil/offre." },
  { href: "/candidatures", title: "Candidatures", icon: ClipboardList, tone: "from-sky-500 to-cyan-600", description: "Suivi centralise de toutes tes candidatures : statut, notes, contacts et plan de relance." },
  { href: "/profil", title: "Mon profil", icon: User, tone: "from-emerald-500 to-teal-600", description: "Configure ton profil candidat : competences, experiences, postes cibles et televersement de CV." },
  { href: "/business", title: "Observabilite", icon: LayoutDashboard, tone: "from-amber-500 to-orange-600", description: "Tableau de bord metier : couts LLM, fiabilite des agents, taux de succes et valeur business." },
];

const VALUE_PROPS = [
  { icon: Zap, title: "Rapide", description: "Recherche sur 6 plateformes en parallele, score de matching et generation de CV en moins de 30 secondes." },
  { icon: Target, title: "Pertinent", description: "Algorithme de scoring base sur competences, localisation, contrat et annees d experience." },
  { icon: ShieldCheck, title: "Multi-tenant", description: "Isolation stricte par tenant, idempotence des workflows et circuit breaker sur les connecteurs externes." },
  { icon: Globe, title: "Multi-sources", description: "Connecteurs unifies pour LinkedIn, Indeed, HelloWork, Welcome to the Jungle, France Travail et Adzuna." },
];

const STATS = [
  { value: "19", label: "agents specialises" },
  { value: "6",  label: "sources d offres integrees" },
  { value: "<30s", label: "temps de recherche median" },
  { value: "100%", label: "isolation par tenant" },
];

export default function Home() {
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10">
          <div className="absolute -top-40 left-1/2 h-[500px] w-[900px] -translate-x-1/2 rounded-full bg-gradient-to-tr from-indigo-200/40 via-violet-200/30 to-transparent blur-3xl dark:from-indigo-500/20 dark:via-violet-500/10" />
        </div>
        <div className="mx-auto max-w-7xl px-4 pb-16 pt-20 sm:px-6 sm:pt-28 lg:px-8 lg:pt-32">
          <div className="mx-auto max-w-3xl text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-300">
              <Sparkles className="h-3.5 w-3.5" />
              Orchestrateur V3 - multi-agents specialise emploi
            </div>
            <h1 className="mt-6 text-4xl font-bold tracking-tight text-slate-900 dark:text-white sm:text-5xl lg:text-6xl">
              Ton copilote IA pour{" "}
              <span className="bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 bg-clip-text text-transparent">
                candidater plus vite
              </span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-slate-600 dark:text-slate-300">
              OmniAgent automatise la recherche d emploi, le matching profil/offre, la generation de CV adapte et le suivi
              de toutes tes candidatures - sur les 6 principales plateformes francaises.
            </p>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/emploi"
                className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-600/20 transition hover:bg-indigo-700"
              >
                Lancer une recherche <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/profil"
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 hover:border-indigo-300 hover:text-indigo-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:border-indigo-400 dark:hover:text-indigo-300"
              >
                Configurer mon profil
              </Link>
            </div>
          </div>

          {/* Stats */}
          <div className="mx-auto mt-16 grid max-w-4xl grid-cols-2 gap-4 sm:grid-cols-4">
            {STATS.map((s) => (
              <div key={s.label} className="rounded-2xl border border-slate-200 bg-white/60 p-4 text-center backdrop-blur dark:border-slate-800 dark:bg-slate-900/60">
                <div className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">{s.value}</div>
                <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Modules */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Quatre modules, un seul workflow</h2>
          <p className="mt-3 text-base text-slate-600 dark:text-slate-300">
            De la recherche initiale jusqu a l analyse de performance, tout est orchestre par les memes agents IA.
          </p>
        </div>
        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-2">
          {MODULES.map((m) => {
            const Icon = m.icon;
            return (
              <Link
                key={m.href}
                href={m.href}
                className="group card-hover relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
              >
                <div className={"absolute right-0 top-0 h-24 w-24 rounded-full bg-gradient-to-br opacity-10 blur-2xl transition group-hover:opacity-20 " + m.tone} />
                <div className={"mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-md " + m.tone}>
                  <Icon className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-semibold text-slate-900 group-hover:text-indigo-700 dark:text-white dark:group-hover:text-indigo-300">
                  {m.title}
                </h3>
                <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">{m.description}</p>
                <div className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-indigo-600 opacity-0 transition group-hover:opacity-100 dark:text-indigo-400">
                  Ouvrir <ArrowRight className="h-3.5 w-3.5" />
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      {/* Value props */}
      <section className="bg-white py-16 dark:bg-slate-900/50">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Pourquoi OmniAgent</h2>
            <p className="mt-3 text-base text-slate-600 dark:text-slate-300">
              Une plateforme concue pour les candidats qui visent l excellence - pas pour ceux qui spamment 200 offres.
            </p>
          </div>
          <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {VALUE_PROPS.map((v) => {
              const Icon = v.icon;
              return (
                <div key={v.title} className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
                  <Icon className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
                  <h3 className="mt-3 text-base font-semibold text-slate-900 dark:text-white">{v.title}</h3>
                  <p className="mt-1.5 text-sm text-slate-600 dark:text-slate-300">{v.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-600 via-violet-600 to-fuchsia-600 p-10 shadow-2xl sm:p-14">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight text-white">Pret a candidater 10x plus vite ?</h2>
            <p className="mt-4 text-lg text-indigo-100">
              Cree ton profil en 2 minutes et lance ta premiere recherche multi-sources.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/profil"
                className="inline-flex items-center gap-2 rounded-lg bg-white px-5 py-3 text-sm font-semibold text-indigo-700 shadow-md hover:bg-indigo-50"
              >
                Creer mon profil <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/emploi"
                className="inline-flex items-center gap-2 rounded-lg border border-white/30 bg-white/10 px-5 py-3 text-sm font-semibold text-white backdrop-blur hover:bg-white/20"
              >
                Voir une demo
              </Link>
            </div>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-indigo-100">
              <span className="inline-flex items-center gap-1.5"><CheckCircle2 className="h-4 w-4" /> Sans carte bancaire</span>
              <span className="inline-flex items-center gap-1.5"><CheckCircle2 className="h-4 w-4" /> Multi-tenant securise</span>
              <span className="inline-flex items-center gap-1.5"><CheckCircle2 className="h-4 w-4" /> Isolation par organisation</span>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}