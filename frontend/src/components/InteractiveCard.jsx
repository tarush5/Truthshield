import React, { useState, useRef, useEffect } from 'react';

export default function InteractiveCard({ children, className = '', tiltIntensity = 12, glareIntensity = 0.35 }) {
  const cardRef = useRef(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [glare, setGlare] = useState({ x: 50, y: 50, opacity: 0 });
  const [isHovered, setIsHovered] = useState(false);

  // Use requestAnimationFrame for smooth inertia/momentum
  const rafRef = useRef(null);
  const targetTiltRef = useRef({ x: 0, y: 0 });
  const currentTiltRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const updateTilt = () => {
      // Linear interpolation (lerp) for smooth inertia/momentum
      const ease = 0.12; 
      currentTiltRef.current.x += (targetTiltRef.current.x - currentTiltRef.current.x) * ease;
      currentTiltRef.current.y += (targetTiltRef.current.y - currentTiltRef.current.y) * ease;

      setTilt({
        x: currentTiltRef.current.x,
        y: currentTiltRef.current.y,
      });

      if (isHovered || Math.abs(currentTiltRef.current.x) > 0.01 || Math.abs(currentTiltRef.current.y) > 0.01) {
        rafRef.current = requestAnimationFrame(updateTilt);
      }
    };

    rafRef.current = requestAnimationFrame(updateTilt);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [isHovered]);

  const handleMouseMove = (e) => {
    const card = cardRef.current;
    if (!card) return;

    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left; // x coordinate within element
    const y = e.clientY - rect.top;  // y coordinate within element

    const width = rect.width;
    const height = rect.height;

    // Calculate normalized values (-0.5 to 0.5)
    const normalizedX = (x / width) - 0.5;
    const normalizedY = (y / height) - 0.5;

    // Compute tilt angles (rotateX depends on y, rotateY depends on x)
    targetTiltRef.current = {
      x: -normalizedY * tiltIntensity,
      y: normalizedX * tiltIntensity,
    };

    // Calculate glare position
    const glareX = (x / width) * 100;
    const glareY = (y / height) * 100;

    setGlare({
      x: glareX,
      y: glareY,
      opacity: glareIntensity,
    });
  };

  const handleMouseEnter = () => {
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    targetTiltRef.current = { x: 0, y: 0 };
    setGlare(prev => ({ ...prev, opacity: 0 }));
  };

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`relative rounded-2xl transition-shadow duration-300 ${className}`}
      style={{
        transformStyle: 'preserve-3d',
        transform: `perspective(1000px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg) scale3d(${isHovered ? 1.02 : 1}, ${isHovered ? 1.02 : 1}, 1)`,
        transition: 'transform 0.1s ease-out, shadow 0.3s ease',
        boxShadow: isHovered 
          ? '0 25px 50px -12px rgba(125, 211, 252, 0.15), 0 0 30px 2px rgba(139, 92, 246, 0.05)' 
          : '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
      }}
    >
      {/* Glare effect */}
      <div
        className="absolute inset-0 pointer-events-none rounded-2xl transition-opacity duration-300 z-50"
        style={{
          background: `radial-gradient(circle 200px at ${glare.x}% ${glare.y}%, rgba(255, 255, 255, 0.12), transparent)`,
          opacity: glare.opacity,
        }}
      />

      {/* Underglow glow backplate */}
      <div
        className="absolute -inset-px rounded-2xl bg-gradient-to-br from-cyan-500/20 to-purple-500/20 opacity-0 transition-opacity duration-500 pointer-events-none z-0"
        style={{
          opacity: isHovered ? 1 : 0,
        }}
      />

      {/* Children content wrapper with depth */}
      <div className="relative z-10 w-full h-full" style={{ transform: 'translateZ(10px)' }}>
        {children}
      </div>
    </div>
  );
}
