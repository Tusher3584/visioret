import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useState } from "react";
import { ApiError, submitFeedback } from "../../api/client";
import type { Feedback } from "../../api/types";
import { formatDateTime } from "../../lib/format";
import { Button } from "../ui/Button";

interface Props {
  scanId: number;
  predictedClass: string;
  availableClasses: string[];
  initialFeedback: Feedback | null;
  /** Whether this caller holds the reviewer role. Server-enforced; this only
   *  decides what to show. */
  canReview: boolean;
}

/**
 * Researcher review of the prediction. Intentionally the quietest panel in
 * the workspace -- it is a secondary action that should stay available
 * without competing with the imaging analysis for attention.
 */
export function ReviewPanel({
  scanId,
  predictedClass,
  availableClasses,
  initialFeedback,
  canReview,
}: Props) {
  const reduceMotion = useReducedMotion();
  const [feedback, setFeedback] = useState<Feedback | null>(initialFeedback);
  const [mode, setMode] = useState<"idle" | "correcting">("idle");
  const [correctedClass, setCorrectedClass] = useState(
    availableClasses.find((c) => c !== predictedClass) ?? "",
  );
  const [comment, setComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(payload: Parameters<typeof submitFeedback>[1]) {
    setIsSubmitting(true);
    setError(null);
    try {
      setFeedback(await submitFeedback(scanId, payload));
      setMode("idle");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this review.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function startEditing() {
    setCorrectedClass(
      feedback?.corrected_class ?? availableClasses.find((c) => c !== predictedClass) ?? "",
    );
    setComment(feedback?.comment ?? "");
    setMode("correcting");
  }

  const motionProps = reduceMotion
    ? {}
    : {
        initial: { opacity: 0, y: -4 },
        animate: { opacity: 1, y: 0 },
        exit: { opacity: 0, y: -4 },
        transition: { duration: 0.16 },
      };

  return (
    <section aria-labelledby="review-heading" className="px-4 py-3.5">
      <h3
        id="review-heading"
        className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted"
      >
        Researcher review
      </h3>

      <AnimatePresence mode="wait">
        {/* No reviewer role: show any existing review read-only, and say plainly
            why the controls are absent rather than silently hiding them. */}
        {!canReview && feedback === null && (
          <motion.p key="locked" {...motionProps} className="mt-2.5 text-xs leading-relaxed text-muted">
            Not yet reviewed. Recording a correction requires the{" "}
            <span className="font-medium text-ink">reviewer</span> role, because corrections are
            training-grade labels.
          </motion.p>
        )}

        {canReview && mode === "idle" && feedback === null && (
          <motion.div key="ask" {...motionProps} className="mt-2.5 flex items-center gap-2">
            <Button
              size="sm"
              variant="positive"
              onClick={() => send({ is_correct: true })}
              disabled={isSubmitting}
            >
              Correct
            </Button>
            <Button
              size="sm"
              variant="negative"
              onClick={() => setMode("correcting")}
              disabled={isSubmitting}
            >
              Incorrect
            </Button>
          </motion.div>
        )}

        {mode === "idle" && feedback !== null && (
          <motion.div key="done" {...motionProps} className="mt-2.5 flex flex-col gap-1.5">
            <div className="flex items-start gap-2">
              <span
                className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                  feedback.is_correct ? "bg-emerald-500" : "bg-rose-500"
                }`}
                aria-hidden="true"
              />
              <p className="text-xs leading-relaxed text-ink">
                {feedback.is_correct ? (
                  <>Marked <span className="font-semibold">correct</span>.</>
                ) : (
                  <>
                    Marked <span className="font-semibold">incorrect</span> — recorded as{" "}
                    <span className="font-semibold">{feedback.corrected_class}</span>.
                  </>
                )}
                {feedback.comment && (
                  <span className="mt-1 block text-muted">“{feedback.comment}”</span>
                )}
                <span className="mt-1 block font-mono text-[10px] text-subtle">
                  {feedback.reviewer_name ? `${feedback.reviewer_name} · ` : ""}
                  {formatDateTime(feedback.reviewed_at)}
                </span>
              </p>
            </div>
            {canReview && (
              <button
                onClick={startEditing}
                className="w-fit text-xs font-medium text-accent hover:underline"
              >
                Change review
              </button>
            )}
          </motion.div>
        )}

        {mode === "correcting" && (
          <motion.div key="edit" {...motionProps} className="mt-2.5 flex flex-col gap-2.5">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-ink">Correct class</span>
              <select
                value={correctedClass}
                onChange={(e) => setCorrectedClass(e.target.value)}
                className="rounded-[3px] border border-line-strong bg-surface px-2.5 py-1.5 text-xs text-ink"
              >
                {availableClasses.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-ink">Note (optional)</span>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={2}
                placeholder="What led you to a different reading?"
                className="rounded-[3px] border border-line-strong bg-surface px-2.5 py-1.5 text-xs text-ink placeholder:text-subtle"
              />
            </label>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="primary"
                disabled={isSubmitting || !correctedClass}
                onClick={() =>
                  send({
                    is_correct: false,
                    corrected_class: correctedClass,
                    comment: comment.trim() || null,
                  })
                }
              >
                {isSubmitting ? "Saving…" : "Save review"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setMode("idle")} disabled={isSubmitting}>
                Cancel
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {error && (
        <p role="alert" className="mt-2 text-xs text-rose-700 dark:text-rose-300">
          {error}
        </p>
      )}
    </section>
  );
}
