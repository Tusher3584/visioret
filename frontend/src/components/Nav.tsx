import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { fetchHealth } from "../api/client";
import type { HealthResponse } from "../api/types";
import { useAuth } from "../context/AuthContext";

const NAV_LINKS = [
  { to: "/", label: "Predict", end: true },
  { to: "/history", label: "History", end: false },
  { to: "/metrics", label: "Metrics", end: false },
];

export default function Nav() {
  const [health, setHealth] = useState<HealthResponse | "error" | null>(null);
  const { user, isLoading, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth("error"));
  }, []);

  return (
    <motion.header
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="flex flex-col gap-4 border-b border-slate-200 pb-5 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex items-center gap-3">
        <LogoMark />
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-50">Visioret</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Explainable AI for retinal OCT disease classification</p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <nav className="flex gap-1">
          {NAV_LINKS.map((link) => (
            <NavItem key={link.to} to={link.to} end={link.end}>
              {link.label}
            </NavItem>
          ))}
        </nav>
        <StatusBadge health={health} />
        {!isLoading && (
          <AuthControl
            user={user}
            onLogout={() => {
              logout();
              navigate("/");
            }}
          />
        )}
      </div>
    </motion.header>
  );
}

function NavItem({ to, end, children }: { to: string; end: boolean; children: string }) {
  return (
    <NavLink to={to} end={end} className="relative rounded-lg px-3 py-1.5 text-sm font-medium">
      {({ isActive }) => (
        <>
          {isActive && (
            <motion.span
              layoutId="nav-active-pill"
              className="absolute inset-0 rounded-lg bg-blue-600"
              transition={{ type: "spring", stiffness: 500, damping: 35 }}
            />
          )}
          <span
            className={`relative transition-colors ${
              isActive ? "text-white" : "text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
            }`}
          >
            {children}
          </span>
        </>
      )}
    </NavLink>
  );
}

function AuthControl({ user, onLogout }: { user: { name: string } | null; onLogout: () => void }) {
  if (!user) {
    return (
      <NavLink to="/login" className="text-sm font-medium text-blue-700 hover:underline dark:text-blue-400">
        Log in
      </NavLink>
    );
  }
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-slate-600 dark:text-slate-300">{user.name}</span>
      <button onClick={onLogout} className="font-medium text-blue-700 hover:underline dark:text-blue-400">
        Log out
      </button>
    </div>
  );
}

function LogoMark() {
  return (
    <motion.svg
      width="32"
      height="32"
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      initial={{ rotate: -8, scale: 0.8, opacity: 0 }}
      animate={{ rotate: 0, scale: 1, opacity: 1 }}
      transition={{ duration: 0.5, ease: "backOut" }}
    >
      <rect width="32" height="32" rx="8" className="fill-blue-600" />
      <circle cx="16" cy="16" r="7" stroke="white" strokeWidth="2" />
      <motion.circle
        cx="16"
        cy="16"
        r="2.25"
        fill="white"
        animate={{ opacity: [1, 0.4, 1] }}
        transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
      />
    </motion.svg>
  );
}

function StatusBadge({ health }: { health: HealthResponse | "error" | null }) {
  if (health === null) {
    return <span className="text-xs text-slate-400">checking API...</span>;
  }
  if (health === "error") {
    return (
      <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-medium text-red-700 dark:bg-red-900/50 dark:text-red-300">
        API unreachable
      </span>
    );
  }
  return (
    <span
      title={`Device: ${health.device} | Classes: ${health.classes.join(", ")}`}
      className={`rounded-full px-2.5 py-1 font-mono text-xs font-medium ${
        health.checkpoint_loaded
          ? "bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300"
          : "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300"
      }`}
    >
      {health.checkpoint_loaded ? "Model ready" : "No trained checkpoint"} &middot; {health.device.toUpperCase()}
    </span>
  );
}
