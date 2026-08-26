import type { ConfusionMatrix as ConfusionMatrixData } from "../../api/types";
import { formatCount } from "../../lib/format";

/** Cell tint never exceeds this, so cell text keeps AA contrast at full intensity. */
const MAX_ALPHA = 0.7;

/**
 * The confusion matrix, treated as the focal point of the metrics page.
 *
 * Cells are tinted by their share of the *row* (i.e. of all scans whose true
 * label is that row), so intensity reads as "what proportion of this class
 * went here" rather than being dominated by class imbalance. The diagonal is
 * tinted in the accent hue and errors in the error hue, making the
 * correct/incorrect structure legible before any number is read.
 */
export function ConfusionMatrix({ data }: { data: ConfusionMatrixData }) {
  const { labels, matrix } = data;

  return (
    <figure className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <figcaption>
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted">
            Confusion matrix
          </h3>
        </figcaption>
        <div className="flex items-center gap-3 text-[10px] text-subtle">
          <span className="inline-flex items-center gap-1.5">
            <span
              className="h-2.5 w-2.5 rounded-[1px]"
              style={{ backgroundColor: `rgb(var(--cm-correct) / 0.7)` }}
              aria-hidden="true"
            />
            Correct
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="h-2.5 w-2.5 rounded-[1px]"
              style={{ backgroundColor: `rgb(var(--cm-error) / 0.7)` }}
              aria-hidden="true"
            />
            Misclassified
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="border-collapse text-sm">
          <caption className="sr-only">
            Confusion matrix. Rows are the true label, columns are the label the model predicted.
            Each cell is the number of scans.
          </caption>
          <thead>
            <tr>
              <th scope="col" className="px-2 py-1.5">
                <span className="sr-only">True label</span>
              </th>
              <th
                scope="col"
                colSpan={labels.length}
                className="px-2 pb-1.5 text-center text-[10px] font-medium uppercase tracking-[0.12em] text-subtle"
              >
                Predicted
              </th>
            </tr>
            <tr>
              <th scope="col" className="px-2 py-1.5">
                <span className="sr-only">True label</span>
              </th>
              {labels.map((label) => (
                <th
                  key={label}
                  scope="col"
                  className="min-w-[62px] border-b border-line px-2 py-1.5 text-center font-mono text-[11px] font-medium text-muted"
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, i) => {
              const rowTotal = row.reduce((a, b) => a + b, 0) || 1;
              return (
                <tr key={labels[i]}>
                  <th
                    scope="row"
                    className="whitespace-nowrap border-r border-line py-1 pr-2.5 text-right font-mono text-[11px] font-medium text-muted"
                  >
                    {labels[i]}
                  </th>
                  {row.map((count, j) => {
                    const isDiagonal = i === j;
                    const share = count / rowTotal;
                    const alpha = count === 0 ? 0 : Math.max(share * MAX_ALPHA, 0.06);
                    return (
                      <td
                        key={labels[j]}
                        className="border border-line/60 px-2 py-2 text-center align-middle"
                        style={{
                          backgroundColor: `rgb(var(--cm-${
                            isDiagonal ? "correct" : "error"
                          }) / ${alpha})`,
                        }}
                      >
                        <span className="block font-mono text-xs font-medium tabular-nums text-ink">
                          {formatCount(count)}
                        </span>
                        <span className="mt-0.5 block font-mono text-[10px] tabular-nums text-muted">
                          {(share * 100).toFixed(0)}%
                        </span>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="text-[11px] leading-relaxed text-subtle">
        Rows are the true label, columns the predicted label. Percentages are of the row, so the
        diagonal reads as per-class recall.
      </p>
    </figure>
  );
}
