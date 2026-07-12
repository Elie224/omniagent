"use client";

// Toast notifications minimales. Auto-dismiss apres `duration` ms.
// API imperative via window.dispatchEvent(new CustomEvent("omniagent:toast", {detail: {...}}))

import { useEffect, useState, useCallback } from "react";
import { CheckCircle2, AlertTriangle, Info, XCircle, X } from "lucide-react";

export type ToastKind = "success" | "error" | "info" | "warning";

export interface ToastInput {
  kind?: ToastKind;
  title?: string;
  message: string;
  duration?: number;
}

interface ToastItem extends ToastInput {
  id: string;
}

const ICONS: Record<ToastKind, React.ComponentType<{ className?: string }>> = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
  warning: AlertTriangle,
};

const KIND_STYLES: Record<ToastKind, string> = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200",
  error: "border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200",
  info: "border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-sky-200",
  warning: "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200",
};

export function toast(input: ToastInput) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<ToastInput>("omniagent:toast", { detail: input }));
}

export function ToastHost() {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  useEffect(() => {
    function onToast(e: Event) {
      const detail = (e as CustomEvent<ToastInput>).detail;
      if (!detail?.message) return;
      const id = Math.random().toString(36).slice(2, 10);
      const duration = detail.duration ?? 3500;
      setItems((prev) => [...prev, { ...detail, id }]);
      if (duration > 0) {
        window.setTimeout(() => dismiss(id), duration);
      }
    }
    window.addEventListener("omniagent:toast", onToast as EventListener);
    return () => window.removeEventListener("omniagent:toast", onToast as EventListener);
  }, [dismiss]);

  if (items.length === 0) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4 sm:bottom-6">
      {items.map((t) => {
        const Icon = ICONS[t.kind ?? "info"];
        return (
          <div
            key={t.id}
            role="status"
            className={
              "pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border px-4 py-3 shadow-lg animate-fade-in " +
              (KIND_STYLES[t.kind ?? "info"])
            }
          >
            <Icon className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="flex-1 min-w-0">
              {t.title ? <div className="text-sm font-semibold">{t.title}</div> : null}
              <div className="text-sm">{t.message}</div>
            </div>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              aria-label="Fermer"
              className="ml-1 rounded p-0.5 opacity-70 hover:opacity-100"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}