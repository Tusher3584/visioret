import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, listScans, mediaUrl } from "../api/client";
import type { ScanSummary } from "../api/types";

export default function ScanHistory() {
  const [scans, setScans] = useState<ScanSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listScans()
      .then(setScans)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load scan history."));
  }, []);

  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
        {error}
      </div>
    );
  }

  if (!scans) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">Loading...</p>;
  }

  if (scans.length === 0) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">No scans yet -- predict on an image to see it here.</p>;
  }

  return (
    <ul className="flex flex-col divide-y divide-slate-200 dark:divide-slate-700">
      {scans.map((scan) => (
        <li key={scan.scan_id}>
          <Link
            to={`/scans/${scan.scan_id}`}
            className="flex items-center gap-4 py-3 transition hover:bg-slate-50 dark:hover:bg-slate-800/50"
          >
            <img
              src={mediaUrl(scan.original_image_url)}
              alt=""
              className="h-16 w-16 shrink-0 rounded-md border border-slate-200 object-cover dark:border-slate-700"
            />
            <div className="flex flex-1 flex-col">
              <span className="font-medium text-slate-900 dark:text-slate-50">{scan.predicted_class}</span>
              <span className="text-sm text-slate-500 dark:text-slate-400">
                {(scan.confidence * 100).toFixed(1)}% confidence
              </span>
            </div>
            <span className="text-sm text-slate-400 dark:text-slate-500">
              {new Date(scan.uploaded_at).toLocaleString()}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
