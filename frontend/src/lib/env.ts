/**
 * Dev-only switch for automated browsers.
 *
 * Headless and background browser panes often report the document as hidden,
 * where requestAnimationFrame never fires: Motion's exit animations (and the
 * route transitions that wait on them) never complete, and the page appears
 * frozen. `localStorage.setItem('ts.skipMotion', '1')` turns transitions and
 * the intro off entirely. Never active in production builds.
 */
export const SKIP_MOTION: boolean = (() => {
  if (!import.meta.env.DEV) return false;
  try {
    return localStorage.getItem('ts.skipMotion') === '1';
  } catch {
    return false;
  }
})();
