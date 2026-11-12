// What the browser keeps for a signed-in user, and how it is thrown away.
// A login lives as long as its token (JWT_EXPIRE_MINUTES on the server, 24 h).
// When the token ends, or the user signs out, every per-user trace goes with
// it: the token, the MarketPulse AI chat, and anything in sessionStorage. The
// interface language is a device setting and stays.

export const TOKEN_KEY = "marketpulse_token";
const CHAT_PREFIX = "marketpulse_chat_";

export const chatKey = (userId: number) => `${CHAT_PREFIX}${userId}`;

/** Expiry of a JWT in ms since epoch, or null when the token cannot be read. */
export function tokenExpiry(token: string): number | null {
  try {
    const part = token.split(".")[1];
    const json = atob(part.replace(/-/g, "+").replace(/_/g, "/"));
    const exp = JSON.parse(json).exp;
    return typeof exp === "number" ? exp * 1000 : null;
  } catch {
    return null;
  }
}

/** A token that has run out (or cannot be read) is not worth sending. */
export function tokenAlive(token: string | null, now = Date.now()): boolean {
  if (!token) return false;
  const exp = tokenExpiry(token);
  return exp != null && exp > now;
}

/** The stored token, or null after removing a dead one with its session. */
export function storedToken(): string | null {
  const token = safe(() => localStorage.getItem(TOKEN_KEY), null);
  if (token && !tokenAlive(token)) {
    clearSession();
    return null;
  }
  return token;
}

/** Remove the token, every user's chat and the tab's session storage. */
export function clearSession(): void {
  safe(() => {
    const keys: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && (k === TOKEN_KEY || k.startsWith(CHAT_PREFIX))) keys.push(k);
    }
    keys.forEach((k) => localStorage.removeItem(k));
  }, undefined);
  safe(() => sessionStorage.clear(), undefined);
}

function safe<T>(fn: () => T, fallback: T): T {
  try {
    return fn();
  } catch {
    return fallback; // storage blocked (private mode, site data off)
  }
}
