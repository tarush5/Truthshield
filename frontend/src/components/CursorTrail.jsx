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
      // Create trail points with star sparkle and electric spark types
      points.push({
        x: e.clientX,
        y: e.clientY,
        age: 0,
        maxAge: 38,
        size: Math.random() * 3.8 + 2.2,
        color: Math.random() > 0.4 ? '#7dd3fc' : '#22d3ee', // Ice blue or Cyan
        angle: Math.random() * Math.PI,
        spin: (Math.random() - 0.5) * 0.05,
        type: Math.random() > 0.78 ? 'star' : 'sparkle'
      });
    };

    const handleMouseDown = (e) => {
      // Create a particle burst on click containing sparkles and electric sparks
      for (let i = 0; i < 35; i++) {
        const angle = Math.random() * Math.PI * 2;
        const speed = Math.random() * 6.5 + 2.5;
        const isElectric = Math.random() > 0.45;
        
        bursts.push({
          x: e.clientX,
          y: e.clientY,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          size: Math.random() * 4.5 + 1.2,
          opacity: 1,
          decay: 0.018 + Math.random() * 0.025,
          color: Math.random() > 0.5 ? '#22d3ee' : (Math.random() > 0.5 ? '#a78bfa' : '#38bdf8'), // Cyan, Purple, Sky Blue
          type: isElectric ? 'electric' : 'star',
          points: [] // path points for electric arcs
        });
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mousedown', handleMouseDown);

    // Twinkling Star drawing helper
    const drawStar = (cx, cy, spikes, outerRadius, innerRadius, color, alpha, rotationAngle = 0) => {
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      ctx.shadowBlur = 14;
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
        
        const ratio = 1 - p.age / p.maxAge;
        const currentSize = p.size * ratio;
        
        if (p.type === 'star') {
          drawStar(p.x, p.y, 4, currentSize * 2.8, currentSize * 0.5, p.color, ratio * 0.78, p.angle);
        } else {
          // Standard sparkling glow dot
          ctx.beginPath();
          ctx.arc(p.x, p.y, currentSize * 0.8, 0, Math.PI * 2);
          ctx.fillStyle = p.color;
          ctx.globalAlpha = ratio * 0.7;
          ctx.shadowBlur = 12;
          ctx.shadowColor = p.color;
          ctx.fill();
        }

        // Ribbon tail linking trail elements
        if (i > 0) {
          const prev = points[i - 1];
          const dist = Math.hypot(p.x - prev.x, p.y - prev.y);
          if (dist < 45) {
            ctx.beginPath();
            ctx.strokeStyle = p.color;
            ctx.lineWidth = currentSize * 0.5;
            ctx.globalAlpha = ratio * 0.25;
            ctx.shadowBlur = 10;
            ctx.shadowColor = p.color;
            ctx.moveTo(prev.x, prev.y);
            ctx.lineTo(p.x, p.y);
            ctx.stroke();
          }
        }
      }

      // 2. Draw click particle bursts
      for (let i = bursts.length - 1; i >= 0; i--) {
        const b = bursts[i];
        b.x += b.vx;
        b.y += b.vy;
        b.vy += 0.05; // gravity
        b.opacity -= b.decay;

        if (b.opacity <= 0) {
          bursts.splice(i, 1);
          continue;
        }

        if (b.type === 'electric') {
          // Render jagged electric discharge arc
          ctx.save();
          ctx.shadowBlur = 15;
          ctx.shadowColor = b.color;
          ctx.strokeStyle = '#e0f2fe';
          ctx.lineWidth = Math.random() * 1.5 + 0.5;
          ctx.globalAlpha = b.opacity;

          ctx.beginPath();
          ctx.moveTo(b.x, b.y);
          
          // Draw a small 3-segment lightning arc
          let lastX = b.x;
          let lastY = b.y;
          for (let s = 0; s < 3; s++) {
            const nextX = lastX + (Math.random() - 0.5) * 16 + b.vx * 0.5;
            const nextY = lastY + (Math.random() - 0.5) * 16 + b.vy * 0.5;
            ctx.lineTo(nextX, nextY);
            lastX = nextX;
            lastY = nextY;
          }
          ctx.stroke();
          ctx.restore();
        } else {
          // Render twinkling star burst particle
          drawStar(b.x, b.y, 4, b.size * 2.2, b.size * 0.45, b.color, b.opacity, b.x * 0.015);
        }
      }

      ctx.restore();

      // Filter out aged points
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
