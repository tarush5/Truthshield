import React, { useEffect, useRef } from 'react';

/**
 * Cursor trail + click bursts.
 *
 * Perf notes — the previous version had three costs that dominated the frame:
 *   1. A point was pushed per mousemove event but aged once per frame. A
 *      1000 Hz mouse against a 60 Hz loop meant ~16 new points per frame with a
 *      38-frame lifetime, so the live set sat in the hundreds.
 *   2. Every particle set ctx.shadowBlur, which forces a per-draw blur pass.
 *   3. The canvas carried mixBlendMode:'screen' at z-9999, which promotes the
 *      whole viewport to a blended compositing layer re-blended each frame.
 *
 * This version emits by distance travelled, ages by elapsed time, caps the pool,
 * and replaces shadowBlur with a glow sprite rendered once per colour.
 */

const MAX_POINTS = 80;
const MAX_BURSTS = 140;
const POINT_LIFETIME_MS = 620;
const EMIT_MIN_DIST = 4;
const TRAIL_COLORS = ['#7dd3fc', '#22d3ee'];
const BURST_COLORS = ['#22d3ee', '#a78bfa', '#38bdf8'];

/** Pre-render a soft radial glow once per colour so draws become drawImage. */
function makeGlowSprite(color, radius) {
  const size = radius * 2;
  const c = document.createElement('canvas');
  c.width = size;
  c.height = size;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(radius, radius, 0, radius, radius, radius);
  grad.addColorStop(0, color);
  grad.addColorStop(0.35, color);
  grad.addColorStop(1, 'rgba(0,0,0,0)');
  g.globalAlpha = 1;
  g.fillStyle = grad;
  g.beginPath();
  g.arc(radius, radius, radius, 0, Math.PI * 2);
  g.fill();
  return c;
}

/** Pre-render a 4-point star once per colour. */
function makeStarSprite(color, radius) {
  const size = radius * 2;
  const c = document.createElement('canvas');
  c.width = size;
  c.height = size;
  const g = c.getContext('2d');
  const outer = radius * 0.92;
  const inner = radius * 0.18;

  const grad = g.createRadialGradient(radius, radius, 0, radius, radius, outer);
  grad.addColorStop(0, color);
  grad.addColorStop(0.5, color);
  grad.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = grad;

  let rot = (Math.PI / 2) * 3;
  const step = Math.PI / 4;
  g.beginPath();
  g.moveTo(radius, radius - outer);
  for (let i = 0; i < 4; i++) {
    g.lineTo(radius + Math.cos(rot) * outer, radius + Math.sin(rot) * outer);
    rot += step;
    g.lineTo(radius + Math.cos(rot) * inner, radius + Math.sin(rot) * inner);
    rot += step;
  }
  g.closePath();
  g.fill();
  return c;
}

