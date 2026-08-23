import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { ApiError, submitFeedback } from "../api/client";
import type { Feedback } from "../api/types";

interface Props {
  scanId: number;
  predictedClass: string;
  availableClasses: string[];
  initialFeedback: Feedback | null;
}

export default function FeedbackForm({ scanId, predictedClass, availableClasses, initialFeedback }: Props) {
  const [feedback, setFeedback] = useState<Feedback | null>(initialFeedback);
  const [mode, setMode] = useState<"idle" | "correcting">("idle");
  const [correctedClass, setCorrectedClass] = useState(
    availableClasses.find((c) => c !== predictedClass) ?? "",
  );
  const [comment, setComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function markCorrect() {
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await submitFeedback(scanId, { is_correct: true });
      setFeedback(result);
      setMode("idle");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save feedback.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitCorrection() {
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await submitFeedback(scanId, {
        is_correct: false,
        corrected_class: correctedClass,
        comment: comment.trim() || null,
      });
      setFeedback(result);
      setMode("idle");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save feedback.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function startEditing() {
    setCorrectedClass(feedback?.corrected_class ?? availableClasses.find((c) => c !== predictedClass) ?? "");
    setComment(feedback?.comment ?? "");
    setMode("correcting");
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
        Was this prediction correct?
      </h3>

      <AnimatePresence mode="wait">
        {mode === "idle" && feedback === null && (
          <motion.div
            key="ask"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="flex gap-2"
          >
            <motion.button
              whileTap={{ scale: 0.96 }}
              onClick={markCorrect}
              disabled={isSubmitting}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Correct
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.96 }}
              onClick={() => setMode("correcting")}
              disabled={isSubmitting}
              className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Incorrect
            </motion.button>
          </motion.div>
        )}

        {mode === "idle" && feedback !== null && (
          <motion.div
            key="reviewed"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="flex flex-col gap-2"
          >
            {feedback.is_correct ? (
              <p className="text-sm text-emerald-700 dark:text-emerald-400">
                You confirmed this prediction is correct.
              </p>
            ) : (
              <p className="text-sm text-rose-700 dark:text-rose-400">
                You flagged this as incorrect &mdash; should be <span className="font-semibold">{feedback.corrected_class}</span>.
                {feedback.comment && <span className="block text-slate-600 dark:text-slate-400">&ldquo;{feedback.comment}&rdquo;</span>}
              </p>
            )}
            <button
              onClick={startEditing}
              className="w-fit text-sm font-medium text-blue-700 hover:underline dark:text-blue-400"
            >
              Change my review
            </button>
          </motion.div>
        )}

        {mode === "correcting" && (
          <motion.div
            key="correcting"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="flex flex-col gap-3"
          >
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-slate-700 dark:text-slate-300">What should it have been?</span>
              <select
                value={correctedClass}
                onChange={(e) => setCorrectedClass(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
              >
                {availableClasses.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-slate-700 dark:text-slate-300">Comment (optional)</span>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={2}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                placeholder="Anything that would help explain the correction..."
              />
            </label>
            <div className="flex gap-2">
              <motion.button
                whileTap={{ scale: 0.96 }}
                onClick={submitCorrection}
                disabled={isSubmitting || !correctedClass}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-40 dark:bg-slate-100 dark:text-slate-900"
              >
                Submit correction
              </motion.button>
              <button
                onClick={() => setMode("idle")}
                disabled={isSubmitting}
                className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {error && (
        <p role="alert" className="text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}
