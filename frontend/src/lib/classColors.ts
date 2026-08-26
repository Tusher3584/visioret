// Semantic colour per disease class. These are *data indicators*, not
// decoration -- they appear only where a class is being identified (the
// prediction readout, probability bars, archive rows, metrics tables), so a
// reader learns to recognise a class by colour anywhere in the app.
//
// Deliberately not "red = all abnormal": CNV/DME (need clinical follow-up)
// and DRUSEN (an early, usually-monitored finding) read differently, and
// NORMAL reads as unambiguously clear.
//
// All pairings verified for WCAG AA (>=4.5:1) against both the light
// (#ffffff) and dark (#0f131b) panel surfaces.

export interface ClassTokens {
  /** Class name set in its own colour, on a panel surface. */
  text: string;
  /** Solid fill for bars / indicator strips. */
  fill: string;
  /** Small square/dot marker. */
  dot: string;
  /** Tinted background + readable text, for chips. */
  chip: string;
  /** Border tone for the accent strip on the prediction readout. */
  border: string;
}

const CLASS_TOKENS: Record<string, ClassTokens> = {
  CNV: {
    text: "text-amber-700 dark:text-amber-400",
    fill: "bg-amber-600 dark:bg-amber-400",
    dot: "bg-amber-500",
    chip: "bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300",
    border: "border-amber-600 dark:border-amber-400",
  },
  DME: {
    text: "text-rose-700 dark:text-rose-400",
    fill: "bg-rose-600 dark:bg-rose-400",
    dot: "bg-rose-500",
    chip: "bg-rose-50 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300",
    border: "border-rose-600 dark:border-rose-400",
  },
  DRUSEN: {
    text: "text-violet-700 dark:text-violet-400",
    fill: "bg-violet-600 dark:bg-violet-400",
    dot: "bg-violet-500",
    chip: "bg-violet-50 text-violet-800 dark:bg-violet-950/60 dark:text-violet-300",
    border: "border-violet-600 dark:border-violet-400",
  },
  NORMAL: {
    text: "text-emerald-700 dark:text-emerald-400",
    fill: "bg-emerald-600 dark:bg-emerald-400",
    dot: "bg-emerald-500",
    chip: "bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300",
    border: "border-emerald-600 dark:border-emerald-400",
  },
};

const FALLBACK: ClassTokens = {
  text: "text-ink",
  fill: "bg-line-strong",
  dot: "bg-line-strong",
  chip: "bg-raised text-muted",
  border: "border-line-strong",
};

export function classColors(className: string): ClassTokens {
  return CLASS_TOKENS[className.toUpperCase()] ?? FALLBACK;
}

/** One-line clinical gloss, shown as supporting context beside a class name. */
export const CLASS_DESCRIPTIONS: Record<string, string> = {
  CNV: "Choroidal neovascularization",
  DME: "Diabetic macular edema",
  DRUSEN: "Drusen deposits",
  NORMAL: "No abnormality detected",
};

export function classDescription(className: string): string {
  return CLASS_DESCRIPTIONS[className.toUpperCase()] ?? "";
}
