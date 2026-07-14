import "./globals.css";
import type { Metadata, Viewport } from "next";
import { ToastHost } from "@/components/Toast";

export const metadata: Metadata = {
  title: "OmniAgent - Plateforme d agents IA specialisee emploi",
  description: "Orchestrateur multi-agents specialise emploi : recherche, matching, generation de CV et suivi des candidatures.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0f172a" },
  ],
};

// Script anti-flash : applique le theme avant le premier paint.
const themeBootstrap = `
(function() {
  try {
    var stored = localStorage.getItem('omniagent:theme');
    var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    var theme = stored === 'light' || stored === 'dark' ? stored : (prefersDark ? 'dark' : 'light');
    if (theme === 'dark') document.documentElement.classList.add('dark');
    document.documentElement.style.colorScheme = theme;
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <head>
        {/* Script statique local uniquement (aucune interpolation utilisateur). */}
        <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
      </head>
      <body className="bg-slate-50 text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-100">
        {children}
        <ToastHost />
      </body>
    </html>
  );
}