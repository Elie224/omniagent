import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "OmniAgent",
  description: "Plateforme SaaS d'agents IA specialisee emploi",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="bg-slate-50 text-slate-900 antialiased">{children}</body>
    </html>
  );
}