import { motion, useReducedMotion } from "framer-motion";
import { canAnimate } from "../../lib/motion";
import type { Feedback } from "../../api/types";
import { ExplanationPanel } from "./ExplanationPanel";
import { PredictionSummary } from "./PredictionSummary";
import { ProbabilityDistribution } from "./ProbabilityDistribution";
import { ReviewPanel } from "./ReviewPanel";
import { ScanComparison } from "./ScanComparison";

interface Props {
  scanId: number;
  originalImageUrl: string;
  gradcamOverlayUrl: string;
  predictedClass: string;
  confidence: number;
  probabilities: Record<string, number>;
  explanation: string;
  feedback: Feedback | null;
  canReview: boolean;
}

/**
 * The scan analysis workspace, shared verbatim by the prediction page and the
 * scan detail page so there is exactly one implementation of "what a result
 * looks like".
 *
 * Layout is a two-column workspace on large screens: imaging takes the wide
 * left column (it is the object being studied), and a narrower right rail
 * carries the readout in reading order -- verdict, distribution,
 * interpretation, then review. The rail sticks while the images are inspected.
 * Below `xl` the rail drops underneath, preserving the same order.
 */
export function ScanAnalysis({
  scanId,
  originalImageUrl,
  gradcamOverlayUrl,
  predictedClass,
  confidence,
  probabilities,
  explanation,
  feedback,
  canReview,
}: Props) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      initial={canAnimate(reduceMotion) ? { opacity: 0, y: 10 } : false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="grid grid-cols-1 items-start gap-4 xl:grid-cols-[minmax(0,1fr)_380px]"
    >
      <ScanComparison
        originalImageUrl={originalImageUrl}
        gradcamOverlayUrl={gradcamOverlayUrl}
      />

      <aside
        aria-labelledby="analysis-heading"
        className="divide-y divide-line border border-line bg-surface rounded-[3px] xl:sticky xl:top-[72px]"
      >
        <h2 id="analysis-heading" className="sr-only">
          Analysis
        </h2>
        <PredictionSummary predictedClass={predictedClass} confidence={confidence} />
        <ProbabilityDistribution probabilities={probabilities} predictedClass={predictedClass} />
        <ExplanationPanel explanation={explanation} />
        <ReviewPanel
          scanId={scanId}
          predictedClass={predictedClass}
          availableClasses={Object.keys(probabilities)}
          initialFeedback={feedback}
          canReview={canReview}
        />
      </aside>
    </motion.div>
  );
}
