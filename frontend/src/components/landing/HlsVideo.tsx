import { useEffect, useRef } from 'react';

import { cn } from '@/lib/format';

export function Backdrop() {
  // Shown under the video: while it buffers, when it cannot play, and for
  // reduced-motion visitors, who get a still image of the same mood instead.
  return (
    <div aria-hidden className="absolute inset-0">
      <div className="absolute left-1/2 top-1/3 h-[60vh] w-[80vw] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#4E85BF]/20 blur-[140px]" />
      <div className="absolute bottom-0 right-0 h-[40vh] w-[50vw] rounded-full bg-[#89AACC]/10 blur-[120px]" />
      <div className="halftone absolute inset-0 opacity-[0.15]" />
    </div>
  );
}

export const HLS_SOURCE = 'https://stream.mux.com/Aa02T7oM1wH5Mk5EEVDYhbZ1ChcdhRsS2m1NYyx4Ua1g.m3u8';

/**
 * Background HLS video. Nothing is fetched until the video is within a
 * screen of the viewport: hls.js (~114 kB gzipped) and the stream are
 * loaded on approach, so a visitor who never scrolls to the footer never
 * pays for its video.
 */
export function HlsVideo({ className, flip = false }: { className?: string; flip?: boolean }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    let destroyed = false;
    let started = false;
    let visible = false;
    let hls: { destroy: () => void } | null = null;

    const sync = () => {
      if (visible && !document.hidden) video.play().catch(() => undefined);
      else video.pause();
    };

    const start = () => {
      started = true;
      // hls.js first wherever Media Source Extensions exist; native HLS only
      // as the fallback. Some Chromium builds answer "maybe" to canPlayType
      // for HLS and then play nothing, so the native answer cannot be
      // trusted first.
      import('hls.js/light')
        .then(({ default: Hls }) => {
          if (destroyed) return;
          if (Hls.isSupported()) {
            const instance = new Hls({ capLevelToPlayerSize: true, maxBufferLength: 10 });
            instance.loadSource(HLS_SOURCE);
            instance.attachMedia(video);
            hls = instance;
          } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            video.src = HLS_SOURCE;
          }
          // Some browsers reject play() before the first segment arrives.
          video.addEventListener('canplay', sync, { once: true });
          sync();
        })
        .catch(() => undefined);
    };

    // Start on approach; afterwards, pause whenever off-screen or the tab is
    // hidden. Two full-bleed videos decoding at once is a noticeable battery
    // cost for no visible benefit.
    const near = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started) start();
      },
      { rootMargin: '100% 0px' },
    );
    const onScreen = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (started) sync();
    });
    near.observe(video);
    onScreen.observe(video);
    document.addEventListener('visibilitychange', sync);

    return () => {
      destroyed = true;
      near.disconnect();
      onScreen.disconnect();
      document.removeEventListener('visibilitychange', sync);
      video.removeEventListener('canplay', sync);
      hls?.destroy();
    };
  }, []);

  return (
    <video
      ref={ref}
      preload="none"
      muted
      loop
      playsInline
      aria-hidden
      className={cn(
        'absolute left-1/2 top-1/2 min-h-full min-w-full -translate-x-1/2 -translate-y-1/2 object-cover',
        flip && 'scale-y-[-1]',
        className,
      )}
    />
  );
}
