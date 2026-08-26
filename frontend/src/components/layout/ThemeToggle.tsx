import { motion, useReducedMotion } from "framer-motion";
import { useTheme } from "../../context/ThemeContext";

/**
 * Circular theme switch.
 *
 * The icon shows the theme you'd get by clicking, not the one you're in: a sun
 * in dark mode (click for light), a moon in light mode (click for dark). They
 * counter-rotate through each other so the swap reads as one turn of a dial.
 *
 * The icon states are plain CSS classes with a CSS transition, deliberately
 * not a JS-driven animation. Which icon is showing is *information*, not
 * decoration, so its resting state has to be correct even when no animation
 * ever runs -- requestAnimationFrame is throttled in background tabs, and an
 * earlier AnimatePresence version could strand the button showing the wrong
 * symbol. CSS handles the tween; Framer is left to the tap/hover flourish,
 * where being skipped costs nothing. Reduced motion is covered by the global
 * transition-duration override in index.css.
 */
export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const reduceMotion = useReducedMotion();
  const isDark = theme === "dark";
  const goingTo = isDark ? "light" : "dark";

  const shown = "rotate-0 scale-100 opacity-100";
  const hidden = "opacity-0 scale-50";

  return (
    <motion.button
      type="button"
      onClick={toggleTheme}
      whileTap={reduceMotion ? undefined : { scale: 0.88 }}
      whileHover={reduceMotion ? undefined : { rotate: 12 }}
      transition={{ type: "spring", stiffness: 420, damping: 18 }}
      aria-label={`Switch to ${goingTo} theme`}
      title={`Switch to ${goingTo} theme`}
      className="relative grid h-8 w-8 shrink-0 place-items-center overflow-hidden rounded-full border border-line text-muted transition-colors hover:border-line-strong hover:text-ink"
    >
      <span
        className={`absolute grid place-items-center transition-all duration-300 ease-out ${
          isDark ? shown : `-rotate-[110deg] ${hidden}`
        }`}
      >
        <SunIcon />
      </span>

      <span
        className={`absolute grid place-items-center transition-all duration-300 ease-out ${
          isDark ? `rotate-[110deg] ${hidden}` : shown
        }`}
      >
        <MoonIcon />
      </span>
    </motion.button>
  );
}

function SunIcon() {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4.2" />
      <path d="M12 2v2.4M12 19.6V22M4.22 4.22l1.7 1.7M18.08 18.08l1.7 1.7M2 12h2.4M19.6 12H22M4.22 19.78l1.7-1.7M18.08 5.92l1.7-1.7" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M20.5 14.6A8.6 8.6 0 1 1 9.4 3.5a7 7 0 0 0 11.1 11.1z" />
    </svg>
  );
}
