import React, { useEffect, useRef } from 'react';

/**
 * Layered ambient background: static wash, aurora waves, neural nodes,
 * lightning, and drifting snow.
 *
 * Fixes over the previous version:
 *   - the 'mousedown' listener was added but never removed, so handlers
 *     accumulated across remounts and every click re-ran the node sort once
 *     per leaked handler;
 *   - snow pushed away from the cursor divided by a distance that can be 0,
 *     producing NaN coordinates that removed the flake permanently (the
 *     background slowly lost its snow);
 *   - nodes at a boundary flipped velocity while still out of bounds, so they
 *     stuck to the edge and vibrated;
 *   - the base wash, its radial gradient, and all five aurora gradients were
 *     re-allocated every frame; the wash is now cached to an offscreen canvas
 *     and gradients are rebuilt only on resize or theme change.
 */

const SNOW_COUNT = 65;
const NODE_COUNT = 45;
const CONNECTION_DIST = 150;
const CONNECTION_DIST_SQ = CONNECTION_DIST * CONNECTION_DIST;

export default function ArcticIntelligenceBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d', { alpha: false });
    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

    let animId = null;
    let width = window.innerWidth;
    let height = window.innerHeight;
    let dpr = Math.min(window.devicePixelRatio || 1, 2);

    let snow = [];
    let nodes = [];
    let activeLightnings = [];
    let auroraTime = 0;

    // Theme is read once per frame, not once per lightning bolt — each read is
    // a DOM query inside the render loop.
    let isLight = document.documentElement.classList.contains('light');

    // Offscreen cache for the parts of the frame that never move.
    const bgCanvas = document.createElement('canvas');
    const bgCtx = bgCanvas.getContext('2d', { alpha: false });
    let auroraGradients = null;

    const mouse = { x: null, y: null, radius: 200, speed: 0 };

    const buildStaticLayer = () => {
      bgCanvas.width = Math.max(1, Math.floor(width * dpr));
      bgCanvas.height = Math.max(1, Math.floor(height * dpr));
      bgCtx.setTransform(dpr, 0, 0, dpr, 0, 0);

      bgCtx.fillStyle = isLight ? '#f1f5f9' : '#020617';
      bgCtx.fillRect(0, 0, width, height);

      const centerGlow = bgCtx.createRadialGradient(
        width / 2, height / 3, 10,
        width / 2, height / 2, Math.max(width, height)
      );
      if (isLight) {
        centerGlow.addColorStop(0, 'rgba(186, 230, 253, 0.25)');
        centerGlow.addColorStop(0.5, 'rgba(226, 232, 240, 0.4)');
        centerGlow.addColorStop(1, '#f1f5f9');
      } else {
        centerGlow.addColorStop(0, '#071124');
        centerGlow.addColorStop(0.5, '#040b1a');
        centerGlow.addColorStop(1, '#020617');
      }
      bgCtx.fillStyle = centerGlow;
      bgCtx.fillRect(0, 0, width, height);
    };

    // Aurora geometry animates but its fill does not, so build each gradient
    // once and reuse it across frames.
    const buildAuroraGradients = () => {
      const make = (offsetY, amp, waveCount, color1, color2, alpha) => {
        const layers = [];
        for (let w = 0; w < waveCount; w++) {
          const g = ctx.createLinearGradient(0, offsetY - amp, 0, height);
          g.addColorStop(0, `${color1}, ${alpha * (1 - w * 0.2)})`);
          g.addColorStop(0.5, `${color2}, ${alpha * 0.4 * (1 - w * 0.2)})`);
          g.addColorStop(1, isLight ? 'rgba(241, 245, 249, 0)' : 'rgba(2, 6, 23, 0)');
          layers.push(g);
        }
        return { offsetY, amp, waveCount, layers };
      };

      auroraGradients = [
        make(
          height * 0.65, 80, 3,
          isLight ? 'rgba(8, 145, 178' : 'rgba(34, 211, 238',
          isLight ? 'rgba(2, 132, 199' : 'rgba(14, 165, 233',
          isLight ? 0.03 : 0.07
        ),
        make(
          height * 0.45, 60, 2,
          isLight ? 'rgba(109, 40, 217' : 'rgba(139, 92, 246',
          isLight ? 'rgba(8, 145, 178' : 'rgba(34, 211, 238',
          isLight ? 0.025 : 0.05
        ),
      ];
    };

    const resize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.floor(width * dpr));
      canvas.height = Math.max(1, Math.floor(height * dpr));
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      buildStaticLayer();
      buildAuroraGradients();
    };

    const handleMouseMove = (e) => {
      if (mouse.x !== null) {
        mouse.speed = Math.hypot(e.clientX - mouse.x, e.clientY - mouse.y);
        if (mouse.speed > 35 && Math.random() < 0.18 && nodes.length > 1) {
          spawnLightningNear(e.clientX, e.clientY, 200, 1);
        }
      }
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };

    const handleMouseLeave = () => {
      mouse.x = null;
      mouse.y = null;
      mouse.speed = 0;
    };

    const handleMouseDown = (e) => {
      spawnLightningNear(e.clientX, e.clientY, 260, 3);
    };

    // Picks the nearest nodes without the map/filter/sort allocation the old
    // path did on every mousemove.
    const spawnLightningNear = (x, y, range, strikes) => {
      if (nodes.length < 2) return;
      const rangeSq = range * range;
      const near = [];
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        const d = (n.x - x) * (n.x - x) + (n.y - y) * (n.y - y);
        if (d < rangeSq) near.push({ n, d });
      }
      if (near.length < 2) return;
      near.sort((a, b) => a.d - b.d);

      const count = Math.min(strikes, Math.floor(near.length / 2));
      for (let i = 0; i < count; i++) {
        activeLightnings.push({
          nodeA: near[i * 2].n,
          nodeB: near[i * 2 + 1].n,
          life: Math.floor(Math.random() * 8 + 4),
          width: Math.random() * 1.5 + 0.8,
        });
      }
    };

    const initParticles = () => {
      snow = [];
      for (let i = 0; i < SNOW_COUNT; i++) {
        snow.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.2) * 0.5,
          vy: Math.random() * 0.7 + 0.3,
          size: Math.random() * 2 + 0.8,
          opacity: Math.random() * 0.6 + 0.2,
          parallax: Math.random() * 0.8 + 0.4,
        });
      }
      nodes = [];
      for (let i = 0; i < NODE_COUNT; i++) {
        nodes.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.25,
          vy: (Math.random() - 0.5) * 0.25,
          size: Math.random() * 1.5 + 0.8,
          pulseVal: Math.random() * Math.PI,
          pulseSpeed: 0.015 + Math.random() * 0.02,
        });
      }
    };

    const drawLightningSegment = (x1, y1, x2, y2, displace) => {
      if (displace < 1.8) {
        ctx.lineTo(x2, y2);
        return;
      }
      const dx = x2 - x1;
      const dy = y2 - y1;
      const len = Math.hypot(dx, dy) || 1; // guard: coincident nodes
      const offset = (Math.random() - 0.5) * displace;
      const cx = (x1 + x2) / 2 + (-dy / len) * offset;
      const cy = (y1 + y2) / 2 + (dx / len) * offset;
      drawLightningSegment(x1, y1, cx, cy, displace / 2);
      drawLightningSegment(cx, cy, x2, y2, displace / 2);
    };

    const renderLightningBolt = (bolt) => {
      const { nodeA, nodeB, width: w } = bolt;
      ctx.save();
      if (isLight) {
        ctx.globalCompositeOperation = 'source-over';
        ctx.shadowBlur = 8;
        ctx.shadowColor = '#0ea5e9';
        ctx.strokeStyle = '#0284c7';
      } else {
        ctx.globalCompositeOperation = 'screen';
        ctx.shadowBlur = 16;
        ctx.shadowColor = '#06b6d4';
        ctx.strokeStyle = '#e0f2fe';
      }
      ctx.lineWidth = w * (0.4 + Math.random() * 0.8);

      ctx.beginPath();
      ctx.moveTo(nodeA.x, nodeA.y);
      drawLightningSegment(nodeA.x, nodeA.y, nodeB.x, nodeB.y, 38);
      ctx.stroke();

      if (Math.random() < 0.3) {
        const branchAngle = (Math.random() - 0.5) * 0.7;
        const branchLen = 0.4 + Math.random() * 0.35;
        const dx = nodeB.x - nodeA.x;
        const dy = nodeB.y - nodeA.y;
        const bx = nodeA.x + dx * 0.5;
        const by = nodeA.y + dy * 0.5;
        const rx = (dx * Math.cos(branchAngle) - dy * Math.sin(branchAngle)) * branchLen;
        // was: dx * sin + dx * cos — the second term should use dy
        const ry = (dx * Math.sin(branchAngle) + dy * Math.cos(branchAngle)) * branchLen;
        ctx.beginPath();
        ctx.moveTo(bx, by);
        drawLightningSegment(bx, by, bx + rx, by + ry, 20);
        ctx.stroke();
      }
      ctx.restore();
    };

    let lastFrame = performance.now();

    const draw = (now) => {
      const dt = Math.min((now - lastFrame) / 16.667, 3);
      lastFrame = now;

      const themeNow = document.documentElement.classList.contains('light');
      if (themeNow !== isLight) {
        isLight = themeNow;
        buildStaticLayer();
        buildAuroraGradients();
      }

      // Static wash: one blit instead of a fill plus a full-screen radial.
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.drawImage(bgCanvas, 0, 0);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      // ── Aurora ──
      auroraTime += 0.002 * dt;
      ctx.save();
      ctx.globalCompositeOperation = isLight ? 'source-over' : 'screen';
      for (const wave of auroraGradients) {
        for (let w = 0; w < wave.waveCount; w++) {
          ctx.beginPath();
          ctx.moveTo(0, height);
          for (let x = 0; x <= width; x += 20) {
            const angle = (x / width) * Math.PI * 2 + auroraTime * 2 + w * 0.5;
            ctx.lineTo(
              x,
              wave.offsetY + Math.sin(angle) * wave.amp +
                Math.cos(angle * 0.5) * (wave.amp * 0.5)
            );
          }
          ctx.lineTo(width, height);
          ctx.closePath();
          ctx.fillStyle = wave.layers[w];
          ctx.fill();
        }
      }
      ctx.restore();

      // ── Cursor spotlight ──
      if (mouse.x !== null) {
        const mouseGlow = ctx.createRadialGradient(
          mouse.x, mouse.y, 0, mouse.x, mouse.y, mouse.radius
        );
        if (isLight) {
          mouseGlow.addColorStop(0, 'rgba(14, 165, 233, 0.06)');
          mouseGlow.addColorStop(0.5, 'rgba(109, 40, 217, 0.02)');
          mouseGlow.addColorStop(1, 'rgba(241, 245, 249, 0)');
        } else {
          mouseGlow.addColorStop(0, 'rgba(125, 211, 252, 0.08)');
          mouseGlow.addColorStop(0.5, 'rgba(139, 92, 246, 0.03)');
          mouseGlow.addColorStop(1, 'rgba(0, 0, 0, 0)');
        }
        ctx.save();
        ctx.globalCompositeOperation = isLight ? 'source-over' : 'screen';
        ctx.fillStyle = mouseGlow;
        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, mouse.radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }

      // ── Nodes ──
      const nodeHalo = isLight ? 'rgba(14, 165, 233, 0.15)' : 'rgba(125, 211, 252, 0.25)';
      const nodeCore = isLight ? '#0284c7' : '#7dd3fc';
      for (let i = 0; i < nodes.length; i++) {
        const p = nodes[i];
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.pulseVal += p.pulseSpeed * dt;

        // Clamp as well as reflect. Flipping velocity alone let a node that was
        // already past the edge flip every frame and buzz in place.
        if (p.x < 0) { p.x = 0; p.vx = Math.abs(p.vx); }
        else if (p.x > width) { p.x = width; p.vx = -Math.abs(p.vx); }
        if (p.y < 0) { p.y = 0; p.vy = Math.abs(p.vy); }
        else if (p.y > height) { p.y = height; p.vy = -Math.abs(p.vy); }

        const scale = 1 + Math.sin(p.pulseVal) * 0.25;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * scale, 0, Math.PI * 2);
        ctx.fillStyle = nodeHalo;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * 0.4, 0, Math.PI * 2);
        ctx.fillStyle = nodeCore;
        ctx.fill();
      }

      // ── Connections: one path per alpha bucket instead of one per pair ──
      ctx.lineWidth = 0.5;
      const rgb = isLight ? '14, 165, 233' : '125, 211, 252';
      const maxAlpha = isLight ? 0.05 : 0.06;
      const BUCKETS = 4;
      for (let b = 0; b < BUCKETS; b++) {
        let opened = false;
        const lo = (b / BUCKETS) * CONNECTION_DIST_SQ;
        const hi = ((b + 1) / BUCKETS) * CONNECTION_DIST_SQ;
        for (let i = 0; i < nodes.length; i++) {
          const p1 = nodes[i];
          for (let j = i + 1; j < nodes.length; j++) {
            const p2 = nodes[j];
            const dx = p1.x - p2.x;
            const dy = p1.y - p2.y;
            const dsq = dx * dx + dy * dy;
            if (dsq < lo || dsq >= hi) continue;
            if (!opened) { ctx.beginPath(); opened = true; }
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
          }
        }
        if (opened) {
          const alpha = maxAlpha * (1 - (b + 0.5) / BUCKETS);
          ctx.strokeStyle = `rgba(${rgb}, ${alpha})`;
          ctx.stroke();
        }
      }

      // ── Ambient lightning ──
      if (Math.random() < 0.0075 * dt && nodes.length > 1) {
        const a = nodes[(Math.random() * nodes.length) | 0];
        spawnLightningNear(a.x, a.y, 220, 1);
      }
      for (let i = activeLightnings.length - 1; i >= 0; i--) {
        const bolt = activeLightnings[i];
        renderLightningBolt(bolt);
        bolt.life -= dt;
        if (bolt.life <= 0) activeLightnings.splice(i, 1);
      }

      // ── Snow ──
      const snowRGB = isLight ? '148, 163, 184' : '248, 250, 252';
      const snowMul = isLight ? 0.35 : 1;
      for (let i = 0; i < snow.length; i++) {
        const f = snow[i];
        f.x += f.vx * f.parallax * dt;
        f.y += f.vy * f.parallax * dt;

        if (f.y > height) { f.y = -10; f.x = Math.random() * width; }
        if (f.x > width) f.x = 0;
        else if (f.x < 0) f.x = width;

        if (mouse.x !== null) {
          const dx = f.x - mouse.x;
          const dy = f.y - mouse.y;
          const dsq = dx * dx + dy * dy;
          // Guard the zero case: dividing by a zero distance produced NaN
          // coordinates, and a NaN flake fails every reset test forever.
          if (dsq < 10000 && dsq > 0.0001) {
            const dist = Math.sqrt(dsq);
            const force = (100 - dist) / 100;
            f.x += (dx / dist) * force * 3 * dt;
            f.y += (dy / dist) * force * 3 * dt;
          }
        }

        ctx.beginPath();
        ctx.arc(f.x, f.y, f.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${snowRGB}, ${f.opacity * snowMul})`;
        ctx.fill();
      }

      animId = requestAnimationFrame(draw);
    };

    // Static single frame for reduced-motion users: wash only, no loop.
    const renderStatic = () => {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.drawImage(bgCanvas, 0, 0);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const stop = () => {
      if (animId !== null) cancelAnimationFrame(animId);
      animId = null;
    };

    const start = () => {
      if (animId !== null || motionQuery.matches || document.hidden) return;
      lastFrame = performance.now();
      animId = requestAnimationFrame(draw);
    };

    const handleVisibility = () => {
      if (document.hidden) stop();
      else start();
    };

    const handleMotionChange = () => {
      if (motionQuery.matches) { stop(); renderStatic(); }
      else start();
    };

    resize();
    initParticles();

    const handleResize = () => { resize(); if (motionQuery.matches) renderStatic(); };

    window.addEventListener('resize', handleResize);
    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    window.addEventListener('mouseleave', handleMouseLeave);
    window.addEventListener('mousedown', handleMouseDown, { passive: true });
    document.addEventListener('visibilitychange', handleVisibility);
    motionQuery.addEventListener('change', handleMotionChange);

    if (motionQuery.matches) renderStatic();
    else start();

    return () => {
      stop();
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseleave', handleMouseLeave);
      window.removeEventListener('mousedown', handleMouseDown); // was leaking
      document.removeEventListener('visibilitychange', handleVisibility);
      motionQuery.removeEventListener('change', handleMotionChange);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      style={{ opacity: 0.8 }}
      aria-hidden="true"
    />
  );
}
