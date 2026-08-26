import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getScan } from "../api/client";
import type { ScanDetail } from "../api/types";
import { ScanAnalysis } from "../components/analysis/ScanAnalysis";
import { PageHeader } from "../components/layout/PageHeader";
import { ErrorState, LoadingState } from "../components/states/States";
import { formatDateTime } from "../lib/format";

export function ScanDetailPage() {
  const { scanId } = useParams<{ scanId: string }>();
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!scanId) return;
    setScan(null);
    setError(null);
    getScan(Number(scanId))
      .then(setScan)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load this scan."),
      );
  }, [scanId]);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title={scan ? `Scan #${scan.scan_id}` : "Scan"}
        above={
          <Link
            to="/history"
            className="w-fit text-xs font-medium text-accent hover:underline"
          >
            ← Scan archive
          </Link>
        }
        actions={
          scan && (
            <dl className="flex flex-col items-end gap-0.5 text-right">
              <div className="flex items-baseline gap-2">
                <dt className="text-[10px] uppercase tracking-[0.09em] text-subtle">Captured</dt>
                <dd className="font-mono text-[11px] text-muted">
                  {formatDateTime(scan.uploaded_at)}
                </dd>
              </div>
              <div className="flex items-baseline gap-2">
                <dt className="text-[10px] uppercase tracking-[0.09em] text-subtle">Model</dt>
                <dd className="font-mono text-[11px] text-muted">{scan.model_version_label}</dd>
              </div>
            </dl>
          )
        }
      />

      {error && <ErrorState message={error} />}
      {!error && !scan && <LoadingState label="Loading scan" />}

      {scan && (
        <ScanAnalysis
          scanId={scan.scan_id}
          originalImageUrl={scan.original_image_url}
          gradcamOverlayUrl={scan.gradcam_overlay_url}
          predictedClass={scan.predicted_class}
          confidence={scan.confidence}
          probabilities={scan.probabilities}
          explanation={scan.explanation}
          feedback={scan.feedback}
          canReview={scan.can_review}
        />
      )}
    </div>
  );
}
