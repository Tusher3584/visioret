import { motion, type Variants } from "framer-motion";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, listScans, mediaUrl } from "../api/client";
import { classColors } from "../lib/classColors";
import type { ScanSummary } from "../api/types";

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};

const item: Variants = {
  hidden: { opacity: 0, x: -12 },
  show: { opacity: 1, x: 0, transition: { duration: 0.3, ease: "easeOut" } },
};

export default function ScanHistory() {
  const [scans, setScans] = useState<ScanSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listScans()
      .then(setScans)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load scan history."));
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">Scan History</h2>

      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
          {error}
        </div>
      )}

      {!error && !scans && <p className="text-sm text-slate-500 dark:text-slate-400">Loading...</p>}

      {!error && scans && scans.length === 0 && (
        <p className="text-sm text-slate-500 dark:text-slate-400">No scans yet -- predict on an image to see it here.</p>
      )}

      {!error && scans && scans.length > 0 && (
        <motion.ul variants={container} initial="hidden" animate="show" className="flex flex-col gap-2">
          {scans.map((scan) => {
            const colors = classColors(scan.predicted_class);
            return (
              <motion.li key={scan.scan_id} variants={item}>
                <Link to={`/scans/${scan.scan_id}`} className="block">
                  <motion.div
                    whileHover={{ x: 4 }}
                    transition={{ duration: 0.15 }}
                    className="flex items-center gap-4 rounded-xl border border-slate-200 bg-white p-3 shadow-sm transition-shadow hover:border-slate-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
                  >
                    <img
                      src={mediaUrl(scan.original_image_url)}
                      alt=""
                      className="h-16 w-16 shrink-0 rounded-lg border border-slate-200 object-cover dark:border-slate-800"
                    />
                    <div className="flex flex-1 flex-col gap-1">
                      <span className="flex items-center gap-2 font-semibold text-slate-900 dark:text-slate-50">
                        <span className={`h-2 w-2 shrink-0 rounded-full ${colors.dot}`} />
                        {scan.predicted_class}
                      </span>
                      <span className="font-mono text-sm text-slate-500 dark:text-slate-400">
                        {(scan.confidence * 100).toFixed(1)}% confidence
                      </span>
                    </div>
                    <span className="text-sm text-slate-400 dark:text-slate-500">
                      {new Date(scan.uploaded_at).toLocaleString()}
                    </span>
                  </motion.div>
                </Link>
              </motion.li>
            );
          })}
        </motion.ul>
      )}
    </div>
  );
}
