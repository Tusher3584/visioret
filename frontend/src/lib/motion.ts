/**
 * Whether entrance animations can be trusted to actually run right now.
 *
 * Browsers throttle or halt requestAnimationFrame in hidden/background tabs,
 * which is what drives Framer Motion. Any animation that starts from a "zero"
 * state (a 0% bar, a 0.0% counter) can therefore get stuck showing something
 * factually wrong rather than merely un-animated. Components that animate
 * *from* an empty state should skip the animation entirely when this returns
 * false and render the true value immediately.
 *
 * "Zero state" includes opacity: 0, which is the same hazard wearing a
 * different hat -- the content is not merely un-animated, it is invisible.
 * Every entrance animation in this codebase now goes through here rather
 * than checking useReducedMotion alone. Measured before that change: with
 * document.visibilityState === "hidden", the route wrapper in App.tsx held
 * computed opacity 0 indefinitely, so a page opened in a background tab had
 * its entire content present in the DOM and invisible on screen.
 *
 * Checking reduceMotion alone is the trap: it looks like it covers the
 * "don't animate" case, and it covers only half of it.
 */
export function canAnimate(reduceMotion: boolean | null): boolean {
  if (reduceMotion) return false;
  if (typeof document === "undefined") return false;
  return document.visibilityState !== "hidden";
}
