const STORAGE_KEY = "visioret_anon_session";

/**
 * Opaque id for one anonymous browser session.
 *
 * Stored in `sessionStorage`, not `localStorage`, and that choice is the whole
 * feature: sessionStorage is cleared when the browser/tab closes, so an
 * anonymous visitor's scan history lasts exactly as long as their session and
 * then becomes unreachable. It is also per-tab, so two tabs are two sessions.
 *
 * Returns null when storage is unavailable (private mode, storage disabled).
 * The server treats a missing id as "matches nothing" rather than "matches all
 * anonymous scans", so failing to produce one costs the visitor their history
 * but never exposes anyone else's.
 */
export function getAnonSessionId(): string | null {
  try {
    const existing = sessionStorage.getItem(STORAGE_KEY);
    if (existing) return existing;

    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : Math.random().toString(36).slice(2) + Date.now().toString(36);

    sessionStorage.setItem(STORAGE_KEY, id);
    return id;
  } catch {
    return null;
  }
}
