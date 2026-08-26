import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { clearToken, fetchMe, login as apiLogin, register as apiRegister, setToken } from "../api/client";
import type { User } from "../api/types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  /** True only for the reviewer role. Presentation convenience -- the server
   *  enforces this independently; never rely on it for actual protection. */
  isReviewer: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const result = await apiLogin({ email, password });
    setToken(result.access_token);
    setUser(result.user);
  }

  async function register(name: string, email: string, password: string) {
    const result = await apiRegister({ name, email, password });
    setToken(result.access_token);
    setUser(result.user);
  }

  function logout() {
    clearToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider
      value={{ user, isLoading, isReviewer: user?.role === "reviewer", login, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider.");
  return ctx;
}
