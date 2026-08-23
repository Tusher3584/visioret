import { animate, useMotionValue, useTransform, motion } from "framer-motion";
import { useEffect } from "react";

interface Props {
  value: number;
  decimals?: number;
  suffix?: string;
  className?: string;
}

// Counts up from 0 to `value` on mount/change -- used for the confidence
// percentage so it reads as a live measurement rather than static text.
export default function AnimatedNumber({ value, decimals = 1, suffix = "", className }: Props) {
  const motionValue = useMotionValue(0);
  const rounded = useTransform(motionValue, (v) => `${v.toFixed(decimals)}${suffix}`);

  useEffect(() => {
    const controls = animate(motionValue, value, { duration: 0.8, ease: "easeOut" });
    return controls.stop;
  }, [value, motionValue]);

  return <motion.span className={className}>{rounded}</motion.span>;
}