export default function CursorTrail() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Respect the OS "reduce motion" setting — skip the effect entirely.
    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (motionQuery.matches) return;

    // Coarse pointers (touch) never produce a hover trail; skip the whole loop.
    if (window.matchMedia('(pointer: coarse)').matches) return;

    const ctx = canvas.getContext('2d', { alpha: true });
    let animId = null;
    let running = true;

    const SPRITE_R = 32;
    const glow = {};
    const stars = {};
    for (const c of new Set([...TRAIL_COLORS, ...BURST_COLORS])) {
      glow[c] = makeGlowSprite(c, SPRITE_R);
      stars[c] = makeStarSprite(c, SPRITE_R);
    }

    // Fixed-size pools. Nothing is allocated per frame, so the GC stays quiet.
    const points = [];
    const bursts = [];

    let width = window.innerWidth;
    let height = window.innerHeight;
    let dpr = Math.min(window.devicePixelRatio || 1, 2); // clamp: 3x costs 9x fill

    const resize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      // Setting .width resets the transform, so this scale is not cumulative.
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();

    let lastX = null;
    let lastY = null;
    let pendingX = null;
    let pendingY = null;

    // Only record the latest position here; emission happens in the frame loop
    // so a high-polling mouse cannot outrun the renderer.
    const handleMouseMove = (e) => {
      pendingX = e.clientX;
      pendingY = e.clientY;
    };

    const emitTrail = (now) => {
      if (pendingX === null) return;
      const x = pendingX;
      const y = pendingY;
      if (lastX !== null) {
        const dx = x - lastX;
        const dy = y - lastY;
        if (dx * dx + dy * dy < EMIT_MIN_DIST * EMIT_MIN_DIST) return;
      }
      lastX = x;
      lastY = y;

      if (points.length >= MAX_POINTS) points.shift();
      points.push({
        x,
        y,
        born: now,
        size: Math.random() * 3.8 + 2.2,
        color: Math.random() > 0.4 ? TRAIL_COLORS[0] : TRAIL_COLORS[1],
        angle: Math.random() * Math.PI,
        spin: (Math.random() - 0.5) * 0.05,
        star: Math.random() > 0.78,
      });
    };

    const handleMouseDown = (e) => {
      const room = MAX_BURSTS - bursts.length;
      const count = Math.min(28, room);
      for (let i = 0; i < count; i++) {
        const angle = Math.random() * Math.PI * 2;
        const speed = Math.random() * 6.5 + 2.5;
        const electric = Math.random() > 0.45;
        // Jag offsets are frozen at spawn. Re-rolling them every frame is what
        // made the arcs strobe rather than travel.
        const jag = electric
          ? [
              (Math.random() - 0.5) * 16, (Math.random() - 0.5) * 16,
              (Math.random() - 0.5) * 16, (Math.random() - 0.5) * 16,
              (Math.random() - 0.5) * 16, (Math.random() - 0.5) * 16,
            ]
          : null;
        bursts.push({
          x: e.clientX,
          y: e.clientY,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          size: Math.random() * 4.5 + 1.2,
          opacity: 1,
          decay: 0.018 + Math.random() * 0.025,
          color: BURST_COLORS[(Math.random() * BURST_COLORS.length) | 0],
          electric,
          jag,
        });
      }
    };

    // Drop everything and stop the loop while the tab is hidden.
    const handleVisibility = () => {
      if (document.hidden) {
        running = false;
        if (animId !== null) cancelAnimationFrame(animId);
        animId = null;
      } else if (!running) {
        running = true;
        points.length = 0;
        bursts.length = 0;
        lastFrame = performance.now();
        animId = requestAnimationFrame(draw);
      }
    };

    let lastFrame = performance.now();

    const draw = (now) => {
      // Normalise motion to 60 fps so a 144 Hz display does not fast-forward
      // the burst physics, and clamp so a long stall cannot teleport particles.
      const dt = Math.min((now - lastFrame) / 16.667, 3);
      lastFrame = now;

      ctx.clearRect(0, 0, width, height);
      emitTrail(now);

      ctx.globalCompositeOperation = 'lighter';

      // ── Trail ──
      for (let i = points.length - 1; i >= 0; i--) {
        const p = points[i];
        const ratio = 1 - (now - p.born) / POINT_LIFETIME_MS;
        if (ratio <= 0) {
          points.splice(i, 1);
          continue;
        }
        p.angle += p.spin * dt;
        const size = p.size * ratio;

        if (p.star) {
          const r = size * 2.8;
          ctx.globalAlpha = ratio * 0.78;
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate(p.angle);
          ctx.drawImage(stars[p.color], -r, -r, r * 2, r * 2);
          ctx.restore();
        } else {
          const r = size * 2.2;
          ctx.globalAlpha = ratio * 0.7;
          ctx.drawImage(glow[p.color], p.x - r, p.y - r, r * 2, r * 2);
        }
      }

      // ── Ribbon linking consecutive trail points ──
      ctx.globalAlpha = 1;
      for (let i = 1; i < points.length; i++) {
        const p = points[i];
        const prev = points[i - 1];
        const ratio = 1 - (now - p.born) / POINT_LIFETIME_MS;
        if (ratio <= 0) continue;
        const dx = p.x - prev.x;
        const dy = p.y - prev.y;
        if (dx * dx + dy * dy > 45 * 45) continue;
        ctx.strokeStyle = p.color;
        ctx.lineWidth = p.size * ratio * 0.5;
        ctx.globalAlpha = ratio * 0.25;
        ctx.beginPath();
        ctx.moveTo(prev.x, prev.y);
        ctx.lineTo(p.x, p.y);
        ctx.stroke();
      }

      // ── Click bursts ──
      for (let i = bursts.length - 1; i >= 0; i--) {
        const b = bursts[i];
        b.x += b.vx * dt;
        b.y += b.vy * dt;
        b.vy += 0.05 * dt; // gravity
        b.opacity -= b.decay * dt;

        if (b.opacity <= 0) {
          bursts.splice(i, 1);
          continue;
        }

        if (b.electric) {
          ctx.globalAlpha = b.opacity;
          ctx.strokeStyle = '#e0f2fe';
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.moveTo(b.x, b.y);
          let lx = b.x;
          let ly = b.y;
          for (let s = 0; s < 3; s++) {
            lx += b.jag[s * 2] + b.vx * 0.5;
            ly += b.jag[s * 2 + 1] + b.vy * 0.5;
            ctx.lineTo(lx, ly);
          }
          ctx.stroke();
        } else {
          const r = b.size * 2.2;
          ctx.globalAlpha = b.opacity;
          ctx.drawImage(stars[b.color], b.x - r, b.y - r, r * 2, r * 2);
        }
      }

      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = 'source-over';

      animId = requestAnimationFrame(draw);
    };

    const handleMotionChange = (e) => {
      if (e.matches) {
        running = false;
        if (animId !== null) cancelAnimationFrame(animId);
        animId = null;
        ctx.clearRect(0, 0, width, height);
      }
    };

    window.addEventListener('resize', resize);
    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    window.addEventListener('mousedown', handleMouseDown, { passive: true });
    document.addEventListener('visibilitychange', handleVisibility);
    motionQuery.addEventListener('change', handleMotionChange);

    animId = requestAnimationFrame(draw);

    return () => {
      if (animId !== null) cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('visibilitychange', handleVisibility);
      motionQuery.removeEventListener('change', handleMotionChange);
    };
  }, []);

  // No mixBlendMode: a full-viewport blended layer at z-9999 forced the entire
  // page to be re-composited every frame. 'lighter' inside the canvas gives the
  // same additive glow for free.
  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-[9999]"
      aria-hidden="true"
    />
  );
}
