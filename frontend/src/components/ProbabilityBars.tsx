import { motion } from "framer-motion";
import { classColors } from "../lib/classColors";

interface Props {
  probabilities: Record<string, number>;
  predictedClass: string;
}

export default function ProbabilityBars({ probabilities, predictedClass }: Props) {
  const entries = Object.entries(probabilities).sort((a, b) => b[1] - a[1]);

  return (
    <div className="flex flex-col gap-2.5">
      {entries.map(([className, value], index) => {
        const isPredicted = className === predictedClass;
        const colors = classColors(className);
        return (
          <div key={className} className="flex items-center gap-3">
            <span
              className={`w-16 shrink-0 text-sm ${isPredicted ? `font-semibold ${colors.text}` : "text-slate-500 dark:text-slate-400"}`}
            >
              {className}
            </span>
            <div aria-hidden="true" className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${Math.max(value * 100, 1)}%` }}
                transition={{ duration: 0.6, delay: index * 0.06, ease: "easeOut" }}
                className={`h-full rounded-full ${isPredicted ? colors.bar : "bg-slate-300 dark:bg-slate-600"}`}
              />
            </div>
            <span className="w-14 shrink-0 text-right font-mono text-sm tabular-nums text-slate-500 dark:text-slate-400">
              {(value * 100).toFixed(1)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}
