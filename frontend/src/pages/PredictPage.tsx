import { useState } from "react";
import { ApiError, predict } from "../api/client";
import type { PredictionResponse } from "../api/types";
import { ScanAnalysis } from "../components/analysis/ScanAnalysis";
import { PageHeader } from "../components/layout/PageHeader";
import { ErrorState, OODRejectionState } from "../components/states/States";
import { Button } from "../components/ui/Button";
import { UploadWorkspace } from "../components/upload/UploadWorkspace";
import { useAuth } from "../context/AuthContext";
import { CLASS_DESCRIPTIONS, classColors } from "../lib/classColors";

export function PredictPage() {
  const { isReviewer } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rejection, setRejection] = useState<string | null>(null);

  function selectFile(selected: File | null) {
    setFile(selected);
    setResult(null);
    setError(null);
    setRejection(null);
    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return selected ? URL.createObjectURL(selected) : null;
    });
  }

  function reset() {
    selectFile(null);
  }

  async function analyze() {
    if (!file) return;
    setIsLoading(true);
    setError(null);
    setRejection(null);
    try {
      setResult(await predict(file));
    } catch (err) {
      // 422 is the OOD gate declining the image -- a valid decision, not a failure.
      if (err instanceof ApiError && err.status === 422) {
        setRejection(err.message);
      } else {
        setError(
          err instanceof ApiError ? err.message : "The analysis could not be completed.",
        );
      }
    } finally {
      setIsLoading(false);
    }
  }

  if (result) {
    return (
      <div className="flex flex-col gap-5">
        <PageHeader
          title="Analysis"
          description="Model attention and classification for the scan you just submitted."
          above={
            <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-subtle">
              Scan #{result.scan_id}
            </span>
          }
          actions={
            <Button variant="secondary" size="sm" onClick={reset}>
              Analyze another scan
            </Button>
          }
        />
        <ScanAnalysis
          scanId={result.scan_id}
          originalImageUrl={result.original_image_url}
          gradcamOverlayUrl={result.gradcam_overlay_url}
          predictedClass={result.predicted_class}
          confidence={result.confidence}
          probabilities={result.probabilities}
          explanation={result.explanation}
          feedback={null}
          canReview={isReviewer}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Predict"
        description="Submit a single retinal OCT B-scan for classification and a Grad-CAM explanation."
      />

      {rejection && (
        <OODRejectionState
          message={rejection}
          previewUrl={previewUrl}
          onReset={
            <Button variant="secondary" size="sm" onClick={reset}>
              Choose a different image
            </Button>
          }
        />
      )}

      {error && <ErrorState message={error} />}

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <UploadWorkspace
          file={file}
          previewUrl={previewUrl}
          isLoading={isLoading}
          onFileChange={selectFile}
          onAnalyze={analyze}
        />
        <ReferencePanel />
      </div>
    </div>
  );
}

/**
 * Static domain reference, not backend data -- it documents the fixed
 * four-class taxonomy the model was trained on and what the pipeline does,
 * so the workspace is informative before a scan is submitted.
 */
function ReferencePanel() {
  return (
    <aside
      aria-label="Reference"
      className="divide-y divide-line border border-line bg-surface rounded-[3px]"
    >
      <div className="px-4 py-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted">
          Classification targets
        </h2>
        <ul className="mt-2.5 flex flex-col gap-2">
          {Object.entries(CLASS_DESCRIPTIONS).map(([name, description]) => {
            const tokens = classColors(name);
            return (
              <li key={name} className="flex items-start gap-2">
                <span
                  className={`mt-[5px] h-2 w-2 shrink-0 rounded-[1px] ${tokens.dot}`}
                  aria-hidden="true"
                />
                <span className="min-w-0">
                  <span className={`block text-xs font-semibold ${tokens.text}`}>{name}</span>
                  <span className="block text-[11px] leading-snug text-muted">{description}</span>
                </span>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="px-4 py-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted">
          How a scan is handled
        </h2>
        <ol className="mt-2.5 flex flex-col gap-2 text-[11px] leading-snug text-muted">
          <Step n={1} title="Validation">
            The image is checked to confirm it really is an OCT B-scan. Anything else is declined
            rather than guessed at.
          </Step>
          <Step n={2} title="Classification">
            A ResNet-50 assigns one of the four classes and a probability for each.
          </Step>
          <Step n={3} title="Explanation">
            Grad-CAM highlights the region that drove the decision.
          </Step>
        </ol>
      </div>

      <p className="px-4 py-3 text-[11px] leading-snug text-subtle">
        Research and demonstration tool. Not an approved clinical diagnostic device.
      </p>
    </aside>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="flex gap-2">
      <span className="font-mono text-[10px] text-subtle">{n}</span>
      <span>
        <span className="font-medium text-ink">{title}. </span>
        {children}
      </span>
    </li>
  );
}
