import { useEffect, useState } from "react";
import { ApiError, fetchMetrics } from "../api/client";
import type { EvaluationMetric } from "../api/types";
import { PageHeader } from "../components/layout/PageHeader";
import { MetricsSection } from "../components/metrics/MetricsSection";
import { EmptyState, ErrorState, LoadingState } from "../components/states/States";

export function MetricsPage() {
  const [metrics, setMetrics] = useState<EvaluationMetric[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMetrics()
      .then(setMetrics)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load evaluation results."),
      );
  }, []);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Model evaluation"
        description="Held-out test results for the currently deployed checkpoint, reported per dataset split."
      />

      {error && <ErrorState message={error} />}
      {!error && !metrics && <LoadingState label="Loading evaluation results" />}

      {!error && metrics && metrics.length === 0 && (
        <EmptyState
          title="No evaluation results recorded"
          description="Run model/evaluate.py (and optionally model/evaluate_cross_dataset.py) against the deployed checkpoint to populate this page."
        />
      )}

      {!error && metrics && metrics.length > 0 && (
        <div className="flex flex-col gap-5">
          {metrics.map((metric) => (
            <MetricsSection key={metric.dataset_split} metric={metric} />
          ))}
          <p className="text-[11px] leading-relaxed text-subtle">
            Test splits are patient-disjoint: no patient contributing to a training set appears in
            the corresponding test set.
          </p>
        </div>
      )}
    </div>
  );
}
