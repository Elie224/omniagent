"use client";

import { useEffect, useState } from "react";
import { Loader2, RefreshCcw, TrendingUp, DollarSign, CheckCircle2, Activity, AlertTriangle } from "lucide-react";
import { devAuthHeaders } from "@/lib/api";
import { Sparkline, ReliabilityBadge } from "@/components/Sparkline";
import { Skeleton, SkeletonKPI } from "@/components/Skeleton";
import { toast } from "@/components/Toast";

interface AgentScore {
  agent: string;
  runs: number;
  success_rate: number;
  avg_duration_ms: number;
  cost_per_success: number;
  reliability_score: number;
  business_value: number;
  anomalies: number;
}

interface BusinessDashboard {
  tenant_id: string;
  scope: string;
  total_cost_usd: number;
  total_runs: number;
  total_success: number;
  global_success_rate: number;
  agents: AgentScore[];
}

export default function BusinessPage() {
  const [data, setData] = useState<BusinessDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/api/v1/shared/business-dashboard", {
        headers: devAuthHeaders("admin"),
        cache: "no-store",
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e: any) {
      setError(e?.message ?? "Erreur");
      toast({ kind: "error", title: "Chargement impossible", message: e?.message ?? "Erreur" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Tableau de bord activite</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Espace de travail : <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">{data?.tenant_id ?? "-"}</code>
            {" - "}
            perimetre : <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">{data?.scope ?? "-"}</code>
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm hover:border-indigo-300 hover:text-indigo-700 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
          {loading ? "Chargement..." : "Actualiser"}
        </button>
      </header>

      {error ? (
        <div className="mb-6 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </div>
      ) : null}

      {!data && loading ? (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <SkeletonKPI /><SkeletonKPI /><SkeletonKPI /><SkeletonKPI />
          </div>
          <div className="mt-8 space-y-3">
            <Skeleton className="h-10 w-1/3" />
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        </>
      ) : null}

      {data ? (
        <>
          {/* KPI cards avec sparkline */}
          <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <KpiCard
              label="Executions totales"
              value={data.total_runs.toString()}
              icon={<Activity className="h-4 w-4" />}
              series={generateSeries(data.total_runs, 12)}
              tone="indigo"
            />
            <KpiCard
              label="Reussites"
              value={data.total_success.toString()}
              icon={<CheckCircle2 className="h-4 w-4" />}
              series={generateSeries(data.total_success, 12)}
              tone="emerald"
            />
            <KpiCard
              label="Taux de reussite"
              value={`${Math.round(data.global_success_rate * 100)}%`}
              icon={<TrendingUp className="h-4 w-4" />}
              series={generatePctSeries(data.global_success_rate, 12)}
              tone="violet"
            />
            <KpiCard
              label="Cout LLM"
              value={`$${data.total_cost_usd.toFixed(4)}`}
              icon={<DollarSign className="h-4 w-4" />}
              series={generateSeries(data.total_cost_usd * 100, 12)}
              tone="amber"
            />
          </section>

          {/* Repartition par agent */}
          <section className="mt-10">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Repartition par agent</h2>
              <span className="text-xs text-slate-500 dark:text-slate-400">{data.agents.length} agent(s) enregistre(s)</span>
            </div>

            {data.agents.length === 0 ? (
              <div className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-900">
                <Activity className="mx-auto h-8 w-8 text-slate-400" />
                <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
                  Aucun agent enregistre. Lance l orchestrateur depuis la page Emploi pour voir les metriques remonter.
                </p>
              </div>
            ) : (
              <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <table className="w-full text-sm">
                  <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
                    <tr>
                      <th className="px-4 py-3">Agent</th>
                      <th className="px-4 py-3 text-right">Runs</th>
                      <th className="px-4 py-3 text-right">Succes</th>
                      <th className="px-4 py-3 text-right">Latence moy.</th>
                      <th className="px-4 py-3 text-right">Fiabilite</th>
                      <th className="px-4 py-3 text-right">Anomalies</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {data.agents.map((a) => (
                      <tr key={a.agent} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                        <td className="px-4 py-3 font-mono text-xs text-slate-800 dark:text-slate-200">{a.agent}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{a.runs}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{Math.round(a.success_rate * 100)}%</td>
                        <td className="px-4 py-3 text-right tabular-nums text-slate-600 dark:text-slate-300">{a.avg_duration_ms.toFixed(1)} ms</td>
                        <td className="px-4 py-3 text-right"><ReliabilityBadge value={a.reliability_score} /></td>
                        <td className="px-4 py-3 text-right tabular-nums">
                          {a.anomalies > 0 ? (
                            <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">
                              <AlertTriangle className="h-3 w-3" /> {a.anomalies}
                            </span>
                          ) : (
                            <span className="text-slate-400">0</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}

function KpiCard(props: {
  label: string;
  value: string;
  icon: React.ReactNode;
  series: number[];
  tone: "indigo" | "emerald" | "violet" | "amber";
}) {
  const colors = {
    indigo:  { stroke: "#6366f1", fill: "rgba(99,102,241,0.15)",  icon: "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300" },
    emerald: { stroke: "#10b981", fill: "rgba(16,185,129,0.15)",  icon: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300" },
    violet:  { stroke: "#8b5cf6", fill: "rgba(139,92,246,0.15)",  icon: "bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300" },
    amber:   { stroke: "#f59e0b", fill: "rgba(245,158,11,0.15)",  icon: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300" },
  }[props.tone];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{props.label}</span>
        <span className={"inline-flex h-7 w-7 items-center justify-center rounded-lg " + colors.icon}>{props.icon}</span>
      </div>
      <div className="mt-2 text-2xl font-bold tabular-nums text-slate-900 dark:text-white">{props.value}</div>
      <div className="mt-2">
        <Sparkline values={props.series} stroke={colors.stroke} fill={colors.fill} width={140} height={28} />
      </div>
    </div>
  );
}

// Helpers pour generer une mini serie stable a partir d une valeur.
// Deterministe pour eviter le shimmer aleatoire entre re-renders.
function generateSeries(seed: number, n: number): number[] {
  const arr: number[] = [];
  let v = Math.max(1, Math.round(seed / Math.max(n, 1)));
  for (let i = 0; i < n; i++) {
    v = Math.max(0, v + ((i * 7 + seed) % 5) - 2);
    arr.push(v);
  }
  return arr;
}

function generatePctSeries(seed: number, n: number): number[] {
  const arr: number[] = [];
  const target = Math.max(0, Math.min(1, seed));
  for (let i = 0; i < n; i++) {
    const noise = ((i * 13 + Math.round(seed * 100)) % 11) / 100 - 0.05;
    arr.push(Math.max(0, Math.min(1, target + noise)));
  }
  return arr;
}