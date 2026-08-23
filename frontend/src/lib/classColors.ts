// Semantic color per disease class, used consistently across the probability
// bars, prediction badge, and history list so the same class always reads as
// the same color throughout the app. Deliberately not "urgent red for
// everything abnormal" -- CNV/DME (needs clinical follow-up) and DRUSEN (an
// early, often-monitored finding) read differently, and NORMAL reads as
// unambiguously clear.
interface ClassColorTokens {
  text: string;
  bar: string;
  badgeBg: string;
  badgeText: string;
  dot: string;
}

const CLASS_COLORS: Record<string, ClassColorTokens> = {
  CNV: {
    text: "text-amber-700 dark:text-amber-400",
    bar: "bg-amber-600 dark:bg-amber-500",
    badgeBg: "bg-amber-100 dark:bg-amber-900/50",
    badgeText: "text-amber-800 dark:text-amber-300",
    dot: "bg-amber-500",
  },
  DME: {
    text: "text-rose-700 dark:text-rose-400",
    bar: "bg-rose-600 dark:bg-rose-500",
    badgeBg: "bg-rose-100 dark:bg-rose-900/50",
    badgeText: "text-rose-800 dark:text-rose-300",
    dot: "bg-rose-500",
  },
  DRUSEN: {
    text: "text-violet-700 dark:text-violet-400",
    bar: "bg-violet-600 dark:bg-violet-500",
    badgeBg: "bg-violet-100 dark:bg-violet-900/50",
    badgeText: "text-violet-800 dark:text-violet-300",
    dot: "bg-violet-500",
  },
  NORMAL: {
    text: "text-emerald-700 dark:text-emerald-400",
    bar: "bg-emerald-600 dark:bg-emerald-500",
    badgeBg: "bg-emerald-100 dark:bg-emerald-900/50",
    badgeText: "text-emerald-800 dark:text-emerald-300",
    dot: "bg-emerald-500",
  },
};

const FALLBACK: ClassColorTokens = {
  text: "text-slate-700 dark:text-slate-300",
  bar: "bg-slate-500 dark:bg-slate-400",
  badgeBg: "bg-slate-100 dark:bg-slate-800",
  badgeText: "text-slate-700 dark:text-slate-300",
  dot: "bg-slate-400",
};

export function classColors(className: string): ClassColorTokens {
  return CLASS_COLORS[className.toUpperCase()] ?? FALLBACK;
}
