import { motion, useReducedMotion } from "framer-motion";
import { classColors } from "../../lib/classColors";
import { percent } from "../../lib/format";
import { canAnimate } from "../../lib/motion";

interface Props {
  probabilities: Record<string, number>;
  predictedClass: string;
}

/**
 * Full four-class distribution, sorted descending. Only the winning class
 * carries its semantic colour; the rest stay neutral so the hierarchy is
 * unambiguous at a glance.
 */
export function ProbabilityDistribution({ probabilities, predictedClass }: Props) {
  const reduceMotion = useReducedMotion();
  // Bars grow from zero width; if the animation can't run they would sit empty
  // and misrepresent the distribution, so fall back to rendering them filled.
  const animated = canAnimate(reduceMotion);
  const entries = Object.entries(probabilities).sort((a, b) => b[1] - a[1]);

  return (
    <div className="flex flex-col gap-2 px-4 py-3.5">
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted">
        Class distribution
      </h3>
      <ul className="flex flex-col gap-2">
        {entries.map(([name, value], index) => {
          const isWinner = name === predictedClass;
          const tokens = classColors(name);
          return (
            <li key={name} className="flex items-center gap-2.5">
              <span
                className={`w-[62px] shrink-0 text-xs ${
                  isWinner ? `font-semibold ${tokens.text}` : "text-muted"
                }`}
              >
                {name}
              </span>
              <span
                aria-hidden="true"
                className="h-1.5 flex-1 overflow-hidden rounded-full bg-raised dark:bg-black/40"
              >
                <motion.span
                  className={`block h-full rounded-full ${
                    isWinner ? tokens.fill : "bg-line-strong"
                  }`}
                  initial={animated ? { width: 0 } : false}
                  animate={{ width: `${Math.max(value * 100, 0.8)}%` }}
                  transition={
                    animated
                      ? { duration: 0.55, delay: index * 0.05, ease: "easeOut" }
                      : { duration: 0 }
                  }
                />
              </span>
              <span
                className={`w-[52px] shrink-0 text-right font-mono text-xs tabular-nums ${
                  isWinner ? "text-ink" : "text-subtle"
                }`}
              >
                {percent(value)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
