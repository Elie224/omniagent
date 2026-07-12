// Petit helper de concatenation de classes (equivalent minimal de clsx).
// On n importe pas clsx pour eviter une dep ; mais le composant reste simple.

type ClassValue = string | number | null | undefined | false | Record<string, boolean | null | undefined>;

export function cn(...inputs: ClassValue[]): string {
  const out: string[] = [];
  for (const v of inputs) {
    if (!v) continue;
    if (typeof v === "string" || typeof v === "number") {
      out.push(String(v));
    } else if (typeof v === "object") {
      for (const k of Object.keys(v)) {
        if (v[k]) out.push(k);
      }
    }
  }
  return out.join(" ");
}