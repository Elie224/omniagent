"use client";

// Password strength meter minimal (cote client uniquement).
// Score 0..4 base sur : longueur, diversite (lower/upper/digit/symbol).
// Pas de calcul de zxcvbn (volontairement zero-dep) ; ce meter reste indicatif.

import { Check, X } from "lucide-react";
import { useMemo } from "react";

interface Props {
  password: string;
  className?: string;
}

interface Rule {
  label: string;
  test: (s: string) => boolean;
}

const RULES: Rule[] = [
  { label: "Au moins 8 caracteres", test: (s) => s.length >= 8 },
  { label: "Une lettre majuscule", test: (s) => /[A-Z]/.test(s) },
  { label: "Un chiffre",            test: (s) => /\d/.test(s) },
  { label: "Un caractere special",  test: (s) => /[^A-Za-z0-9]/.test(s) },
];

const LEVELS = [
  { min: 0, label: "Trop faible", color: "bg-rose-500",    text: "text-rose-600" },
  { min: 1, label: "Faible",      color: "bg-rose-400",    text: "text-rose-600" },
  { min: 2, label: "Correct",     color: "bg-amber-400",   text: "text-amber-600" },
  { min: 3, label: "Bon",         color: "bg-emerald-400", text: "text-emerald-600" },
  { min: 4, label: "Excellent",   color: "bg-emerald-500", text: "text-emerald-700" },
];

export function PasswordStrengthMeter({ password, className }: Props) {
  const results = useMemo(() => RULES.map((r) => ({ ...r, ok: r.test(password) })), [password]);
  const score = results.filter((r) => r.ok).length;
  const level = LEVELS[Math.min(score, LEVELS.length - 1)];

  if (!password) return null;

  return (
    <div className={"mt-2 space-y-2 " + (className || "")}>
      <div className="flex items-center gap-2">
        <div className="flex flex-1 gap-1">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className={
                "h-1.5 flex-1 rounded-full transition-colors " +
                (i < score ? level.color : "bg-slate-200 dark:bg-slate-700")
              }
            />
          ))}
        </div>
        <span className={"text-xs font-medium " + level.text}>{level.label}</span>
      </div>
      <ul className="grid grid-cols-1 gap-1 text-xs sm:grid-cols-2">
        {results.map((r) => (
          <li key={r.label} className="flex items-center gap-1.5 text-slate-500">
            {r.ok ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <X className="h-3.5 w-3.5 text-slate-300" />}
            <span className={r.ok ? "text-slate-700 dark:text-slate-200" : ""}>{r.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}