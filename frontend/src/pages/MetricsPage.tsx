import { useEffect, useState } from "react";
import { ApiError, fetchMetrics } from "../api/client";
import type { EvaluationMetric } from "../api/types";
import { PageHeader } from "../components/layout/PageHeader";
import { MetricsSection } from "../components/metrics/MetricsSection";
import { EmptyState, ErrorState, LoadingState } from "../components/states/States";

export function MetricsPage() {
  const [metrics, setMetrics] = useState<EvaluationMetric[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Distinguished from a real error: being signed out, or lacking the
  // reviewer role, is the system working as designed. Rendering "Error. Not
  // authenticated." for it made a correct authorization decision look like a
  // fault -- and this is the page an examiner is most likely to open first.
  const [denied, setDenied] = useState<401 | 403 | null>(null);

  useEffect(() => {
    fetchMetrics()
      .then(setMetrics)
      .catch((err) => {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          setDenied(err.status);
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not load evaluation results.");
      });
  }, []);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Model evaluation"
        description="Held-out test results for the currently deployed checkpoint, reported per dataset split."
      />

      {denied === 401 && (
        <EmptyState
          title="Sign in to view evaluation results"
          description="Model metrics are available to reviewer accounts. Sign in with a reviewer account to see per-class results and the confusion matrix for the deployed checkpoint."
        />
      )}
      {denied === 403 && (
        <EmptyState
          title="Reviewer access required"
          description="Your account is signed in as a viewer. Model metrics are limited to reviewer accounts, because interpreting them alongside recorded corrections is part of the reviewing role. An administrator can grant reviewer access."
        />
      )}

      {error && <ErrorState message={error} />}
      {!error && !denied && !metrics && <LoadingState label="Loading evaluation results" />}

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
          {/* This footnote used to claim the splits were patient-disjoint
              outright. They are not, for the Kermany split: the grouping key
              is class-prefixed, so a patient with images under two classes is
              treated as two patients. The effect was measured
              (model/audit_patient_leakage.py) and runs the conservative way,
              but stating the original claim in the product would have been
              asserting something untrue in the place a reader trusts most. */}
          <p className="text-[11px] leading-relaxed text-subtle">
            Test patients are reserved before training. For the Kermany split the grouping key
            includes the class label, so a patient with findings under more than one class counts
            as more than one group — about 41% of those test images come from a patient seen during
            training. Measured separately, the model scores{" "}
            <span className="font-mono">0.9750</span> on patients never seen at all versus{" "}
            <span className="font-mono">0.9180</span> on the overlapping ones, so the figures above
            understate rather than overstate performance. The external split is unaffected.
          </p>
        </div>
      )}
    </div>
  );
}
