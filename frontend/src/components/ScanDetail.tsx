import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getScan } from "../api/client";
import type { ScanDetail as ScanDetailType } from "../api/types";
import ScanResult from "./ScanResult";

export default function ScanDetail() {
  const { scanId } = useParams<{ scanId: string }>();
  const [scan, setScan] = useState<ScanDetailType | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!scanId) return;
    setScan(null);
    setError(null);
    getScan(Number(scanId)).then(setScan).catch((err) => setError(err instanceof ApiError ? err.message : "Could not load this scan."));
  }, [scanId]);

  return (
    <div className="flex flex-col gap-6">
      <Link to="/history" className="w-fit text-sm font-medium text-blue-700 hover:underline dark:text-blue-400">
        &larr; Back to history
      </Link>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
          {error}
        </div>
      )}

      {!scan && !error && <p className="text-sm text-slate-500 dark:text-slate-400">Loading...</p>}

      {scan && (
        <>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
              Scan #{scan.scan_id} &middot; {new Date(scan.uploaded_at).toLocaleString()}
            </h2>
            <span className="font-mono text-xs text-slate-400 dark:text-slate-500">Model: {scan.model_version_label}</span>
          </div>
          <ScanResult
            originalImageUrl={scan.original_image_url}
            gradcamOverlayUrl={scan.gradcam_overlay_url}
            predictedClass={scan.predicted_class}
            confidence={scan.confidence}
            probabilities={scan.probabilities}
            explanation={scan.explanation}
          />
        </>
      )}
    </div>
  );
}
