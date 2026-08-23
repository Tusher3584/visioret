import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { fetchHealth } from "../api/client";
import type { HealthResponse } from "../api/types";

export default function Nav() {
  const [health, setHealth] = useState<HealthResponse | "error" | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth("error"));
  }, []);

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-1.5 text-sm font-medium transition ${
      isActive
        ? "bg-blue-600 text-white"
        : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
    }`;

  return (
    <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <LogoMark />
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-50">Visioret</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Explainable AI for retinal OCT disease classification</p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <nav className="flex gap-1.5">
          <NavLink to="/" end className={linkClass}>
            Predict
          </NavLink>
          <NavLink to="/history" className={linkClass}>
            History
          </NavLink>
          <NavLink to="/metrics" className={linkClass}>
            Metrics
          </NavLink>
        </nav>
        <StatusBadge health={health} />
      </div>
    </header>
  );
}

function LogoMark() {
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect width="32" height="32" rx="8" className="fill-blue-600" />
      <circle cx="16" cy="16" r="7" stroke="white" strokeWidth="2" />
      <circle cx="16" cy="16" r="2.25" fill="white" />
    </svg>
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
