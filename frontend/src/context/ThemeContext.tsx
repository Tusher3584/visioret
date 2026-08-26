import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "visioret_theme";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  /** True while the theme is still whatever the OS asked for, i.e. the user
   *  has not made an explicit choice yet. */
  followsSystem: boolean;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readStored(): Theme | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

function systemTheme(): Theme {
  return typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

/**
 * Theme state, kept in sync with the `data-theme` attribute that the inline
 * script in index.html already set before React mounted -- so this provider
 * adopts the existing value rather than re-deciding it and causing a flash.
 *
 * Until the user picks explicitly, the app keeps following the OS: if they
 * change their system theme it follows along live. The first click stores a
 * choice, and from then on that choice wins.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof document !== "undefined") {
      const applied = document.documentElement.getAttribute("data-theme");
      if (applied === "light" || applied === "dark") return applied;
    }
    return readStored() ?? systemTheme();
  });
  const [followsSystem, setFollowsSystem] = useState(() => readStored() === null);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Track the OS preference only while the user has not overridden it.
  useEffect(() => {
    if (!followsSystem) return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event: MediaQueryListEvent) => setTheme(event.matches ? "dark" : "light");
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [followsSystem]);

  const toggleTheme = useCallback(() => {
    setTheme((current) => {
      const next: Theme = current === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        // Storage unavailable -- the choice just won't persist across reloads.
      }
      return next;
    });
    setFollowsSystem(false);
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, followsSystem }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider.");
  return ctx;
}
