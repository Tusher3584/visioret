import { classColors, classDescription } from "../../lib/classColors";
import { AnimatedNumber } from "../ui/AnimatedNumber";

interface Props {
  predictedClass: string;
  confidence: number;
}

/** The headline verdict: what the model decided, and how strongly. */
export function PredictionSummary({ predictedClass, confidence }: Props) {
  const tokens = classColors(predictedClass);
  const description = classDescription(predictedClass);

  return (
    <div className="relative px-4 py-4">
      <span
        className={`absolute inset-y-0 left-0 w-[3px] ${tokens.fill}`}
        aria-hidden="true"
      />
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted">
        Predicted class
      </h3>
      <div className="mt-2 flex items-end justify-between gap-4">
        <div className="min-w-0">
          <p className={`text-3xl font-semibold leading-none tracking-tight ${tokens.text}`}>
            {predictedClass}
          </p>
          {description && <p className="mt-1.5 text-xs text-muted">{description}</p>}
        </div>
        <div className="shrink-0 text-right">
          <p className="font-mono text-2xl font-semibold leading-none text-ink">
            <AnimatedNumber value={confidence * 100} suffix="%" />
          </p>
          <p className="mt-1.5 text-[11px] uppercase tracking-[0.06em] text-subtle">Confidence</p>
        </div>
      </div>
    </div>
  );
}
