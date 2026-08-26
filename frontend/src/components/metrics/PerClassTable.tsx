import type { PerClassMetric } from "../../api/types";
import { classColors } from "../../lib/classColors";
import { fixed, formatCount } from "../../lib/format";

interface Props {
  perClassMetrics: Record<string, PerClassMetric>;
}

/**
 * Per-class precision / recall / F1 / support. The inline bar behind each
 * score makes the weakest class visible at a glance without having to read
 * and compare twelve numbers.
 */
export function PerClassTable({ perClassMetrics }: Props) {
  const entries = Object.entries(perClassMetrics);

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted">
        Per-class performance
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[380px] border-collapse text-sm">
          <caption className="sr-only">Precision, recall, F1 score and support for each class</caption>
          <thead>
            <tr className="border-b border-line">
              <th
                scope="col"
                className="py-2 pr-3 text-left text-[11px] font-semibold uppercase tracking-[0.09em] text-subtle"
              >
                Class
              </th>
              {["Precision", "Recall", "F1"].map((label) => (
                <th
                  key={label}
                  scope="col"
                  className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-[0.09em] text-subtle"
                >
                  {label}
                </th>
              ))}
              <th
                scope="col"
                className="py-2 pl-3 text-right text-[11px] font-semibold uppercase tracking-[0.09em] text-subtle"
              >
                Support
              </th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([name, metric]) => {
              const tokens = classColors(name);
              return (
                <tr key={name} className="border-b border-line/60 last:border-0">
                  <th scope="row" className="py-2 pr-3 text-left">
                    <span className="inline-flex items-center gap-1.5">
                      <span
                        className={`h-2 w-2 shrink-0 rounded-[1px] ${tokens.dot}`}
                        aria-hidden="true"
                      />
                      <span className={`text-xs font-medium ${tokens.text}`}>{name}</span>
                    </span>
                  </th>
                  <ScoreCell value={metric.precision} fill={tokens.fill} />
                  <ScoreCell value={metric.recall} fill={tokens.fill} />
                  <ScoreCell value={metric.f1_score} fill={tokens.fill} />
                  <td className="py-2 pl-3 text-right font-mono text-xs tabular-nums text-subtle">
                    {formatCount(metric.support)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ScoreCell({ value, fill }: { value: number; fill: string }) {
  return (
    <td className="px-3 py-2">
      <span className="flex items-center justify-end gap-2">
        <span
          aria-hidden="true"
          className="hidden h-1 w-12 overflow-hidden rounded-full bg-raised dark:bg-black/40 sm:block"
        >
          <span
            className={`block h-full rounded-full ${fill}`}
            style={{ width: `${Math.max(value * 100, 2)}%` }}
          />
        </span>
        <span className="w-11 text-right font-mono text-xs tabular-nums text-ink">
          {fixed(value)}
        </span>
      </span>
    </td>
  );
}
