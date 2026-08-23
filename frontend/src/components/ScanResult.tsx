import { motion, type Variants } from "framer-motion";
import { mediaUrl } from "../api/client";
import type { Feedback } from "../api/types";
import { classColors } from "../lib/classColors";
import AnimatedNumber from "./AnimatedNumber";
import FeedbackForm from "./FeedbackForm";
import ProbabilityBars from "./ProbabilityBars";

interface Props {
  scanId: number;
  originalImageUrl: string;
  gradcamOverlayUrl: string;
  predictedClass: string;
  confidence: number;
  probabilities: Record<string, number>;
  explanation: string;
  feedback: Feedback | null;
}

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" } },
};

export default function ScanResult({
  scanId,
  originalImageUrl,
  gradcamOverlayUrl,
  predictedClass,
  confidence,
  probabilities,
  explanation,
  feedback,
}: Props) {
  const colors = classColors(predictedClass);

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.div variants={item} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <figure className="flex flex-col gap-2">
          <motion.img
            whileHover={{ scale: 1.02 }}
            transition={{ duration: 0.2 }}
            src={mediaUrl(originalImageUrl)}
            alt="Original OCT scan"
            className="w-full rounded-lg border border-slate-200 shadow-sm dark:border-slate-800"
          />
          <figcaption className="text-center text-sm text-slate-500 dark:text-slate-400">Original image</figcaption>
        </figure>
        <figure className="flex flex-col gap-2">
          <motion.img
            whileHover={{ scale: 1.02 }}
            transition={{ duration: 0.2 }}
            src={mediaUrl(gradcamOverlayUrl)}
            alt="Grad-CAM overlay highlighting the region the model focused on"
            className="w-full rounded-lg border border-slate-200 shadow-sm dark:border-slate-800"
          />
          <figcaption className="text-center text-sm text-slate-500 dark:text-slate-400">Grad-CAM overlay</figcaption>
        </figure>
      </motion.div>

      <motion.div
        variants={item}
        className={`relative flex flex-col gap-4 overflow-hidden rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900`}
      >
        <span className={`absolute inset-x-0 top-0 h-1 ${colors.bar}`} aria-hidden="true" />
        <div className="flex items-baseline justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Predicted class
          </h3>
          <span className={`rounded-full px-3 py-1 font-mono text-sm font-semibold ${colors.badgeBg} ${colors.badgeText}`}>
            <AnimatedNumber value={confidence * 100} suffix="% confidence" />
          </span>
        </div>
        <div className={`text-3xl font-bold ${colors.text}`}>{predictedClass}</div>
        <ProbabilityBars probabilities={probabilities} predictedClass={predictedClass} />
      </motion.div>

      <motion.div
        variants={item}
        className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
          Why this region?
        </h3>
        <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300">{explanation}</p>
      </motion.div>

      <motion.div variants={item}>
        <FeedbackForm
          scanId={scanId}
          predictedClass={predictedClass}
          availableClasses={Object.keys(probabilities)}
          initialFeedback={feedback}
        />
      </motion.div>
    </motion.div>
  );
}
