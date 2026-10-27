import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, UserRead, UserPreferencesUpdate } from "@/lib/api";

const TOKEN_KEY = "marketpulse_token";

interface AuthContextValue {
  user: UserRead | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
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

  const _persist = (newToken: string, newUser: UserRead) => {
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

  const logout = () => {
    if (user) localStorage.removeItem(`marketpulse_chat_${user.id}`);
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  };

  const updatePreferences = async (patch: UserPreferencesUpdate) => {
    const prefs = await api.updatePreferences(patch);
    setUser((prev) => prev ? { ...prev, preferences: prefs } : prev);
  };

  const refreshUser = async () => {
    const u = await api.me();
    setUser(u);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, updatePreferences, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
