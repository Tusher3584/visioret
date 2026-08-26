import type { ReactNode } from "react";

/* --------------------------------------------------------------------------
   Shared state presentations. Every asynchronous surface in the app uses
   these so loading / empty / error / rejection always look and behave the
   same, and always carry the right semantics (role="alert" for anything the
   user must be told about immediately).
-------------------------------------------------------------------------- */

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2.5 px-4 py-6 text-sm text-muted" aria-live="polite">
      <span className="vr-pulse h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-[3px] border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-900 dark:border-rose-900 dark:bg-rose-950/50 dark:text-rose-200"
    >
      <span className="font-semibold">Error. </span>
      {message}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 border border-dashed border-line-strong bg-surface px-6 py-14 text-center rounded-[3px]">
      <p className="text-sm font-semibold text-ink">{title}</p>
      <p className="max-w-sm text-sm text-muted">{description}</p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

/**
 * The OOD gate rejecting an upload is a *correct decision*, not a failure --
 * the system declined to fabricate a diagnosis for an image that isn't an OCT
 * scan. Presented as a considered warning, never as a red error.
 */
export function OODRejectionState({
  message,
  previewUrl,
  onReset,
}: {
  message: string;
  previewUrl: string | null;
  onReset: ReactNode;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-4 rounded-[3px] border border-amber-400 bg-amber-50 p-5 dark:border-amber-700/70 dark:bg-amber-950/40 sm:flex-row sm:items-start"
    >
      {previewUrl && (
        <img
          src={previewUrl}
          alt="The image that was rejected"
          className="h-24 w-32 shrink-0 border border-amber-400/60 bg-imaging object-contain dark:border-amber-800"
        />
      )}
      <div className="flex flex-col gap-2">
        <p className="text-sm font-semibold text-amber-900 dark:text-amber-200">
          Not recognised as a retinal OCT scan
        </p>
        <p className="text-sm leading-relaxed text-amber-900/90 dark:text-amber-200/90">{message}</p>
        <p className="text-xs text-amber-800/80 dark:text-amber-300/70">
          No diagnosis was produced. The system rejects images it cannot verify rather than guessing.
        </p>
        <div className="mt-1">{onReset}</div>
      </div>
    </div>
  );
}
