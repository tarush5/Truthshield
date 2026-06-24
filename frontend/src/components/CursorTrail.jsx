import React, { useEffect, useRef } from 'react';

export default function CursorTrail() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;
    let points = [];
    let bursts = [];

    const resize = () => {
      canvas.width = window.innerWidth * window.devicePixelRatio;
      canvas.height = window.innerHeight * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };
    resize();
    window.addEventListener('resize', resize);

    const handleMouseMove = (e) => {
      // Create fire particles (sparkles and embers)
      points.push({
        x: e.clientX,
        y: e.clientY,
        vy: -Math.random() * 0.4 - 0.1, // float upward slightly
        vx: (Math.random() - 0.5) * 0.3,
        age: 0,
        maxAge: 40,
        size: Math.random() * 3.5 + 1.8,
        color: Math.random() > 0.6 
          ? '#FFD600' // Gold/yellow
          : Math.random() > 0.4 
          ? '#FF9100' // Orange
          : '#FF1744', // Neon red
        angle: Math.random() * Math.PI,
        spin: (Math.random() - 0.5) * 0.08,
        type: Math.random() > 0.8 ? 'flame' : 'spark'
      });
    };

    const handleMouseDown = (e) => {
      // Create a big fiery particle burst on click (flame sparks and red electric arcs)
      for (let i = 0; i < 40; i++) {
        const angle = Math.random() * Math.PI * 2;
        const speed = Math.random() * 7 + 2;
        const isElectric = Math.random() > 0.6;
        
        bursts.push({
          x: e.clientX,
          y: e.clientY,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed - 1.5, // slightly upward blast bias
          size: Math.random() * 4 + 1,
          opacity: 1,
          decay: 0.015 + Math.random() * 0.02,
          color: Math.random() > 0.5 
            ? '#FF3D00' // Red-orange
            : Math.random() > 0.5 
            ? '#FFD600' // Gold
            : '#FF1744', // Neon red
          type: isElectric ? 'electric' : 'ember'
        });
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mousedown', handleMouseDown);

    // Fire Star / Twinkle drawing helper
    const drawSpark = (cx, cy, spikes, outerRadius, innerRadius, color, alpha, rotationAngle = 0) => {
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      ctx.shadowBlur = 10;
      ctx.shadowColor = color;
      ctx.fillStyle = color;
      ctx.globalAlpha = alpha;

      let rot = (Math.PI / 2) * 3 + rotationAngle;
      let x = cx;
      let y = cy;
      const step = Math.PI / spikes;

      ctx.beginPath();
      ctx.moveTo(cx, cy - outerRadius);
      for (let i = 0; i < spikes; i++) {
        x = cx + Math.cos(rot) * outerRadius;
        y = cy + Math.sin(rot) * outerRadius;
        ctx.lineTo(x, y);
        rot += step;

        x = cx + Math.cos(rot) * innerRadius;
        y = cy + Math.sin(rot) * innerRadius;
        ctx.lineTo(x, y);
        rot += step;
      }
      ctx.lineTo(cx, cy - outerRadius);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    };

    const draw = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      ctx.clearRect(0, 0, w, h);

      ctx.save();
      ctx.globalCompositeOperation = 'screen';

      // 1. Draw cursor trails
      for (let i = 0; i < points.length; i++) {
        const p = points[i];
        p.age++;
        p.angle += p.spin;
        p.y += p.vy;
        p.x += p.vx;
        
        const ratio = 1 - p.age / p.maxAge;
        const currentSize = p.size * ratio;
        
        if (p.type === 'flame') {
          // Glow ember particle
          ctx.beginPath();
          ctx.arc(p.x, p.y, currentSize * 1.5, 0, Math.PI * 2);
          const emberGlow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 2 * ratio);
          emberGlow.addColorStop(0, p.color);
          emberGlow.addColorStop(0.5, '#FF3D00');
          emberGlow.addColorStop(1, 'transparent');
          ctx.fillStyle = emberGlow;
          ctx.globalAlpha = ratio * 0.8;
          ctx.fill();
        } else {
          // Sharp sparkle star
          drawSpark(p.x, p.y, 4, currentSize * 2.5, currentSize * 0.45, p.color, ratio * 0.75, p.angle);
        }

        // Connecting fire tail
        if (i > 0) {
          const prev = points[i - 1];
          const dist = Math.hypot(p.x - prev.x, p.y - prev.y);
          if (dist < 40) {
            ctx.beginPath();
            ctx.strokeStyle = p.color;
            ctx.lineWidth = currentSize * 0.4;
            ctx.globalAlpha = ratio * 0.2;
            ctx.shadowBlur = 8;
            ctx.shadowColor = p.color;
            ctx.moveTo(prev.x, prev.y);
            ctx.lineTo(p.x, p.y);
            ctx.stroke();
          }
        }
      }

      // 2. Draw click bursts
      for (let i = bursts.length - 1; i >= 0; i--) {
        const b = bursts[i];
        b.x += b.vx;
        b.y += b.vy;
        b.vy += 0.08; // gravity drop
        b.vx *= 0.98;
        b.opacity -= b.decay;

        if (b.opacity <= 0) {
          bursts.splice(i, 1);
          continue;
        }

        if (b.type === 'electric') {
          // Red lightning/electric heat arc
          ctx.save();
          ctx.shadowBlur = 12;
          ctx.shadowColor = b.color;
          ctx.strokeStyle = '#FFE082'; // bright hot core
          ctx.lineWidth = Math.random() * 1.2 + 0.4;
          ctx.globalAlpha = b.opacity;

          ctx.beginPath();
          ctx.moveTo(b.x, b.y);
          
          let lastX = b.x;
          let lastY = b.y;
          for (let s = 0; s < 3; s++) {
            const nextX = lastX + (Math.random() - 0.5) * 12 + b.vx * 0.4;
            const nextY = lastY + (Math.random() - 0.5) * 12 + b.vy * 0.4;
            ctx.lineTo(nextX, nextY);
            lastX = nextX;
            lastY = nextY;
          }
          ctx.stroke();
          ctx.restore();
        } else {
          // Small glowing fire ash particle
          ctx.beginPath();
          ctx.arc(b.x, b.y, b.size * b.opacity, 0, Math.PI * 2);
          ctx.fillStyle = b.color;
          ctx.globalAlpha = b.opacity * 0.8;
          ctx.shadowBlur = 6;
          ctx.shadowColor = b.color;
          ctx.fill();
        }
      }

      ctx.restore();

      // Filter out dead points
      points = points.filter((p) => p.age < p.maxAge);

      animId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mousedown', handleMouseDown);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-[9999] overflow-hidden"
      style={{ mixBlendMode: 'screen' }}
    />
  );
}
