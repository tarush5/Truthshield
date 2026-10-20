/**
 * Smooth in-page navigation, native: no animation library on the landing
 * page's critical path. Reduced-motion visitors jump straight there.
 */
const reduced = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export function scrollToSection(target: string | number, offset = 88) {
  let top: number;
  if (typeof target === 'number') {
    top = target;
  } else {
    const el = document.querySelector(target);
    if (!el) return;
    top = el.getBoundingClientRect().top + window.scrollY - offset;
  }
  window.scrollTo({ top, behavior: reduced() ? 'auto' : 'smooth' });
}
