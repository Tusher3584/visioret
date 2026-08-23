import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { ApiError, fetchMetrics } from "../api/client";
import type { EvaluationMetric } from "../api/types";
import AnimatedNumber from "./AnimatedNumber";
import { classColors } from "../lib/classColors";

export default function ModelMetrics() {
  const [metrics, setMetrics] = useState<EvaluationMetric[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMetrics()
      .then(setMetrics)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load evaluation metrics."));
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">Model Performance</h2>

      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
          {error}
        </div>
      )}

      {!error && !metrics && <p className="text-sm text-slate-500 dark:text-slate-400">Loading...</p>}

      {!error && metrics && metrics.length === 0 && (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          No evaluation results recorded yet for the deployed model. Run <code className="font-mono">model/evaluate.py</code> (and
          optionally <code className="font-mono">model/evaluate_cross_dataset.py</code>) to populate this view.
        </p>
      )}

      {!error && metrics && metrics.length > 0 && (
        <div className="flex flex-col gap-8">
          {metrics.map((m) => (
            <MetricCard key={m.dataset_split} metric={m} />
          ))}
        </div>
      )}
    </div>
  );
}

function MetricCard({ metric }: { metric: EvaluationMetric }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="flex flex-col gap-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="flex flex-col gap-1">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">{metric.dataset_split_label}</h3>
        <p className="font-mono text-xs text-slate-400 dark:text-slate-500">
          {metric.model_version_label} &middot; evaluated {new Date(metric.evaluated_at).toLocaleString()}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Accuracy" value={metric.accuracy} />
        <StatTile label="Macro Precision" value={metric.precision_macro} />
        <StatTile label="Macro Recall" value={metric.recall_macro} />
        <StatTile label="Macro F1" value={metric.f1_macro} />
      </div>

      <PerClassTable perClassMetrics={metric.per_class_metrics} />
      <ConfusionMatrixTable confusionMatrix={metric.confusion_matrix} />
    </motion.div>
  );
}

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <motion.div
      whileHover={{ scale: 1.03 }}
      transition={{ duration: 0.15 }}
      className="flex flex-col gap-1 rounded-lg bg-slate-50 p-4 dark:bg-slate-800/50"
    >
      <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">{label}</span>
      <span className="font-mono text-2xl font-bold text-slate-900 dark:text-slate-50">
        <AnimatedNumber value={value * 100} suffix="%" />
      </span>
    </motion.div>
  );
}

function PerClassTable({ perClassMetrics }: { perClassMetrics: Record<string, { precision: number; recall: number; f1_score: number; support: number }> }) {
  const entries = Object.entries(perClassMetrics);
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[420px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs font-semibold uppercase tracking-wider text-slate-400 dark:border-slate-800 dark:text-slate-500">
            <th scope="col" className="py-2 pr-4">Class</th>
            <th scope="col" className="px-4 py-2 text-right">Precision</th>
            <th scope="col" className="px-4 py-2 text-right">Recall</th>
            <th scope="col" className="px-4 py-2 text-right">F1</th>
            <th scope="col" className="py-2 pl-4 text-right">Support</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([className, m]) => {
            const colors = classColors(className);
            return (
              <tr key={className} className="border-b border-slate-100 last:border-0 dark:border-slate-800/60">
                <td className="py-2 pr-4">
                  <span className="flex items-center gap-2 font-medium text-slate-900 dark:text-slate-50">
                    <span className={`h-2 w-2 shrink-0 rounded-full ${colors.dot}`} />
                    {className}
                  </span>
                </td>
                <td className="px-4 py-2 text-right font-mono tabular-nums text-slate-700 dark:text-slate-300">{m.precision.toFixed(3)}</td>
                <td className="px-4 py-2 text-right font-mono tabular-nums text-slate-700 dark:text-slate-300">{m.recall.toFixed(3)}</td>
                <td className="px-4 py-2 text-right font-mono tabular-nums text-slate-700 dark:text-slate-300">{m.f1_score.toFixed(3)}</td>
                <td className="py-2 pl-4 text-right font-mono tabular-nums text-slate-500 dark:text-slate-400">{m.support}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ConfusionMatrixTable({ confusionMatrix }: { confusionMatrix: { labels: string[]; matrix: number[][] } }) {
  const { labels, matrix } = confusionMatrix;
  return (
    <div className="overflow-x-auto">
      <table className="border-collapse text-sm">
        <caption className="mb-2 text-left text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
          Confusion matrix (rows = true label, columns = predicted)
        </caption>
        <thead>
          <tr>
            <th scope="col" className="p-2" />
            {labels.map((label) => (
              <th key={label} scope="col" className="p-2 text-center text-xs font-semibold text-slate-500 dark:text-slate-400">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => {
            const rowTotal = row.reduce((a, b) => a + b, 0) || 1;
            return (
              <tr key={labels[i]}>
                <th scope="row" className="p-2 text-right text-xs font-semibold text-slate-500 dark:text-slate-400">{labels[i]}</th>
                {row.map((count, j) => {
                  const isDiagonal = i === j;
                  const intensity = count / rowTotal;
                  return (
                    <td
                      key={j}
                      className="min-w-[56px] p-2 text-center font-mono tabular-nums"
                      style={{
                        backgroundColor: isDiagonal
                          ? `rgba(37, 99, 235, ${0.12 + intensity * 0.55})`
                          : count > 0
                            ? `rgba(225, 29, 72, ${0.08 + intensity * 0.35})`
                            : "transparent",
                      }}
                    >
                      <span className="text-slate-800 dark:text-slate-100">{count}</span>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
