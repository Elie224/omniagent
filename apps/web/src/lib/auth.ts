"use client";

const TOKEN_KEY = "omniagent:auth:access";
const REFRESH_KEY = "omniagent:auth:refresh";
const USER_KEY = "omniagent:auth:user";

export type AuthUser = {
  user_id: string;
  email: string;
  display_name?: string;
  org_id?: string;
  role?: string;
};

export type AuthTokens = {
  access_token: string;
  refresh_token: string;
  token_type?: string;
  expires_in?: number;
};

function getApiBase(): string {
  const env = (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL) || "http://localhost:18000";
  return env.replace(/\/$/, "");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  const access = readAccess();
  if (access && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${access}`;
  }
  const body = init.body && !(init.body instanceof FormData) ? JSON.stringify(init.body) : (init.body as BodyInit | undefined);
  const res = await fetch(`${getApiBase()}${path}`, {
    ...init,
    headers,
    body,
  });
  const text = await res.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
  if (!res.ok) {
    const detail = data?.detail || data?.message || res.statusText;
    throw new Error(typeof detail === "string" ? detail : `HTTP ${res.status}`);
  }
  return data as T;
}

export function readAccess(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function readRefresh(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function readUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw) as AuthUser; } catch { return null; }
}

export function isLoggedIn(): boolean {
  return !!readAccess() || !!readUser();
}

export function setAuth(tokens: AuthTokens, user?: AuthUser | null) {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, tokens.access_token);
  if (tokens.refresh_token) localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
}

export async function signup(input: {
  email: string;
  password: string;
  display_name?: string;
  org_name: string;
}): Promise<AuthTokens> {
  const tokens = await request<AuthTokens>("/api/v1/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  setAuth(tokens);
  return tokens;
}

export async function login(input: {
  email: string;
  password: string;
  org_id?: string;
}): Promise<AuthTokens> {
  const tokens = await request<AuthTokens>("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  setAuth(tokens);
  // Fetch /me to capture user info; tolerate failure.
  try {
    const me = await request<AuthUser>("/api/v1/auth/me", { method: "GET" });
    setAuth(tokens, me);
  } catch {/* ignore */}
  return tokens;
}

export async function logout(): Promise<void> {
  try {
    await request("/api/v1/auth/logout", { method: "POST" });
  } catch {/* ignore */}
  clearAuth();
}

export async function fetchCurrentUser(): Promise<AuthUser | null> {
  try {
    const me = await request<AuthUser>("/api/v1/auth/me", { method: "GET" });
    setAuth({ access_token: readAccess() || "", refresh_token: readRefresh() || "" }, me);
    return me;
  } catch {
    return null;
  }
}