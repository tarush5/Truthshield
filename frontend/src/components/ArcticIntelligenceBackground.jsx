import React, { useEffect, useRef } from 'react';

export default function ArcticIntelligenceBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;
    let width = window.innerWidth;
    let height = window.innerHeight;

    // Wind and snow state
    let snow = [];
    const SNOW_COUNT = 65;
    
    // Neural network nodes
    let nodes = [];
    const NODE_COUNT = 45;
    const CONNECTION_DIST = 150;

    // Active lightning bolts
    let activeLightnings = [];

    // Aurora wave configurations
    let auroraTime = 0;

    const mouse = {
      x: null,
      y: null,
      radius: 200,
      lastX: null,
      lastY: null,
      speed: 0
    };

    const handleMouseMove = (e) => {
      if (mouse.x !== null && mouse.y !== null) {
        const dx = e.clientX - mouse.x;
        const dy = e.clientY - mouse.y;
        mouse.speed = Math.hypot(dx, dy);
        
        // Fast mouse moves trigger local lightning bolts between nearby nodes
        if (mouse.speed > 35 && Math.random() < 0.18 && nodes.length > 1) {
          const localNodes = nodes
            .map((n, idx) => ({ idx, dist: Math.hypot(n.x - e.clientX, n.y - e.clientY) }))
            .filter(n => n.dist < 200)
            .sort((a, b) => a.dist - b.dist);
          if (localNodes.length >= 2) {
            activeLightnings.push({
              nodeA: nodes[localNodes[0].idx],
              nodeB: nodes[localNodes[1].idx],
              life: Math.floor(Math.random() * 6 + 3),
              width: Math.random() * 1.5 + 0.8
            });
          }
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
      // Direct click triggers multiple local lightning strikes
      if (nodes.length > 1) {
        const localNodes = nodes
          .map((n, idx) => ({ idx, dist: Math.hypot(n.x - e.clientX, n.y - e.clientY) }))
          .filter(n => n.dist < 260)
          .sort((a, b) => a.dist - b.dist);
        
        const strikes = Math.min(3, Math.floor(localNodes.length / 2));
        for (let i = 0; i < strikes; i++) {
          activeLightnings.push({
            nodeA: nodes[localNodes[i * 2].idx],
            nodeB: nodes[localNodes[i * 2 + 1].idx],
            life: Math.floor(Math.random() * 10 + 5),
            width: Math.random() * 2.0 + 1.0
          });
        }
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseleave', handleMouseLeave);
    window.addEventListener('mousedown', handleMouseDown);

    const resize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width * window.devicePixelRatio;
      canvas.height = height * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };
    resize();
    window.addEventListener('resize', resize);

    // Initialize Snow particles
    for (let i = 0; i < SNOW_COUNT; i++) {
      snow.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.2) * 0.5, // gentle drift to the right
        vy: Math.random() * 0.7 + 0.3,
        size: Math.random() * 2 + 0.8,
        opacity: Math.random() * 0.6 + 0.2,
        parallax: Math.random() * 0.8 + 0.4
      });
    }

    // Initialize Neural network nodes
    for (let i = 0; i < NODE_COUNT; i++) {
      nodes.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.25,
        vy: (Math.random() - 0.5) * 0.25,
        size: Math.random() * 1.5 + 0.8,
        pulseVal: Math.random() * Math.PI,
        pulseSpeed: 0.015 + Math.random() * 0.02
      });
    }

    // Recursive fractal lightning drawer
    const drawLightningSegment = (x1, y1, x2, y2, displace) => {
      if (displace < 1.8) {
        ctx.lineTo(x2, y2);
      } else {
        const midX = (x1 + x2) / 2;
        const midY = (y1 + y2) / 2;
        const dx = x2 - x1;
        const dy = y2 - y1;
        const len = Math.hypot(dx, dy);
        const nx = -dy / len;
        const ny = dx / len;
        const offset = (Math.random() - 0.5) * displace;
        const cx = midX + nx * offset;
        const cy = midY + ny * offset;
        
        drawLightningSegment(x1, y1, cx, cy, displace / 2);
        drawLightningSegment(cx, cy, x2, y2, displace / 2);
      }
    };

    const renderLightningBolt = (bolt) => {
      const { nodeA, nodeB, width: w } = bolt;
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      
      // Blue/cyan electric glow
      ctx.shadowBlur = 16;
      ctx.shadowColor = '#06b6d4';
      ctx.strokeStyle = '#e0f2fe';
      ctx.lineWidth = w * (0.4 + Math.random() * 0.8);
      
      ctx.beginPath();
      ctx.moveTo(nodeA.x, nodeA.y);
      drawLightningSegment(nodeA.x, nodeA.y, nodeB.x, nodeB.y, 38);
      ctx.stroke();
      
      // Lightning branch
      if (Math.random() < 0.3) {
        const branchAngle = (Math.random() - 0.5) * 0.7;
        const branchLen = 0.4 + Math.random() * 0.35;
        const dx = nodeB.x - nodeA.x;
        const dy = nodeB.y - nodeA.y;
        
        const bx = nodeA.x + dx * 0.5;
        const by = nodeA.y + dy * 0.5;
        const rx = (dx * Math.cos(branchAngle) - dy * Math.sin(branchAngle)) * branchLen;
        const ry = (dx * Math.sin(branchAngle) + dx * Math.cos(branchAngle)) * branchLen;
        
        ctx.beginPath();
        ctx.moveTo(bx, by);
        drawLightningSegment(bx, by, bx + rx, by + ry, 20);
        ctx.stroke();
      }
      ctx.restore();
    };

    const draw = () => {
      // Clear with deep navy space background
      ctx.fillStyle = '#020617';
      ctx.fillRect(0, 0, width, height);

      // ── Layer 1: Atmospheric Gradients ──
      const centerGlow = ctx.createRadialGradient(
        width / 2, height / 3, 10,
        width / 2, height / 2, Math.max(width, height)
      );
      centerGlow.addColorStop(0, '#071124');
      centerGlow.addColorStop(0.5, '#040b1a');
      centerGlow.addColorStop(1, '#020617');
      ctx.fillStyle = centerGlow;
      ctx.fillRect(0, 0, width, height);

      // ── Layer 2: Moving Aurora Waves ──
      auroraTime += 0.002;
      
      const drawAuroraWave = (offsetY, amp, waveCount, color1, color2, alpha) => {
        ctx.save();
        ctx.globalCompositeOperation = 'screen';
        
        // Draw multiple paths layered to create depth
        for (let w = 0; w < waveCount; w++) {
          const shift = w * 40;
          ctx.beginPath();
          ctx.moveTo(0, height);
          
          for (let x = 0; x <= width; x += 20) {
            const angle = (x / width) * Math.PI * 2 + auroraTime * 2 + w * 0.5;
            const y = offsetY + Math.sin(angle) * amp + Math.cos(angle * 0.5) * (amp * 0.5);
            ctx.lineTo(x, y);
          }
          
          ctx.lineTo(width, height);
          ctx.closePath();
          
          const grad = ctx.createLinearGradient(0, offsetY - amp, 0, height);
          grad.addColorStop(0, `${color1}, ${alpha * (1 - w * 0.2)})`);
          grad.addColorStop(0.5, `${color2}, ${alpha * 0.4 * (1 - w * 0.2)})`);
          grad.addColorStop(1, 'rgba(2, 6, 23, 0)');
          
          ctx.fillStyle = grad;
          ctx.fill();
        }
        ctx.restore();
      };

      // Primary cyan/ice-blue wave (bottom/middle)
      drawAuroraWave(
        height * 0.65, 
        80, 
        3, 
        'rgba(34, 211, 238', // Cyan
        'rgba(14, 165, 233', // Ice blue
        0.07
      );

      // Secondary purple wave (higher up)
      drawAuroraWave(
        height * 0.45, 
        60, 
        2, 
        'rgba(139, 92, 246', // Purple
        'rgba(34, 211, 238', // Cyan
        0.05
      );

      // ── Layer 3: Mouse-Reactive Lighting Spotlight ──
      if (mouse.x !== null && mouse.y !== null) {
        const mouseGlow = ctx.createRadialGradient(
          mouse.x, mouse.y, 0,
          mouse.x, mouse.y, mouse.radius
        );
        // Soft icy-blue spotlight
        mouseGlow.addColorStop(0, 'rgba(125, 211, 252, 0.08)');
        mouseGlow.addColorStop(0.5, 'rgba(139, 92, 246, 0.03)');
        mouseGlow.addColorStop(1, 'rgba(0, 0, 0, 0)');
        
        ctx.save();
        ctx.globalCompositeOperation = 'screen';
        ctx.fillStyle = mouseGlow;
        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, mouse.radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }

      // ── Layer 4: Neural Network ──
      nodes.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        p.pulseVal += p.pulseSpeed;

        if (p.x < 0 || p.x > width) p.vx *= -1;
        if (p.y < 0 || p.y > height) p.vy *= -1;

        // Subtle node core glow
        const scale = 1 + Math.sin(p.pulseVal) * 0.25;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * scale, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(125, 211, 252, 0.25)'; // Ice blue
        ctx.fill();

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * 0.4, 0, Math.PI * 2);
        ctx.fillStyle = '#7dd3fc';
        ctx.fill();
      });

      // Connections between nodes
      for (let i = 0; i < nodes.length; i++) {
        const p1 = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const p2 = nodes[j];
          const dx = p1.x - p2.x;
          const dy = p1.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < CONNECTION_DIST) {
            const alpha = (1 - dist / CONNECTION_DIST) * 0.06;
            ctx.beginPath();
            ctx.strokeStyle = `rgba(125, 211, 252, ${alpha})`;
            ctx.lineWidth = 0.5;
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
      }

      // Occasional random background lightning strikes between close nodes
      if (Math.random() < 0.0075 && nodes.length > 1) {
        const startIdx = Math.floor(Math.random() * nodes.length);
        const nodeA = nodes[startIdx];
        let bestNode = null;
        let bestDist = Infinity;
        
        for (let k = 0; k < nodes.length; k++) {
          if (k === startIdx) continue;
          const dist = Math.hypot(nodeA.x - nodes[k].x, nodeA.y - nodes[k].y);
          if (dist < bestDist && dist < 220) {
            bestDist = dist;
            bestNode = nodes[k];
          }
        }
        if (bestNode) {
          activeLightnings.push({
            nodeA,
            nodeB: bestNode,
            life: Math.floor(Math.random() * 8 + 4),
            width: Math.random() * 1.5 + 0.6
          });
        }
      }

      // Render active lightning discharges
      activeLightnings.forEach((bolt) => {
        renderLightningBolt(bolt);
        bolt.life--;
      });
      activeLightnings = activeLightnings.filter(b => b.life > 0);

      // ── Layer 5: Snow Particle Drift ──
      snow.forEach((flake) => {
        flake.x += flake.vx * flake.parallax;
        flake.y += flake.vy * flake.parallax;

        // Drift reset
        if (flake.y > height) {
          flake.y = -10;
          flake.x = Math.random() * width;
        }
        if (flake.x > width) {
          flake.x = 0;
        }

        // Mouse push effect for snow
        if (mouse.x !== null && mouse.y !== null) {
          const dx = flake.x - mouse.x;
          const dy = flake.y - mouse.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 100) {
            const force = (100 - dist) / 100;
            flake.x += (dx / dist) * force * 3;
            flake.y += (dy / dist) * force * 3;
          }
        }

        ctx.beginPath();
        ctx.arc(flake.x, flake.y, flake.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(248, 250, 252, ${flake.opacity})`; // Snow color
        ctx.fill();
      });

      animId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0 overflow-hidden"
      style={{ opacity: 0.8 }}
    />
  );
}
