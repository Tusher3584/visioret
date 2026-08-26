import { classColors } from "../../lib/classColors";

export type SortKey = "recent" | "oldest" | "confidence-high" | "confidence-low";

interface Props {
  allClasses: string[];
  activeClasses: Set<string>;
  onToggleClass: (name: string) => void;
  onClearClasses: () => void;
  sort: SortKey;
  onSortChange: (sort: SortKey) => void;
  query: string;
  onQueryChange: (query: string) => void;
  shownCount: number;
  totalCount: number;
}

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "recent", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "confidence-high", label: "Confidence, high→low" },
  { value: "confidence-low", label: "Confidence, low→high" },
];

/**
 * Filtering and sorting operate purely on the already-fetched history array.
 * The list endpoint returns every scan in one response and exposes no
 * server-side filter/sort parameters, so doing this client-side is honest --
 * nothing here implies a backend capability that doesn't exist.
 */
export function ArchiveToolbar({
  allClasses,
  activeClasses,
  onToggleClass,
  onClearClasses,
  sort,
  onSortChange,
  query,
  onQueryChange,
  shownCount,
  totalCount,
}: Props) {
  const filtering = activeClasses.size > 0;

  return (
    <div className="flex flex-col gap-3 border border-line bg-surface p-3 rounded-[3px] lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-[11px] font-semibold uppercase tracking-[0.09em] text-subtle">
          Class
        </span>
        {allClasses.map((name) => {
          const tokens = classColors(name);
          const active = activeClasses.has(name);
          return (
            <button
              key={name}
              type="button"
              aria-pressed={active}
              onClick={() => onToggleClass(name)}
              className={`inline-flex items-center gap-1.5 rounded-[3px] border px-2 py-1 text-[11px] font-medium transition-colors ${
                active
                  ? "border-line-strong bg-raised text-ink"
                  : "border-line text-muted hover:border-line-strong hover:text-ink"
              }`}
            >
              <span className={`h-2 w-2 rounded-[1px] ${tokens.dot}`} aria-hidden="true" />
              {name}
            </button>
          );
        })}
        {filtering && (
          <button
            type="button"
            onClick={onClearClasses}
            className="ml-1 text-[11px] font-medium text-accent hover:underline"
          >
            Clear
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1.5">
          <span className="sr-only">Search by scan ID</span>
          <input
            type="search"
            inputMode="numeric"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Scan ID…"
            className="w-28 rounded-[3px] border border-line bg-surface px-2 py-1 font-mono text-xs text-ink placeholder:text-subtle"
          />
        </label>

        <label className="flex items-center gap-1.5">
          <span className="sr-only">Sort scans</span>
          <select
            value={sort}
            onChange={(e) => onSortChange(e.target.value as SortKey)}
            className="rounded-[3px] border border-line bg-surface px-2 py-1 text-xs text-ink"
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <span
          className="font-mono text-[11px] text-subtle"
          aria-live="polite"
        >
          {shownCount}/{totalCount}
        </span>
      </div>
    </div>
  );
}
