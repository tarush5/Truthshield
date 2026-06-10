import React, { useEffect, useRef } from 'react';

export default function NeuralNetworkBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;
    let particles = [];
    const PARTICLE_COUNT = 80;
    const CONNECTION_DIST = 140;
    
    // Track mouse position and interaction
    const mouse = {
      x: null,
      y: null,
      radius: 180,
    };

    const handleMouseMove = (e) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };

    const handleMouseLeave = () => {
      mouse.x = null;
      mouse.y = null;
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseleave', handleMouseLeave);

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    // Initialize particles with 3D-like depth properties
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push({
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        z: Math.random() * 2 + 0.5, // Depth scale
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        size: Math.random() * 2 + 1,
        pulseSpeed: 0.02 + Math.random() * 0.03,
        pulseValue: Math.random() * Math.PI,
      });
    }

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      // Update & Draw particles
      particles.forEach((p) => {
        // Move particles
        p.x += p.vx * p.z;
        p.y += p.vy * p.z;
        p.pulseValue += p.pulseSpeed;

        // Bounce on boundaries
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;

        // Interactive mouse force (subtle repulsion/attraction)
        if (mouse.x !== null && mouse.y !== null) {
          const dx = mouse.x - p.x;
          const dy = mouse.y - p.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < mouse.radius) {
            const force = (mouse.radius - dist) / mouse.radius;
            // Push particles slightly away
            p.x -= (dx / dist) * force * 1.5;
            p.y -= (dy / dist) * force * 1.5;
          }
        }

        // Pulse size for biological neural firing look
        const scale = 1 + Math.sin(p.pulseValue) * 0.3;
        const currentSize = p.size * scale * p.z;

        // Draw particle
        ctx.beginPath();
        ctx.arc(p.x, p.y, currentSize, 0, Math.PI * 2);
        
        // Deep cybersecurity palette - Stitch Cyan & Purple glowing nodes
        const isCyan = p.z > 1.5;
        const glowColor = isCyan ? 'rgba(0, 240, 255, ' : 'rgba(188, 19, 254, ';
        ctx.fillStyle = `${glowColor}${0.3 * p.z})`;
        ctx.fill();

        // Node core glowing spot
        ctx.beginPath();
        ctx.arc(p.x, p.y, currentSize * 0.4, 0, Math.PI * 2);
        ctx.fillStyle = isCyan ? '#00f0ff' : '#bc13fe';
        ctx.fill();
      });

      // Draw synapse connections
      for (let i = 0; i < particles.length; i++) {
        const p1 = particles[i];
        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const dx = p1.x - p2.x;
          const dy = p1.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < CONNECTION_DIST) {
            // Stronger link if close, faded if far, scaled by depth z
            const alpha = (1 - dist / CONNECTION_DIST) * 0.12 * Math.min(p1.z, p2.z);
            ctx.beginPath();
            
            // Neon gradient connections representing dynamic synapses
            const grad = ctx.createLinearGradient(p1.x, p1.y, p2.x, p2.y);
            const isCyan1 = p1.z > 1.5;
            const isCyan2 = p2.z > 1.5;
            grad.addColorStop(0, isCyan1 ? `rgba(0, 240, 255, ${alpha})` : `rgba(188, 19, 254, ${alpha})`);
            grad.addColorStop(1, isCyan2 ? `rgba(0, 240, 255, ${alpha})` : `rgba(188, 19, 254, ${alpha})`);
            
            ctx.strokeStyle = grad;
            ctx.lineWidth = 0.7 * Math.min(p1.z, p2.z);
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
      }

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
      style={{ opacity: 0.45 }}
    />
  );
}
