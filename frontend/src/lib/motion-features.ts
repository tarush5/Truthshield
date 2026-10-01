// Loaded after first paint by <LazyMotion> in main.tsx: the animation and
// gesture engine stays off the critical path. Layout animations and drag
// (domMax) are not used anywhere, so they are not shipped at all.
export { domAnimation as default } from 'motion/react';
