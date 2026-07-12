// Layout partage pour toutes les pages internes (non auth).
// Ce route group (app) est invisible dans l URL mais permet d envelopper
// toutes les pages Emploi / Candidatures / Profil / Business avec AppShell.
//
// Note : la racine src/app/layout.tsx reste minimale et sert les pages /auth/*.

import { AppShell } from "@/components/AppShell";
import { ToastHost } from "@/components/Toast";

export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell>
      {children}
      <ToastHost />
    </AppShell>
  );
}