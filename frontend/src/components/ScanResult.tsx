import { mediaUrl } from "../api/client";
import { classColors } from "../lib/classColors";
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
  const colors = classColors(predictedClass);

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <figure className="flex flex-col gap-2">
          <img
            src={mediaUrl(originalImageUrl)}
            alt="Original OCT scan"
            className="w-full rounded-lg border border-slate-200 shadow-sm dark:border-slate-800"
          />
          <figcaption className="text-center text-sm text-slate-500 dark:text-slate-400">Original image</figcaption>
        </figure>
        <figure className="flex flex-col gap-2">
          <img
            src={mediaUrl(gradcamOverlayUrl)}
            alt="Grad-CAM overlay highlighting the region the model focused on"
            className="w-full rounded-lg border border-slate-200 shadow-sm dark:border-slate-800"
          />
          <figcaption className="text-center text-sm text-slate-500 dark:text-slate-400">Grad-CAM overlay</figcaption>
        </figure>
      </div>

      <div className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-baseline justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Predicted class
          </span>
          <span className={`rounded-full px-3 py-1 font-mono text-sm font-semibold ${colors.badgeBg} ${colors.badgeText}`}>
            {(confidence * 100).toFixed(1)}% confidence
          </span>
        </div>
        <div className={`text-3xl font-bold ${colors.text}`}>{predictedClass}</div>
        <ProbabilityBars probabilities={probabilities} predictedClass={predictedClass} />
      </div>

      <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
          Why this region?
        </span>
        <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300">{explanation}</p>
      </div>
    </div>
  );
}
