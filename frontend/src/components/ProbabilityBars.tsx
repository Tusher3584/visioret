interface Props {
  probabilities: Record<string, number>;
  predictedClass: string;
}

export default function ProbabilityBars({ probabilities, predictedClass }: Props) {
  const entries = Object.entries(probabilities).sort((a, b) => b[1] - a[1]);

  return (
    <div className="flex flex-col gap-2">
      {entries.map(([className, value]) => {
        const isPredicted = className === predictedClass;
        return (
          <div key={className} className="flex items-center gap-3">
            <span
              className={`w-16 shrink-0 text-sm ${
                isPredicted ? "font-semibold text-teal-700 dark:text-teal-400" : "text-slate-600 dark:text-slate-400"
              }`}
            >
              {className}
            </span>
            <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <div
                className={`h-full rounded-full ${isPredicted ? "bg-teal-600" : "bg-slate-400 dark:bg-slate-600"}`}
                style={{ width: `${Math.max(value * 100, 1)}%` }}
              />
            </div>
            <span className="w-14 shrink-0 text-right text-sm tabular-nums text-slate-500 dark:text-slate-400">
              {(value * 100).toFixed(1)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}
