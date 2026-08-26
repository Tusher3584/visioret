/**
 * Whether entrance animations can be trusted to actually run right now.
 *
 * Browsers throttle or halt requestAnimationFrame in hidden/background tabs,
 * which is what drives Framer Motion. Any animation that starts from a "zero"
 * state (a 0% bar, a 0.0% counter) can therefore get stuck showing something
 * factually wrong rather than merely un-animated. Components that animate
 * *from* an empty state should skip the animation entirely when this returns
 * false and render the true value immediately.
 */
export function canAnimate(reduceMotion: boolean | null): boolean {
  if (reduceMotion) return false;
  if (typeof document === "undefined") return false;
  return document.visibilityState !== "hidden";
}
