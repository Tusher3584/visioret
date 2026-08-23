import { useRef, useState } from "react";
import { ApiError, predict } from "../api/client";
import type { PredictionResponse } from "../api/types";
import ScanResult from "./ScanResult";

export default function UploadPredict() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notOctWarning, setNotOctWarning] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleFileChange(selected: File | null) {
    setFile(selected);
    setResult(null);
    setError(null);
    setNotOctWarning(null);
    setPreviewUrl(selected ? URL.createObjectURL(selected) : null);
  }

  async function handlePredict() {
    if (!file) return;
    setIsLoading(true);
    setError(null);
    setNotOctWarning(null);
    try {
      const response = await predict(file);
      setResult(response);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        // Not a system failure -- the image was read fine, it just isn't an OCT scan.
        setNotOctWarning(err.message);
      } else {
        setError(err instanceof ApiError ? err.message : "Something went wrong while running the prediction.");
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">1. Provide an image</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Upload an OCT scan (JPEG or PNG).</p>
      </div>

      <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png"
          onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
          className="block text-sm text-slate-600 file:mr-4 file:rounded-md file:border-0 file:bg-teal-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-teal-700 dark:text-slate-300"
        />
        <button
          onClick={handlePredict}
          disabled={!file || isLoading}
          className="rounded-md bg-slate-900 px-5 py-2 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-40 dark:bg-slate-100 dark:text-slate-900"
        >
          {isLoading ? "Running inference..." : "Predict"}
        </button>
      </div>

      {previewUrl && !result && (
        <img
          src={previewUrl}
          alt="Preview of the selected scan"
          className="max-w-xs rounded-lg border border-slate-200 dark:border-slate-700"
        />
      )}

      {notOctWarning && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/50 dark:text-amber-300">
          {notOctWarning}
        </div>
      )}

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
          {error}
        </div>
      )}

      {result && (
        <div>
          <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-slate-50">2. Results</h2>
          <ScanResult
            originalImageUrl={result.original_image_url}
            gradcamOverlayUrl={result.gradcam_overlay_url}
            predictedClass={result.predicted_class}
            confidence={result.confidence}
            probabilities={result.probabilities}
            explanation={result.explanation}
          />
        </div>
      )}
    </div>
  );
}
