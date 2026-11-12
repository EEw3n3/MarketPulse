import { beforeEach, describe, expect, it } from "vitest";
import { TOKEN_KEY, chatKey, clearSession, storedToken, tokenAlive } from "@/lib/session";

const b64 = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
const jwt = (expSec: number) => `${b64({ alg: "HS256" })}.${b64({ sub: "1", exp: expSec })}.sig`;
const now = Math.floor(Date.now() / 1000);

describe("session storage", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it("tells a live token from a dead or broken one", () => {
    expect(tokenAlive(jwt(now + 3600))).toBe(true);
    expect(tokenAlive(jwt(now - 1))).toBe(false);
    expect(tokenAlive("garbage")).toBe(false);
    expect(tokenAlive(null)).toBe(false);
  });

  it("drops an expired token together with the chats", () => {
    localStorage.setItem(TOKEN_KEY, jwt(now - 60));
    localStorage.setItem(chatKey(7), "[]");
    localStorage.setItem("marketpulse_lang", "lv");
    expect(storedToken()).toBeNull();
    expect(localStorage.getItem(chatKey(7))).toBeNull();
    expect(localStorage.getItem("marketpulse_lang")).toBe("lv");
  });

  it("keeps a live token and its chat", () => {
    const t = jwt(now + 3600);
    localStorage.setItem(TOKEN_KEY, t);
    localStorage.setItem(chatKey(7), "[]");
    expect(storedToken()).toBe(t);
    expect(localStorage.getItem(chatKey(7))).toBe("[]");
  });

  it("clearSession removes token, every chat and session storage", () => {
    localStorage.setItem(TOKEN_KEY, jwt(now + 3600));
    localStorage.setItem(chatKey(1), "[]");
    localStorage.setItem(chatKey(2), "[]");
    sessionStorage.setItem("x", "1");
    clearSession();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});
