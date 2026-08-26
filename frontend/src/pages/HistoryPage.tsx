import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, listScans } from "../api/client";
import type { ScanSummary } from "../api/types";
import { ArchiveToolbar, type SortKey } from "../components/archive/ArchiveToolbar";
import { ScanArchive } from "../components/archive/ScanArchive";
import { PageHeader } from "../components/layout/PageHeader";
import { EmptyState, ErrorState, LoadingState } from "../components/states/States";
import { Button } from "../components/ui/Button";
import { useAuth } from "../context/AuthContext";

const KNOWN_CLASSES = ["CNV", "DME", "DRUSEN", "NORMAL"];

export function HistoryPage() {
  const { user, isReviewer } = useAuth();
  const [scans, setScans] = useState<ScanSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeClasses, setActiveClasses] = useState<Set<string>>(new Set());
  const [sort, setSort] = useState<SortKey>("recent");
  const [query, setQuery] = useState("");

  // Which scans are visible depends on who is signed in, so refetch whenever
  // that identity changes rather than only on mount.
  useEffect(() => {
    setScans(null);
    setError(null);
    listScans()
      .then(setScans)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load the scan archive."),
      );
  }, [user?.id]);

  // Filtering and sorting are client-side over the already-fetched array; the
  // list endpoint takes no filter or sort parameters.
  const visible = useMemo(() => {
    if (!scans) return [];
    const trimmed = query.trim();
    const filtered = scans.filter((scan) => {
      if (activeClasses.size > 0 && !activeClasses.has(scan.predicted_class.toUpperCase())) {
        return false;
      }
      if (trimmed && !String(scan.scan_id).includes(trimmed)) return false;
      return true;
    });

    const sorted = [...filtered];
    sorted.sort((a, b) => {
      switch (sort) {
        case "oldest":
          return Date.parse(a.uploaded_at) - Date.parse(b.uploaded_at);
        case "confidence-high":
          return b.confidence - a.confidence;
        case "confidence-low":
          return a.confidence - b.confidence;
        default:
          return Date.parse(b.uploaded_at) - Date.parse(a.uploaded_at);
      }
    });
    return sorted;
  }, [scans, activeClasses, sort, query]);

  function toggleClass(name: string) {
    setActiveClasses((current) => {
      const next = new Set(current);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Scan archive"
        description={
          isReviewer
            ? "Every scan analysed by this instance, across all users. Newest first."
            : user
              ? "Scans you have analysed, newest first."
              : "Scans analysed in this browser without signing in, newest first."
        }
        actions={
          <Link to="/">
            <Button variant="secondary" size="sm">
              New analysis
            </Button>
          </Link>
        }
      />

      {error && <ErrorState message={error} />}
      {!error && !scans && <LoadingState label="Loading archive" />}

      {!error && scans && scans.length === 0 && (
        <EmptyState
          title="No scans yet"
          description="Once you analyse a scan it will appear here, with its classification and confidence."
          action={
            <Link to="/">
              <Button variant="primary" size="sm">
                Analyze a scan
              </Button>
            </Link>
          }
        />
      )}

      {!error && scans && scans.length > 0 && (
        <>
          <ArchiveToolbar
            allClasses={KNOWN_CLASSES}
            activeClasses={activeClasses}
            onToggleClass={toggleClass}
            onClearClasses={() => setActiveClasses(new Set())}
            sort={sort}
            onSortChange={setSort}
            query={query}
            onQueryChange={setQuery}
            shownCount={visible.length}
            totalCount={scans.length}
          />

          {visible.length === 0 ? (
            <EmptyState
              title="No matching scans"
              description="No scan in the archive matches the current filters."
              action={
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setActiveClasses(new Set());
                    setQuery("");
                  }}
                >
                  Reset filters
                </Button>
              }
            />
          ) : (
            <ScanArchive scans={visible} showOwner={isReviewer} />
          )}
        </>
      )}
    </div>
  );
}
