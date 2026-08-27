import { Link } from "react-router-dom";
import { PageHeader } from "../components/layout/PageHeader";

/**
 * Catch-all for unmatched routes.
 *
 * Without this, an unknown path rendered the header and an empty <main> --
 * a mistyped URL or a stale bookmark produced a blank page with no
 * explanation and no way onward.
 */
export function NotFoundPage() {
  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Page not found"
        description="That address doesn't match anything in Visioret."
      />
      <div className="border border-line bg-surface rounded-[3px] px-4 py-5">
        <p className="text-sm text-muted">
          The link may be out of date, or the address may have a typo in it.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            to="/"
            className="rounded-[3px] bg-accent px-3 py-2 text-xs font-medium text-accent-ink"
          >
            Analyze a scan
          </Link>
          <Link
            to="/history"
            className="rounded-[3px] border border-line-strong px-3 py-2 text-xs font-medium text-ink"
          >
            Scan archive
          </Link>
        </div>
      </div>
    </div>
  );
}
