import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "framer-motion";
import { useEffect } from "react";

interface Props {
  value: number;
  decimals?: number;
  suffix?: string;
  className?: string;
}

function isHidden() {
  return typeof document !== "undefined" && document.visibilityState === "hidden";
}

/**
 * Counts up to `value` on mount so a measurement reads as something the system
 * just computed.
 *
 * Correctness before decoration: the count-up is driven by requestAnimationFrame,
 * which browsers throttle or halt in a hidden/background tab. Left unguarded the
 * number can freeze at its starting value -- a metrics readout stuck at "0.0%"
 * when the real figure is 95.2% is misinformation, not a missing animation. So
 * the true value is shown immediately whenever the animation cannot be trusted
 * to run (reduced motion, or a hidden tab), and any in-flight animation snaps to
 * the true value if the tab is backgrounded.
 */
export function AnimatedNumber({ value, decimals = 1, suffix = "", className }: Props) {
  const reduceMotion = useReducedMotion();
  const motionValue = useMotionValue(reduceMotion || isHidden() ? value : 0);
  const display = useTransform(motionValue, (v) => `${v.toFixed(decimals)}${suffix}`);

  useEffect(() => {
    if (reduceMotion || isHidden()) {
      motionValue.set(value);
      return;
    }

    const controls = animate(motionValue, value, { duration: 0.7, ease: "easeOut" });

    function onVisibilityChange() {
      if (document.visibilityState === "hidden") {
        controls.stop();
        motionValue.set(value);
      }
    }
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      controls.stop();
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [value, motionValue, reduceMotion]);

  return <motion.span className={className}>{display}</motion.span>;
}
