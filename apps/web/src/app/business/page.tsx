"use client";
import { useEffect, useState } from "react";
import { devAuthHeaders } from "@/lib/api";

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
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e: any) {
      setError(e.message ?? "Erreur");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <header className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold text-brand-700">Tableau de bord activite</h1>
          <p className="mt-1 text-sm text-slate-500">
            Espace de travail : <code>{data?.tenant_id ?? "?"}</code> - perimetre : <code>{data?.scope ?? "?"}</code>
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="rounded bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {loading ? "Chargement..." : "Actualiser"}
        </button>
      </header>

      {error && <p className="mb-4 text-sm text-red-600">Erreur : {error}</p>}

      {data && (
        <>
          <section className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
            <Stat label="Executions" value={data.total_runs} />
            <Stat label="Reussites" value={data.total_success} />
            <Stat label="Taux global de reussite" value={`${Math.round(data.global_success_rate * 100)}%`} />
            <Stat label="Cout LLM" value={`$${data.total_cost_usd.toFixed(4)}`} />
          </section>

          <section>
            <h2 className="mb-3 text-xl font-semibold">Repartition par agent</h2>
            {data.agents.length === 0 ? (
              <p className="text-sm text-slate-500">
                Aucun agent enregistre. Lance l'orchestrateur depuis la home pour voir les metriques remonter.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead className="border-b text-left text-slate-600">
                  <tr>
                    <th className="py-2">Agent</th>
                    <th className="py-2 text-right">Runs</th>
                    <th className="py-2 text-right">Succes</th>
                    <th className="py-2 text-right">Latence moyenne</th>
                    <th className="py-2 text-right">Fiabilite</th>
                    <th className="py-2 text-right">Anomalies detectees</th>
                  </tr>
                </thead>
                <tbody>
                  {data.agents.map((a) => (
                    <tr key={a.agent} className="border-b">
                      <td className="py-2 font-mono">{a.agent}</td>
                      <td className="py-2 text-right">{a.runs}</td>
                      <td className="py-2 text-right">{Math.round(a.success_rate * 100)}%</td>
                      <td className="py-2 text-right">{a.avg_duration_ms.toFixed(1)} ms</td>
                      <td className="py-2 text-right">{Math.round(a.reliability_score * 100)}%</td>
                      <td className="py-2 text-right">{a.anomalies}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded border border-slate-200 bg-white p-4">
      <div className="text-xs uppercase text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
    </div>
  );
}