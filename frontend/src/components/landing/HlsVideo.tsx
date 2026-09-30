import { useEffect, useRef } from 'react';

import { cn } from '@/lib/format';
import { HLS_SOURCE } from '@/lib/scroll';

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

/**
 * Background HLS video. hls.js is imported lazily so it never sits on the
 * initial bundle; Safari plays HLS natively and skips it entirely.
 */
export function HlsVideo({ className, flip = false }: { className?: string; flip?: boolean }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    let destroyed = false;
    let hls: { destroy: () => void } | null = null;

    // hls.js first wherever Media Source Extensions exist; native HLS only as
    // the fallback. Some Chromium builds answer "maybe" to canPlayType for
    // HLS and then play nothing, so the native answer cannot be trusted first.
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
      })
      .catch(() => undefined);

    // Pause when off-screen: two full-bleed videos decoding at once is a
    // noticeable battery cost on a laptop for no visible benefit.
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) video.play().catch(() => undefined);
      else video.pause();
    });
    observer.observe(video);

    return () => {
      destroyed = true;
      observer.disconnect();
      hls?.destroy();
    };
  }, []);

  return (
    <video
      ref={ref}
      autoPlay
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
