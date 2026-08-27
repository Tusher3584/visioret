import { motion, useReducedMotion } from "framer-motion";
import { canAnimate } from "../../lib/motion";
import type { EvaluationMetric } from "../../api/types";
import { formatDateTime } from "../../lib/format";
import { AnimatedNumber } from "../ui/AnimatedNumber";
import { ConfusionMatrix } from "./ConfusionMatrix";
import { PerClassTable } from "./PerClassTable";

/**
 * One evaluated dataset split. Headline macro scores sit in a divided readout
 * strip, with the per-class breakdown and the confusion matrix side by side
 * on wide screens so the summary and the evidence for it are visible together.
 */
export function MetricsSection({ metric }: { metric: EvaluationMetric }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.section
      initial={canAnimate(reduceMotion) ? { opacity: 0, y: 12 } : false}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      aria-label={metric.dataset_split_label}
      className="border border-line bg-surface rounded-[3px]"
    >
      <header className="flex flex-col gap-1 border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold text-ink">{metric.dataset_split_label}</h2>
        <p className="font-mono text-[11px] text-subtle">
          {metric.model_version_label} · evaluated {formatDateTime(metric.evaluated_at)}
        </p>
      </header>

      <div className="grid grid-cols-2 divide-x divide-line border-b border-line md:grid-cols-4">
        <Readout label="Accuracy" value={metric.accuracy} emphasis />
        <Readout label="Macro F1" value={metric.f1_macro} emphasis />
        <Readout label="Macro precision" value={metric.precision_macro} />
        <Readout label="Macro recall" value={metric.recall_macro} />
      </div>

      <div className="grid grid-cols-1 gap-6 p-4 lg:grid-cols-[minmax(0,1fr)_auto]">
        <PerClassTable perClassMetrics={metric.per_class_metrics} />
        <ConfusionMatrix data={metric.confusion_matrix} />
      </div>
    </motion.section>
  );
}

function Readout({
  label,
  value,
  emphasis = false,
}: {
  label: string;
  value: number;
  emphasis?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1 px-4 py-3.5 [&:nth-child(3)]:border-t [&:nth-child(3)]:border-line [&:nth-child(4)]:border-t [&:nth-child(4)]:border-line md:[&:nth-child(3)]:border-t-0 md:[&:nth-child(4)]:border-t-0">
      <span className="text-[10px] font-semibold uppercase tracking-[0.09em] text-subtle">
        {label}
      </span>
      <span
        className={`font-mono font-semibold tabular-nums text-ink ${
          emphasis ? "text-2xl" : "text-lg"
        }`}
      >
        <AnimatedNumber value={value * 100} suffix="%" />
      </span>
    </div>
  );
}
