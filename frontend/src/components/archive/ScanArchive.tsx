import { Link } from "react-router-dom";
import { mediaUrl } from "../../api/client";
import type { ScanSummary } from "../../api/types";
import { classColors } from "../../lib/classColors";
import { formatDate, formatTime, percent } from "../../lib/format";

interface Props {
  scans: ScanSummary[];
  /** Reviewers see everyone's scans, so they need to know whose is whose.
   *  For everyone else every row is their own and the column is noise. */
  showOwner?: boolean;
}

/**
 * Dense record archive rather than a stack of floating cards -- the task here
 * is scanning many results quickly, so rows are compact and column-aligned.
 *
 * Uses a real table with proper header scope. The whole row is clickable via a
 * stretched anchor, which keeps a single real link per row for keyboard and
 * screen-reader users (no clickable divs).
 */
export function ScanArchive({ scans, showOwner = false }: Props) {
  return (
    <div className="overflow-hidden border border-line bg-surface rounded-[3px]">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">Previously analysed scans, one row per scan</caption>
        <thead>
          <tr className="border-b border-line text-left">
            <th scope="col" className="w-[68px] px-3 py-2">
              <span className="sr-only">Thumbnail</span>
            </th>
            <Th>Scan</Th>
            <Th>Class</Th>
            <Th className="hidden sm:table-cell">Confidence</Th>
            {showOwner && <Th className="hidden lg:table-cell">Submitted by</Th>}
            <Th className="hidden md:table-cell">Captured</Th>
          </tr>
        </thead>
        <tbody>
          {scans.map((scan) => {
            const tokens = classColors(scan.predicted_class);
            return (
              <tr
                key={scan.scan_id}
                className="relative border-b border-line/70 transition-colors last:border-0 hover:bg-raised focus-within:bg-raised"
              >
                <td className="px-3 py-2">
                  <img
                    src={mediaUrl(scan.original_image_url)}
                    alt=""
                    className="h-11 w-14 border border-line bg-imaging object-contain"
                  />
                </td>

                <td className="px-3 py-2">
                  <Link
                    to={`/scans/${scan.scan_id}`}
                    className="font-mono text-xs font-medium text-ink after:absolute after:inset-0 after:content-['']"
                  >
                    #{scan.scan_id}
                  </Link>
                  <span className="mt-0.5 block text-[11px] text-subtle md:hidden">
                    {formatDate(scan.uploaded_at)}
                  </span>
                </td>

                <td className="px-3 py-2">
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className={`h-2 w-2 shrink-0 rounded-[1px] ${tokens.dot}`}
                      aria-hidden="true"
                    />
                    <span className={`text-xs font-medium ${tokens.text}`}>
                      {scan.predicted_class}
                    </span>
                  </span>
                  <span className="mt-0.5 block font-mono text-[11px] text-subtle sm:hidden">
                    {percent(scan.confidence)}
                  </span>
                </td>

                <td className="hidden px-3 py-2 sm:table-cell">
                  <span className="flex items-center gap-2">
                    <span
                      aria-hidden="true"
                      className="h-1 w-14 overflow-hidden rounded-full bg-raised dark:bg-black/40"
                    >
                      <span
                        className={`block h-full rounded-full ${tokens.fill}`}
                        style={{ width: `${Math.max(scan.confidence * 100, 2)}%` }}
                      />
                    </span>
                    <span className="font-mono text-xs tabular-nums text-muted">
                      {percent(scan.confidence)}
                    </span>
                  </span>
                </td>

                {showOwner && (
                  <td className="hidden px-3 py-2 lg:table-cell">
                    <span className="text-xs text-muted">
                      {scan.owner_name ?? <span className="text-subtle">anonymous</span>}
                    </span>
                  </td>
                )}

                <td className="hidden px-3 py-2 md:table-cell">
                  <span className="block font-mono text-xs text-muted">
                    {formatDate(scan.uploaded_at)}
                  </span>
                  <span className="block font-mono text-[11px] text-subtle">
                    {formatTime(scan.uploaded_at)}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Th({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <th
      scope="col"
      className={`px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.09em] text-subtle ${className}`}
    >
      {children}
    </th>
  );
}
