// Sparkline : mini graphique SVG line/area pour les KPI cards.
// Pas de dependance externe, juste SVG inline.
// Props : values (numeriques), width/height en px, couleur de trait, area optionnelle.

import { cn } from "@/lib/cn";

interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  stroke?: string;
  fill?: string;
  className?: string;
  showArea?: boolean;
}

export function Sparkline({
  values,
  width = 120,
  height = 32,
  stroke = "#6366f1",
  fill = "rgba(99,102,241,0.15)",
  className,
  showArea = true,
}: SparklineProps) {
  if (!values || values.length === 0) {
    return (
      <svg width={width} height={height} className={cn("text-slate-300", className)} aria-hidden="true">
        <line x1={0} y1={height - 1} x2={width} y2={height - 1} stroke="currentColor" strokeWidth={1} strokeDasharray="3 3" />
      </svg>
    );
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = values.length > 1 ? width / (values.length - 1) : width;
  const pad = 2;
  const innerH = height - pad * 2;

  const points = values.map((v, i) => {
    const x = i * stepX;
    const y = pad + innerH - ((v - min) / range) * innerH;
    return { x, y };
  });

  const linePath = points.map((p, i) => (i === 0 ? `M ${p.x},${p.y}` : `L ${p.x},${p.y}`)).join(" ");
  const areaPath = `${linePath} L ${points[points.length - 1].x},${height} L 0,${height} Z`;

  const last = points[points.length - 1];

  return (
    <svg width={width} height={height} className={cn("block", className)} aria-hidden="true">
      {showArea ? <path d={areaPath} fill={fill} /> : null}
      <path d={linePath} fill="none" stroke={stroke} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={last.x} cy={last.y} r={2.5} fill={stroke} />
    </svg>
  );
}

// Badge de fiabilite : vert / ambre / rouge selon le score 0..1.
export function ReliabilityBadge({ value }: { value: number }) {
  const pct = Math.round((value || 0) * 100);
  const color =
    pct >= 90 ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/40"
    : pct >= 70 ? "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/40"
    : "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-500/40";
  const label = pct >= 90 ? "Excellent" : pct >= 70 ? "Correct" : "Fragile";
  return (
    <span className={"inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium " + color}>
      <span className="inline-block h-1.5 w-1.5 rounded-full bg-current" />
      {pct}% - {label}
    </span>
  );
}