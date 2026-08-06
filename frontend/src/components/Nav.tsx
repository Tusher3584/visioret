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
    `rounded-md px-3 py-1.5 text-sm font-medium transition ${
      isActive
        ? "bg-teal-600 text-white"
        : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
    }`;

  return (
    <header className="flex flex-col gap-3 border-b border-slate-200 pb-4 dark:border-slate-700 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-xl font-bold text-slate-900 dark:text-slate-50">Visioret</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">Explainable AI for retinal OCT disease classification</p>
      </div>
      <div className="flex items-center gap-3">
        <nav className="flex gap-2">
          <NavLink to="/" end className={linkClass}>
            Predict
          </NavLink>
          <NavLink to="/history" className={linkClass}>
            History
          </NavLink>
        </nav>
        <StatusBadge health={health} />
      </div>
    </header>
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
      className={`rounded-full px-2.5 py-1 text-xs font-medium ${
        health.checkpoint_loaded
          ? "bg-teal-100 text-teal-800 dark:bg-teal-900/50 dark:text-teal-300"
          : "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300"
      }`}
    >
      {health.checkpoint_loaded ? "Model ready" : "No trained checkpoint"} &middot; {health.device.toUpperCase()}
    </span>
  );
}
