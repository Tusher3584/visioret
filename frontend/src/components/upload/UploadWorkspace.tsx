import { useRef, useState, type DragEvent } from "react";
import { Button } from "../ui/Button";

interface Props {
  file: File | null;
  previewUrl: string | null;
  isLoading: boolean;
  onFileChange: (file: File | null) => void;
  onAnalyze: () => void;
}

const ACCEPTED = ["image/jpeg", "image/png"];

/**
 * Upload surface for a single OCT B-scan.
 *
 * Uses a real drop target plus a keyboard-reachable browse button rather than
 * the raw file input. Once a scan is chosen it previews on the same dark
 * imaging surface the analysis workspace uses, so the transition from
 * "selected" to "analysed" is visually continuous.
 */
export function UploadWorkspace({
  file,
  previewUrl,
  isLoading,
  onFileChange,
  onAnalyze,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [rejected, setRejected] = useState<string | null>(null);

  function accept(candidate: File | undefined | null) {
    if (!candidate) return;
    if (!ACCEPTED.includes(candidate.type)) {
      setRejected("That file type isn’t supported. Use a JPEG or PNG image.");
      return;
    }
    setRejected(null);
    onFileChange(candidate);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    accept(event.dataTransfer.files?.[0]);
  }

  return (
    <section
      aria-label="Upload a scan"
      className="flex flex-col border border-line bg-surface rounded-[3px]"
    >
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted">
          Scan input
        </h2>
        <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-subtle">
          Validate → Classify → Explain
        </p>
      </div>

      <div className="p-4">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
          className={`relative flex min-h-[280px] flex-col items-center justify-center overflow-hidden border border-dashed transition-colors ${
            isDragging ? "border-accent bg-accent-soft/20" : "border-imaging-line"
          } bg-imaging`}
        >
          <div className="vr-grid absolute inset-0" aria-hidden="true" />

          {previewUrl ? (
            <>
              <img
                src={previewUrl}
                alt="Preview of the selected scan"
                className="relative max-h-[420px] w-full object-contain"
              />
              {isLoading && (
                <div className="absolute inset-0 overflow-hidden" aria-hidden="true">
                  <div className="vr-scanline absolute inset-x-0 h-16 bg-gradient-to-b from-transparent via-cyan-300/35 to-transparent" />
                </div>
              )}
              <div className="pointer-events-none absolute left-0 top-0 bg-imaging/85 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-slate-200">
                {isLoading ? "Analyzing" : "Ready"}
              </div>
            </>
          ) : (
            <div className="relative flex flex-col items-center gap-3 px-6 py-10 text-center">
              <svg
                width="34"
                height="34"
                viewBox="0 0 34 34"
                fill="none"
                aria-hidden="true"
                className="text-slate-500"
              >
                <rect x="1" y="6" width="32" height="22" stroke="currentColor" strokeWidth="1.4" />
                <path
                  d="M5 21c4 0 5.5-7 12-7s8 7 12 7"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                />
              </svg>
              <div>
                <p className="text-sm font-medium text-slate-200">Drop a retinal OCT B-scan here</p>
                <p className="mt-1 text-xs text-slate-400">
                  One image at a time · JPEG or PNG
                </p>
              </div>
              <Button variant="secondary" size="sm" onClick={() => inputRef.current?.click()}>
                Browse files
              </Button>
            </div>
          )}
        </div>

        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png"
          tabIndex={-1}
          aria-hidden="true"
          className="sr-only"
          onChange={(e) => accept(e.target.files?.[0])}
        />

        {rejected && (
          <p role="alert" className="mt-3 text-xs text-rose-700 dark:text-rose-300">
            {rejected}
          </p>
        )}

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p className="min-w-0 truncate text-xs text-muted">
            {file ? (
              <>
                <span className="font-mono text-ink">{file.name}</span>
                <span className="text-subtle"> · {(file.size / 1024).toFixed(0)} KB</span>
              </>
            ) : (
              "No scan selected."
            )}
          </p>
          <div className="flex items-center gap-2">
            {file && (
              <Button
                variant="ghost"
                size="sm"
                disabled={isLoading}
                onClick={() => inputRef.current?.click()}
              >
                Replace
              </Button>
            )}
            <Button
              variant="primary"
              size="sm"
              onClick={onAnalyze}
              disabled={!file || isLoading}
              aria-busy={isLoading}
            >
              {isLoading ? "Analyzing…" : "Analyze scan"}
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
