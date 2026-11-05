import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, TokenResponse, UserRead, UserPreferencesUpdate } from "@/lib/api";

const TOKEN_KEY = "marketpulse_token";

interface AuthContextValue {
  user: UserRead | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  /** Sign in or sign up with the ID token from the Google button. */
  loginWithGoogle: (credential: string) => Promise<TokenResponse>;
  logout: () => void;
  updatePreferences: (patch: UserPreferencesUpdate) => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserRead | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    api.me()
      .then(setUser)
      .catch((e) => {
        // Only a rejected token signs the user out; a network blip keeps it for the next load.
        if (/API Error: 40[13]\b/.test(e instanceof Error ? e.message : "")) {
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const qc = useQueryClient();

  const _persist = (newToken: string, newUser: UserRead) => {
    // Another account's cached data (plan, checkout, favorites) must not show for this one.
    qc.clear();
    localStorage.setItem(TOKEN_KEY, newToken);
    setToken(newToken);
    setUser(newUser);
  };

  const login = async (email: string, password: string) => {
    const res = await api.login({ email, password });
    _persist(res.access_token, res.user);
  };

  const register = async (email: string, password: string, fullName?: string) => {
    const res = await api.register({ email, password, full_name: fullName });
    _persist(res.access_token, res.user);
  };

  const loginWithGoogle = async (credential: string) => {
    const res = await api.googleSignIn(credential);
    _persist(res.access_token, res.user);
    return res;
  };

  const logout = () => {
    if (user) localStorage.removeItem(`marketpulse_chat_${user.id}`);
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    qc.clear();
  };

  const updatePreferences = async (patch: UserPreferencesUpdate) => {
    const prefs = await api.updatePreferences(patch);
    setUser((prev) => prev ? { ...prev, preferences: prefs } : prev);
  };

  const refreshUser = async () => {
    const u = await api.me();
    setUser(u);
  };

  // A Pro endpoint answered 403: the term ended while the page was open.
  useEffect(() => {
    if (!token) return;
    const onEnded = () => { api.me().then(setUser).catch(() => undefined); };
    window.addEventListener("mp:pro-ended", onEnded);
    return () => window.removeEventListener("mp:pro-ended", onEnded);
  }, [token]);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, loginWithGoogle, logout, updatePreferences, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
