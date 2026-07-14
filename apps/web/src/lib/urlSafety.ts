const BLOCKED_HOSTS = new Set([
  "example.com",
  "www.example.com",
  "example.org",
  "www.example.org",
  "example.net",
  "www.example.net",
  "jobs.invalid",
  "stub.invalid",
]);

export function toSafeExternalUrl(value?: string | null): string | null {
  const raw = (value || "").trim();
  if (!raw) return null;

  try {
    const u = new URL(raw);
    const protocol = u.protocol.toLowerCase();
    if (protocol !== "http:" && protocol !== "https:") return null;

    const host = u.hostname.toLowerCase();
    if (BLOCKED_HOSTS.has(host)) return null;
    if (host.endsWith(".invalid")) return null;
    if (host.endsWith(".example")) return null;

    return u.toString();
  } catch {
    return null;
  }
}
