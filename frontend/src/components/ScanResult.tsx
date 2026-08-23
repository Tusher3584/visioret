import { mediaUrl } from "../api/client";
import ProbabilityBars from "./ProbabilityBars";

interface Props {
  originalImageUrl: string;
  gradcamOverlayUrl: string;
  predictedClass: string;
  confidence: number;
  probabilities: Record<string, number>;
  explanation: string;
}

export default function ScanResult({
  originalImageUrl,
  gradcamOverlayUrl,
  predictedClass,
  confidence,
  probabilities,
  explanation,
}: Props) {
  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <figure className="flex flex-col gap-2">
          <img
            src={mediaUrl(originalImageUrl)}
            alt="Original OCT scan"
            className="w-full rounded-lg border border-slate-200 dark:border-slate-700"
          />
          <figcaption className="text-center text-sm text-slate-500 dark:text-slate-400">Original image</figcaption>
        </figure>
        <figure className="flex flex-col gap-2">
          <img
            src={mediaUrl(gradcamOverlayUrl)}
            alt="Grad-CAM overlay highlighting the region the model focused on"
            className="w-full rounded-lg border border-slate-200 dark:border-slate-700"
          />
          <figcaption className="text-center text-sm text-slate-500 dark:text-slate-400">Grad-CAM overlay</figcaption>
        </figure>
      </div>

      <div className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-slate-50 p-5 dark:border-slate-700 dark:bg-slate-800/50">
        <div className="flex items-baseline justify-between">
          <span className="text-sm font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Predicted class
          </span>
          <span className="rounded-full bg-teal-100 px-3 py-1 text-sm font-semibold text-teal-800 dark:bg-teal-900/50 dark:text-teal-300">
            {(confidence * 100).toFixed(1)}% confidence
          </span>
        </div>
        <div className="text-3xl font-bold text-slate-900 dark:text-slate-50">{predictedClass}</div>
        <ProbabilityBars probabilities={probabilities} predictedClass={predictedClass} />
      </div>

      <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900/50">
        <span className="text-sm font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Why this region?
        </span>
        <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300">{explanation}</p>
      </div>
    </div>
  );
}
