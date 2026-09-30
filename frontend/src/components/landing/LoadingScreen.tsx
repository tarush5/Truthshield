import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useRef, useState } from 'react';

const WORDS = ['Verify', 'Investigate', 'Trust'];
const DURATION = 2700;

export function LoadingScreen({ onComplete }: { onComplete: () => void }) {
  const [count, setCount] = useState(0);
  const [word, setWord] = useState(0);
  const done = useRef(false);

  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const total = reduced ? 300 : DURATION;
    const start = performance.now();
    let frame = 0;

    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / total);
      setCount(Math.round(progress * 100));
      if (progress < 1) {
        frame = requestAnimationFrame(tick);
      } else if (!done.current) {
        done.current = true;
        setTimeout(onComplete, reduced ? 0 : 400);
      }
    };
    frame = requestAnimationFrame(tick);
    const words = setInterval(() => setWord((w) => (w + 1) % WORDS.length), 900);
    return () => {
      cancelAnimationFrame(frame);
      clearInterval(words);
    };
  }, [onComplete]);

  return (
    <motion.div
      className="fixed inset-0 z-[9999] bg-bg"
      // Never block the page underneath while fading out.
      exit={{ opacity: 0, pointerEvents: 'none' }}
      transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
      role="progressbar"
      aria-label="Loading TruthShield"
      aria-valuenow={count}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <motion.p
        className="absolute left-6 top-6 text-xs uppercase tracking-[0.3em] text-muted md:left-10 md:top-10"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6 }}
      >
        TruthShield
      </motion.p>

      <div className="absolute inset-0 flex items-center justify-center">
        <AnimatePresence mode="wait">
          <motion.span
            key={WORDS[word]}
            className="font-display text-4xl italic text-text-primary/80 md:text-6xl lg:text-7xl"
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -20, opacity: 0 }}
            transition={{ duration: 0.35 }}
          >
            {WORDS[word]}
          </motion.span>
        </AnimatePresence>
      </div>

      <div className="absolute bottom-10 right-6 font-display text-6xl tabular-nums text-text-primary md:right-10 md:text-8xl lg:text-9xl">
        {String(count).padStart(3, '0')}
      </div>

      <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-stroke/50">
        <div
          className="accent-gradient h-full origin-left"
          style={{ transform: `scaleX(${count / 100})`, boxShadow: '0 0 8px rgba(137, 170, 204, 0.35)' }}
        />
      </div>
    </motion.div>
  );
}
