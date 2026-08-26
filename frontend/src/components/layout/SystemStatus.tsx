import { useEffect, useRef, useState } from "react";
import { fetchHealth } from "../../api/client";
import type { HealthResponse } from "../../api/types";

type Health = HealthResponse | "error" | null;

/**
 * Compact live backend indicator. Collapsed it is just a status dot plus a
 * short label; the full technical detail (device, checkpoint, OOD gate, class
 * list) lives in a popover so it is available without cluttering the header.
 */
export function SystemStatus() {
  const [health, setHealth] = useState<Health>(null);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth("error"));
  }, []);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const ok = health !== null && health !== "error" && health.checkpoint_loaded;
  const unreachable = health === "error";

  const dotClass = unreachable
    ? "bg-rose-500"
    : health === null
      ? "bg-subtle"
      : ok
        ? "bg-emerald-500"
        : "bg-amber-500";

  const label = unreachable
    ? "Offline"
    : health === null
      ? "Connecting"
      : ok
        ? "Online"
        : "Degraded";

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="inline-flex items-center gap-2 rounded-[3px] border border-line px-2.5 py-1.5 text-[11px] font-medium text-muted transition-colors hover:border-line-strong hover:text-ink"
      >
        <span className={`h-1.5 w-1.5 rounded-full ${dotClass}`} aria-hidden="true" />
        <span>{label}</span>
        {health !== null && health !== "error" && (
          <span className="hidden font-mono uppercase text-subtle sm:inline">{health.device}</span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="System status detail"
          className="absolute right-0 top-[calc(100%+6px)] z-50 w-64 border border-line bg-surface p-3 shadow-lg rounded-[3px]"
        >
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.09em] text-muted">
            System status
          </p>
          {unreachable ? (
            <p className="text-xs text-rose-700 dark:text-rose-300">
              The API is unreachable. Predictions are unavailable until it is back.
            </p>
          ) : health === null ? (
            <p className="text-xs text-muted">Contacting the API…</p>
          ) : (
            <dl className="flex flex-col gap-1.5 text-xs">
              <Row label="Device" value={health.device.toUpperCase()} mono />
              <Row label="Model" value={health.checkpoint_loaded ? "Loaded" : "Not loaded"} />
              <Row label="OOD gate" value={health.ood_gate_active ? "Active" : "Inactive"} />
              <Row label="Classes" value={health.classes.join(" · ")} mono />
            </dl>
          )}
        </div>
      )}
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="shrink-0 text-subtle">{label}</dt>
      <dd className={`text-right text-ink ${mono ? "font-mono text-[11px]" : ""}`}>{value}</dd>
    </div>
  );
}
