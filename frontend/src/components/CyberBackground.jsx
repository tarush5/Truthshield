import React, { useRef, useEffect } from 'react';

export default function CyberBackground() {
  const canvasRef = useRef(null);
  const mouseRef = useRef({ x: -1000, y: -1000 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationId;
    let particles = [];
    let codeFragments = [];

    const isMobile = window.innerWidth < 768;
    const EMBER_COUNT = isMobile ? 30 : 70;
    const CODE_COUNT = isMobile ? 12 : 25;
    const MOUSE_RADIUS = 160;

    // Fiery color palette (yellow-gold, orange-red, neon red, dark crimson)
    const EMBER_COLORS = ['#FFD700', '#FF8C00', '#FF3D00', '#FF1744', '#B11226', '#8B0000'];
    const CODE_WORDS = [
      '01', '10', '0xFA8B', 'THREAT_DETECTION', 'INGEST_FEED', 'CORE_ACTIVE',
      'SECURE_NODE', 'VERDICT_SYNTHESIS', 'SHIELD_ON', 'INTELLIGENCE', 'AUDIT_TRAIL',
      '0x3E2D', 'STATUS_OK', 'DECRYPTING', 'ANALYZING', 'CLAIM_VECTORS'
    ];

    function resize() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    // Initialize fire embers
    for (let i = 0; i < EMBER_COUNT; i++) {
      particles.push(createEmber(true));
    }

    // Initialize code fragments
    for (let i = 0; i < CODE_COUNT; i++) {
      codeFragments.push(createCodeFragment(true));
    }

    function createEmber(randomY = false) {
      return {
        x: Math.random() * canvas.width,
        y: randomY ? Math.random() * canvas.height : canvas.height + 15,
        vx: (Math.random() - 0.5) * 0.4,
        vy: -Math.random() * 1.2 - 0.4, // Float upward at varying speeds
        radius: Math.random() * 2.5 + 0.5,
        color: EMBER_COLORS[Math.floor(Math.random() * EMBER_COLORS.length)],
        opacity: Math.random() * 0.7 + 0.3,
        life: 1.0,
        decay: Math.random() * 0.003 + 0.0015,
        driftPhase: Math.random() * Math.PI * 2,
        driftSpeed: Math.random() * 0.01 + 0.005,
      };
    }

    function createCodeFragment(randomY = false) {
      return {
        x: Math.random() * canvas.width,
        y: randomY ? Math.random() * canvas.height : canvas.height + 25,
        vy: -Math.random() * 0.7 - 0.2, // Float upward slowly
        text: CODE_WORDS[Math.floor(Math.random() * CODE_WORDS.length)],
        size: Math.floor(Math.random() * 4) + 8, // 8px to 11px
        opacity: Math.random() * 0.3 + 0.1,
        life: 1.0,
        decay: Math.random() * 0.002 + 0.001,
        driftPhase: Math.random() * Math.PI * 2,
        driftSpeed: Math.random() * 0.005 + 0.002,
      };
    }

    function animate() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const time = Date.now() * 0.001;

      // Draw bottom fire hearth glow (radial-gradient that flickers)
      const flicker = Math.sin(time * 12) * 0.015 + 0.985;
      const fogGradient = ctx.createLinearGradient(0, canvas.height * 0.4, 0, canvas.height);
      fogGradient.addColorStop(0, 'transparent');
      fogGradient.addColorStop(0.7, 'rgba(80, 0, 0, 0.02)');
      fogGradient.addColorStop(1, `rgba(180, 10, 15, ${0.1 * flicker})`);
      ctx.fillStyle = fogGradient;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw active heat wave distortion visual cues (subtle horizontal gradients)
      ctx.strokeStyle = `rgba(255, 30, 30, ${0.01 * flicker})`;
      ctx.lineWidth = 15;
      for (let i = 0; i < 3; i++) {
        const waveY = (canvas.height * 0.7 + i * 80 + Math.sin(time + i) * 20) % canvas.height;
        ctx.beginPath();
        ctx.moveTo(0, waveY);
        ctx.bezierCurveTo(
          canvas.width * 0.25, waveY - 15,
          canvas.width * 0.75, waveY + 15,
          canvas.width, waveY
        );
        ctx.stroke();
      }

      // Update and draw code fragments (floating red binary/threat strings)
      codeFragments.forEach((c, idx) => {
        // Wind drift
        c.x += Math.sin(time * c.driftSpeed * 10 + c.driftPhase) * 0.08;

        // Mouse repulsion
        const dx = c.x - mouseRef.current.x;
        const dy = c.y - mouseRef.current.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < MOUSE_RADIUS && dist > 0) {
          const force = ((MOUSE_RADIUS - dist) / MOUSE_RADIUS) * 0.4;
          c.x += (dx / dist) * force;
        }

        c.y += c.vy;
        c.life -= c.decay;

        // Draw code fragment
        ctx.font = `${c.size}px var(--font-mono), monospace`;
        ctx.fillStyle = `rgba(255, 23, 68, ${c.opacity * c.life})`;
        ctx.fillText(c.text, c.x, c.y);

        // Reset if dead or off top
        if (c.life <= 0 || c.y < -20 || c.x < -50 || c.x > canvas.width + 50) {
          codeFragments[idx] = createCodeFragment(false);
        }
      });

      // Update and draw fire embers
      particles.forEach((p, idx) => {
        // Wind drift
        p.vx += Math.sin(time * p.driftSpeed * 10 + p.driftPhase) * 0.02;
        p.vx *= 0.98; // damping

        // Mouse repulsion (stronger for light embers)
        const dx = p.x - mouseRef.current.x;
        const dy = p.y - mouseRef.current.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < MOUSE_RADIUS && dist > 0) {
          const force = ((MOUSE_RADIUS - dist) / MOUSE_RADIUS) * 0.08;
          p.vx += (dx / dist) * force;
          p.vy += (dy / dist) * force * 0.5; // push up too
        }

        p.x += p.vx;
        p.y += p.vy;
        p.life -= p.decay;

        // Color shifts from yellow-orange to deep red as it cools (life decays)
        let alpha = p.opacity * p.life;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius * p.life, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = alpha;
        ctx.fill();

        // Ember Glow Aura (Flickering fire glow)
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius * 4.5 * p.life, 0, Math.PI * 2);
        const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.radius * 4.5 * p.life);
        glow.addColorStop(0, p.color + '40');
        glow.addColorStop(0.5, p.color + '10');
        glow.addColorStop(1, 'transparent');
        ctx.fillStyle = glow;
        ctx.globalAlpha = 0.8;
        ctx.fill();
        ctx.globalAlpha = 1;

        // Reset if dead or off top
        if (p.life <= 0 || p.y < -15 || p.x < -15 || p.x > canvas.width + 15) {
          particles[idx] = createEmber(false);
        }
      });

      animationId = requestAnimationFrame(animate);
    }

    animate();

    const handleMouse = (e) => {
      mouseRef.current = { x: e.clientX, y: e.clientY };
    };
    window.addEventListener('mousemove', handleMouse, { passive: true });

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', handleMouse);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 z-0 pointer-events-none"
      style={{
        background:
          'radial-gradient(ellipse at 50% 15%, rgba(120,0,0,0.14) 0%, rgba(5,0,0,0.98) 60%, #000000 100%)',
      }}
    />
  );
}
