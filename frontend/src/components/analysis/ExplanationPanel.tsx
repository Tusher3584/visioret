interface Props {
  explanation: string;
}

/**
 * The interpretation half of the explainability story. Carries the Grad-CAM
 * intensity legend in its header so the reader connects the overlay they just
 * looked at ("this is where the model focused") to the clinical reasoning
 * ("this is why that region matters") without hunting between panels.
 */
export function ExplanationPanel({ explanation }: Props) {
  return (
    <section aria-labelledby="explanation-heading" className="px-4 py-3.5">
      <div className="flex items-center justify-between gap-3">
        <h3
          id="explanation-heading"
          className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted"
        >
          Interpretation
        </h3>
        <div className="flex items-center gap-1.5" aria-hidden="true">
          <span className="text-[10px] text-subtle">low</span>
          <span
            className="h-1.5 w-16 rounded-full"
            style={{
              background:
                "linear-gradient(to right, #00007f, #0000ff, #00ffff, #7fff7f, #ffff00, #ff0000, #7f0000)",
            }}
          />
          <span className="text-[10px] text-subtle">high</span>
        </div>
      </div>
      <p className="mt-2.5 text-[13px] leading-relaxed text-ink/90">{explanation}</p>
    </section>
  );
}
