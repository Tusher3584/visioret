import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  ApiError,
  clearToken,
  fetchMe,
  getToken,
  login as apiLogin,
  register as apiRegister,
  setToken,
} from "../api/client";
import type { User } from "../api/types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  /** True only for the reviewer role. Presentation convenience -- the server
   *  enforces this independently; never rely on it for actual protection. */
  isReviewer: boolean;
  /** Admin implies reviewer -- see backend/auth.py. */
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  /** Replace the cached user after a profile edit, so the header/menu update
   *  without a reload. */
  setUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // No token means definitively signed out -- skip the request rather than
    // firing a guaranteed 401 on every page load for anonymous visitors
    // (which is most of them: analysis works without an account).
    if (!getToken()) {
      setIsLoading(false);
      return;
    }

    fetchMe()
      .then(setUser)
      .catch((err) => {
        setUser(null);
        // 401 means the token is genuinely bad (expired, or signed with a
        // rotated secret) -- drop it so the app stops retrying it. Anything
        // else is transient: the backend restarting, a network blip. Keeping
        // the token there means a reload signs the user back in instead of
        // silently logging them out over a hiccup.
        if (err instanceof ApiError && err.status === 401) clearToken();
      })
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
      value={{
        user,
        isLoading,
        isReviewer: user?.role === "reviewer" || user?.role === "admin",
        isAdmin: user?.role === "admin",
        login,
        register,
        logout,
        setUser,
      }}
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
