/**
 * CustomCursor — a soft ink dot that follows the mouse with spring lag.
 * On hoverable elements (marked with data-cursor="focus"), the dot expands.
 * Hidden on touch devices.
 *
 * The spring gives it that "ink meeting paper" resistance instead of a
 * hard pixel-perfect follow.
 */
import { motion, useMotionValue, useSpring } from "motion/react";
import { useEffect, useState } from "react";

const SPRING = { damping: 30, stiffness: 400, mass: 0.6 };

export function CustomCursor() {
  const x = useMotionValue(-100);
  const y = useMotionValue(-100);
  const sx = useSpring(x, SPRING);
  const sy = useSpring(y, SPRING);
  const [focused, setFocused] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    // Bail on coarse pointers (mobile / touch) — no custom cursor.
    if (window.matchMedia("(hover: none)").matches) return;

    setVisible(true);

    const onMove = (e: MouseEvent) => {
      x.set(e.clientX);
      y.set(e.clientY);
    };
    const onOver = (e: MouseEvent) => {
      const el = e.target as HTMLElement;
      const wantsFocus = !!el.closest(
        'a, button, [role="button"], input, textarea, [data-cursor="focus"]'
      );
      setFocused(wantsFocus);
    };
    const onLeave = () => setVisible(false);
    const onEnter = () => setVisible(true);

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseover", onOver);
    document.addEventListener("mouseleave", onLeave);
    document.addEventListener("mouseenter", onEnter);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseover", onOver);
      document.removeEventListener("mouseleave", onLeave);
      document.removeEventListener("mouseenter", onEnter);
    };
  }, [x, y]);

  if (!visible) return null;

  return (
    <>
      <motion.div
        aria-hidden
        style={{
          x: sx,
          y: sy,
          translateX: "-50%",
          translateY: "-50%",
        }}
        className="pointer-events-none fixed left-0 top-0 z-[200] mix-blend-difference"
      >
        <motion.div
          animate={{
            width: focused ? 44 : 10,
            height: focused ? 44 : 10,
            opacity: focused ? 0.65 : 0.95,
          }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="rounded-full bg-white"
        />
      </motion.div>
    </>
  );
}
