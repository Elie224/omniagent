"use client";

// AppShell : layout partage pour toutes les pages internes (pas /auth).
// - Header sticky avec logo, nav primaire, dark mode toggle, menu utilisateur.
// - Footer minimal (version + status).
// - Mobile : nav collapse en menu hamburger sous <md.

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Sparkles, LayoutDashboard, Briefcase, User as UserIcon, ClipboardList,
  Menu, X, LogOut, LogIn,
} from "lucide-react";
import { DarkModeToggle } from "./DarkModeToggle";
import { clearAuth, isLoggedIn, readUser } from "@/lib/auth";

type NavItem = { href: string; label: string; icon: React.ComponentType<{ className?: string }> };

const NAV: NavItem[] = [
  { href: "/emploi",        label: "Recherche emploi", icon: Briefcase },
  { href: "/candidatures",  label: "Candidatures",     icon: ClipboardList },
  { href: "/profil",        label: "Mon profil",       icon: UserIcon },
  { href: "/business",      label: "Observabilite",    icon: LayoutDashboard },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [userName, setUserName] = useState<string | null>(null);

  // Hydratation : detecte l'etat auth cote client (evite SSR mismatch).
  useEffect(() => {
    setAuthed(isLoggedIn());
    const u = readUser();
    setUserName(u?.display_name || u?.email || null);
    setHydrated(true);
  }, [pathname]);

  // Ferme le drawer mobile quand on change de route.
  useEffect(() => { setDrawerOpen(false); setUserMenuOpen(false); }, [pathname]);

  function onLogout() {
    clearAuth();
    setAuthed(false);
    setUserName(null);
    router.push("/");
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <Header
        pathname={pathname}
        hydrated={hydrated}
        authed={authed}
        userName={userName}
        userMenuOpen={userMenuOpen}
        onToggleUserMenu={() => setUserMenuOpen((v) => !v)}
        onLogout={onLogout}
        drawerOpen={drawerOpen}
        onToggleDrawer={() => setDrawerOpen((v) => !v)}
      />

      <main className="flex-1 w-full">
        {children}
      </main>

      <Footer />
    </div>
  );
}

function Header(props: {
  pathname: string;
  hydrated: boolean;
  authed: boolean;
  userName: string | null;
  userMenuOpen: boolean;
  onToggleUserMenu: () => void;
  onLogout: () => void;
  drawerOpen: boolean;
  onToggleDrawer: () => void;
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/85 backdrop-blur dark:border-slate-800 dark:bg-slate-900/85">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-sm">
            <Sparkles className="h-5 w-5" />
          </span>
          <span className="hidden text-lg tracking-tight sm:inline">OmniAgent</span>
        </Link>

        {/* Desktop nav */}
        <nav className="ml-2 hidden flex-1 items-center gap-1 md:flex">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = props.pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={
                  "inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition " +
                  (active
                    ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white")
                }
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <DarkModeToggle />

          {props.hydrated && props.authed ? (
            <div className="relative hidden md:block">
              <button
                type="button"
                onClick={props.onToggleUserMenu}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:border-indigo-300 hover:text-indigo-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300">
                  {(props.userName || "?").slice(0, 1).toUpperCase()}
                </span>
                <span className="max-w-[140px] truncate">{props.userName || "Mon compte"}</span>
              </button>
              {props.userMenuOpen ? (
                <div className="absolute right-0 mt-2 w-56 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800">
                  <Link href="/profil" className="flex items-center gap-2 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-700">
                    <UserIcon className="h-4 w-4" /> Mon profil
                  </Link>
                  <button
                    type="button"
                    onClick={props.onLogout}
                    className="flex w-full items-center gap-2 border-t border-slate-100 px-4 py-2.5 text-left text-sm text-rose-600 hover:bg-rose-50 dark:border-slate-700 dark:hover:bg-rose-500/10"
                  >
                    <LogOut className="h-4 w-4" /> Se deconnecter
                  </button>
                </div>
              ) : null}
            </div>
          ) : (
            <Link
              href="/auth/login"
              className="hidden items-center gap-2 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 md:inline-flex"
            >
              <LogIn className="h-4 w-4" /> Connexion
            </Link>
          )}

          {/* Mobile burger */}
          <button
            type="button"
            aria-label="Ouvrir le menu"
            onClick={props.onToggleDrawer}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-700 md:hidden dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
          >
            {props.drawerOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {props.drawerOpen ? (
        <div className="border-t border-slate-200 bg-white md:hidden dark:border-slate-800 dark:bg-slate-900">
          <nav className="mx-auto flex max-w-7xl flex-col gap-1 px-4 py-3">
            {NAV.map((item) => {
              const Icon = item.icon;
              const active = props.pathname?.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={
                    "inline-flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium " +
                    (active
                      ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300"
                      : "text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800")
                  }
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
            <div className="my-2 border-t border-slate-100 dark:border-slate-800" />
            {props.hydrated && props.authed ? (
              <button
                type="button"
                onClick={props.onLogout}
                className="inline-flex items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-500/10"
              >
                <LogOut className="h-4 w-4" /> Se deconnecter
              </button>
            ) : (
              <Link
                href="/auth/login"
                className="inline-flex items-center gap-3 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white"
              >
                <LogIn className="h-4 w-4" /> Connexion
              </Link>
            )}
          </nav>
        </div>
      ) : null}
    </header>
  );
}

function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-2 px-4 py-6 text-xs text-slate-500 sm:flex-row sm:items-center sm:px-6 lg:px-8 dark:text-slate-400">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          OmniAgent - plateforme SaaS d&apos;agents IA specialisee emploi
        </div>
        <div className="flex items-center gap-4">
          <span>v0.1.0</span>
          <span aria-hidden="true">-</span>
          <Link href="/business" className="hover:text-indigo-600 dark:hover:text-indigo-300">Observabilite</Link>
          <span aria-hidden="true">-</span>
          <Link href="/api/health" className="hover:text-indigo-600 dark:hover:text-indigo-300">API status</Link>
        </div>
      </div>
    </footer>
  );
}