/**
 * Smooth in-page navigation.
 *
 * GSAP's ScrollToPlugin rather than CSS `scroll-behavior: smooth`, which
 * fights ScrollTrigger's own scroll restoration during refresh.
 */
import gsap from 'gsap';
import { ScrollToPlugin } from 'gsap/ScrollToPlugin';

gsap.registerPlugin(ScrollToPlugin);

const reduced = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export function scrollToSection(target: string | number, offset = 80) {
  if (typeof target === 'string' && !document.querySelector(target)) return;
  if (reduced()) {
    if (typeof target === 'number') window.scrollTo(0, target);
    else document.querySelector(target)?.scrollIntoView();
    return;
  }
  gsap.to(window, {
    duration: 1.1,
    ease: 'power3.inOut',
    scrollTo: typeof target === 'number' ? { y: target } : { y: target, offsetY: offset },
  });
}

export const HLS_SOURCE = 'https://stream.mux.com/Aa02T7oM1wH5Mk5EEVDYhbZ1ChcdhRsS2m1NYyx4Ua1g.m3u8';
