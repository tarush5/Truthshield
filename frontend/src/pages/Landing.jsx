import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { motion, useInView } from 'framer-motion';
import { 
  Shield, Zap, Globe, Users, Lock, Brain, 
  ArrowRight, CheckCircle2, Sparkles, Eye, 
  FileSearch, BarChart3, ChevronRight, 
  ShieldCheck, Cpu, Database, Fingerprint
} from 'lucide-react';

/* ─────────── Particle Network Canvas ─────────── */
function ParticleNetwork() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;
    let particles = [];
    const PARTICLE_COUNT = 60;
    const CONNECTION_DIST = 150;

    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = canvas.offsetHeight * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };
    resize();
    window.addEventListener('resize', resize);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push({
        x: Math.random() * canvas.offsetWidth,
        y: Math.random() * canvas.offsetHeight,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        size: Math.random() * 2 + 0.5,
      });
    }

    const draw = () => {
      ctx.clearRect(0, 0, canvas.offsetWidth, canvas.offsetHeight);
      
      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < CONNECTION_DIST) {
            const alpha = (1 - dist / CONNECTION_DIST) * 0.15;
            ctx.beginPath();
            ctx.strokeStyle = `rgba(59, 147, 255, ${alpha})`;
            ctx.lineWidth = 0.5;
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }

      // Draw & update particles
      particles.forEach(p => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(59, 147, 255, 0.4)';
        ctx.fill();
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > canvas.offsetWidth) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.offsetHeight) p.vy *= -1;
      });

      animId = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return <canvas ref={canvasRef} className="particle-canvas" style={{ width: '100%', height: '100%' }} />;
}

/* ─────────── Animated Counter ─────────── */
function AnimatedCounter({ end, duration = 2000, suffix = '', prefix = '' }) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-50px' });

  useEffect(() => {
    if (!inView) return;
    let start = 0;
    const startTime = performance.now();

    const step = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.floor(eased * end));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [inView, end, duration]);

  return <span ref={ref}>{prefix}{count.toLocaleString()}{suffix}</span>;
}

/* ─────────── Typing Effect ─────────── */
function TypingText({ texts, className }) {
  const [textIndex, setTextIndex] = useState(0);
  const [charIndex, setCharIndex] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const current = texts[textIndex];
    let timeout;

    if (!isDeleting && charIndex < current.length) {
      timeout = setTimeout(() => setCharIndex(c => c + 1), 60);
    } else if (!isDeleting && charIndex === current.length) {
      timeout = setTimeout(() => setIsDeleting(true), 2000);
    } else if (isDeleting && charIndex > 0) {
      timeout = setTimeout(() => setCharIndex(c => c - 1), 30);
    } else if (isDeleting && charIndex === 0) {
      setIsDeleting(false);
      setTextIndex((i) => (i + 1) % texts.length);
    }

    return () => clearTimeout(timeout);
  }, [charIndex, isDeleting, textIndex, texts]);

  return (
    <span className={className}>
      {texts[textIndex].substring(0, charIndex)}
      <span className="typing-cursor" />
    </span>
  );
}

/* ─────────── Feature Card ─────────── */
function FeatureCard({ icon: Icon, title, description, gradient, delay = 0, wide = false }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-50px' }}
      transition={{ duration: 0.6, delay }}
      className={`glass-card-interactive p-6 group relative overflow-hidden ${wide ? 'bento-wide' : ''}`}
    >
      {/* Accent glow */}
      <div className={`absolute -top-20 -right-20 w-40 h-40 rounded-full blur-3xl opacity-0 group-hover:opacity-20 transition-opacity duration-700 ${gradient}`} />
      
      <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center mb-4 shadow-lg`}>
        <Icon className="w-6 h-6 text-white" />
      </div>
      <h3 className="text-lg font-semibold font-display mb-2 text-white">{title}</h3>
      <p className="text-sm text-white/50 leading-relaxed">{description}</p>
    </motion.div>
  );
}

/* ─────────── Step Card ─────────── */
function StepCard({ number, icon: Icon, title, description, delay }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.6, delay }}
      className="text-center relative"
    >
      <div className="relative inline-flex mb-6">
        <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-brand-500/20 to-cyan-500/20 border border-white/10 flex items-center justify-center glow-pulse">
          <Icon className="w-8 h-8 text-brand-400" />
        </div>
        <div className="absolute -top-2 -right-2 w-7 h-7 rounded-full bg-brand-500 text-white text-xs font-bold flex items-center justify-center shadow-lg shadow-brand-500/30">
          {number}
        </div>
      </div>
      <h3 className="text-lg font-semibold font-display mb-2">{title}</h3>
      <p className="text-sm text-white/50 leading-relaxed max-w-[280px] mx-auto">{description}</p>
    </motion.div>
  );
}

/* ─────────── Main Landing Page ─────────── */
export default function Landing() {
  const heroRef = useRef(null);

  // Mouse spotlight effect
  const handleMouseMove = useCallback((e) => {
    const el = heroRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    el.style.setProperty('--mouse-x', `${e.clientX - rect.left}px`);
    el.style.setProperty('--mouse-y', `${e.clientY - rect.top}px`);
  }, []);

  const features = [
    { icon: Brain, title: 'Multimodal AI Pipeline', description: 'Analyze text, images, audio, video, and URLs through our 5-stage detection engine powered by transformer models.', gradient: 'from-brand-500 to-blue-600' },
    { icon: Database, title: 'pgvector RAG Verification', description: 'Semantic search across verified fact databases using retrieval-augmented generation for evidence-based verdicts.', gradient: 'from-purple-500 to-indigo-600' },
    { icon: Globe, title: 'Real-Time Threat Intel', description: 'Live monitoring of misinformation trends across social platforms with geographic threat mapping.', gradient: 'from-cyan-500 to-teal-600' },
    { icon: Users, title: 'Multi-Tenant Workspaces', description: 'Team collaboration with RBAC roles, shared dashboards, and isolated data environments.', gradient: 'from-emerald-500 to-green-600' },
    { icon: Cpu, title: 'Developer API', description: 'RESTful API with key management, rate limiting, and webhook integrations for automated content pipelines.', gradient: 'from-amber-500 to-orange-600', wide: true },
    { icon: Fingerprint, title: 'Enterprise-Grade Security', description: 'End-to-end encryption, audit trails, SOC2-ready architecture with comprehensive logging.', gradient: 'from-rose-500 to-red-600' },
  ];

  const stats = [
    { value: 12847, label: 'Claims Analyzed', suffix: '+' },
    { value: 98, label: 'Accuracy Rate', suffix: '.7%' },
    { value: 2, label: 'Avg Response Time', prefix: '<', suffix: 's' },
    { value: 50, label: 'Trusted Sources', suffix: '+' },
  ];

  return (
    <div className="relative -mt-20">
      {/* ════════ HERO SECTION ════════ */}
      <section
        ref={heroRef}
        onMouseMove={handleMouseMove}
        className="relative min-h-screen flex items-center justify-center overflow-hidden spotlight"
      >
        {/* Background layers */}
        <div className="aurora-bg">
          <div className="aurora-blob aurora-blob-1" />
          <div className="aurora-blob aurora-blob-2" />
          <div className="aurora-blob aurora-blob-3" />
        </div>
        <ParticleNetwork />
        <div className="bg-grid absolute inset-0 pointer-events-none" />

        {/* Hero content */}
        <div className="relative z-10 max-w-5xl mx-auto px-4 text-center pt-32 pb-20">
          {/* Status badge */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass-card mb-8 float"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-semibold text-white/70">AI-Powered Misinformation Detection</span>
            <Sparkles className="w-3.5 h-3.5 text-brand-400" />
          </motion.div>

          {/* Main heading */}
          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.1 }}
            className="text-5xl sm:text-6xl lg:text-7xl font-bold font-display tracking-tight mb-6 leading-[1.1]"
          >
            <span className="gradient-text-hero">Defend Truth</span>
            <br />
            <span className="text-white/90">with </span>
            <TypingText
              texts={['AI Verification', 'Deepfake Detection', 'Fact Checking', 'Source Analysis']}
              className="gradient-text"
            />
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.3 }}
            className="text-lg sm:text-xl text-white/50 max-w-2xl mx-auto mb-10 leading-relaxed text-balance"
          >
            Enterprise-grade AI platform that detects misinformation, deepfakes, and manipulated content 
            across text, images, audio, and video in real-time.
          </motion.p>

          {/* CTA buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16"
          >
            <Link to="/login" className="btn-primary-lg flex items-center gap-2 group">
              Get Started Free
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Link>
            <a href="#features" className="btn-secondary-lg flex items-center gap-2">
              <Eye className="w-5 h-5" />
              See How It Works
            </a>
          </motion.div>

          {/* Stats counters */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.7 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl mx-auto"
          >
            {stats.map((stat, i) => (
              <div key={i} className="counter-card rounded-xl" style={{ '--accent-color': i === 0 ? 'rgba(59,147,255,0.08)' : i === 1 ? 'rgba(16,185,129,0.08)' : i === 2 ? 'rgba(6,182,212,0.08)' : 'rgba(139,92,246,0.08)' }}>
                <div className="text-3xl font-bold font-display gradient-text">
                  <AnimatedCounter end={stat.value} prefix={stat.prefix} suffix={stat.suffix} />
                </div>
                <div className="text-xs text-white/40 mt-1 font-medium">{stat.label}</div>
              </div>
            ))}
          </motion.div>
        </div>

        {/* Scroll indicator */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.5 }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2"
        >
          <div className="w-6 h-10 rounded-full border-2 border-white/20 flex items-start justify-center p-1.5">
            <motion.div
              animate={{ y: [0, 12, 0] }}
              transition={{ repeat: Infinity, duration: 1.5, ease: 'easeInOut' }}
              className="w-1.5 h-1.5 rounded-full bg-brand-400"
            />
          </div>
        </motion.div>
      </section>

      {/* ════════ PRODUCT DEMO ════════ */}
      <section className="relative py-20 px-4">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="glass-card rounded-2xl overflow-hidden border border-white/10 shadow-2xl shadow-brand-500/5"
          >
            {/* Browser chrome */}
            <div className="flex items-center gap-2 px-4 py-3 bg-white/[0.03] border-b border-white/5">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-500/60" />
                <div className="w-3 h-3 rounded-full bg-amber-500/60" />
                <div className="w-3 h-3 rounded-full bg-emerald-500/60" />
              </div>
              <div className="flex-1 flex items-center gap-2 ml-4">
                <div className="flex-1 flex items-center gap-2 px-3 py-1.5 bg-white/5 rounded-lg text-xs text-white/40 max-w-md">
                  <Lock className="w-3 h-3 text-emerald-400" />
                  truthshield.ai/analyze
                </div>
              </div>
            </div>

            {/* Mock content */}
            <div className="p-6 md:p-8 grid md:grid-cols-2 gap-6">
              {/* Input side */}
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-8 h-8 rounded-lg bg-brand-500/20 flex items-center justify-center">
                    <FileSearch className="w-4 h-4 text-brand-400" />
                  </div>
                  <span className="text-sm font-semibold">Content Analysis</span>
                </div>
                <div className="bg-white/5 rounded-xl p-4 border border-white/5">
                  <div className="text-xs text-white/30 mb-2">Analyzing claim:</div>
                  <p className="text-sm text-white/70 leading-relaxed italic">
                    "A new study confirms that 5G towers are linked to health issues in major cities..."
                  </p>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {['Text Analysis', 'Source Check', 'Claim Extraction', 'Evidence Match'].map((tag, i) => (
                    <motion.span
                      key={tag}
                      initial={{ opacity: 0, scale: 0.8 }}
                      whileInView={{ opacity: 1, scale: 1 }}
                      viewport={{ once: true }}
                      transition={{ delay: 0.3 + i * 0.1 }}
                      className="px-2.5 py-1 rounded-lg bg-brand-500/10 text-brand-400 text-xs font-medium border border-brand-500/10"
                    >
                      {tag}
                    </motion.span>
                  ))}
                </div>
              </div>

              {/* Result side */}
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-8 h-8 rounded-lg bg-red-500/20 flex items-center justify-center">
                    <ShieldCheck className="w-4 h-4 text-red-400" />
                  </div>
                  <span className="text-sm font-semibold">Verdict</span>
                  <span className="badge-danger ml-auto">FALSE</span>
                </div>
                <div className="space-y-3">
                  {/* Trust Score */}
                  <div className="bg-white/5 rounded-xl p-4 border border-white/5">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-xs text-white/40">Trust Score</span>
                      <span className="text-lg font-bold text-red-400">23.4%</span>
                    </div>
                    <div className="progress-bar">
                      <motion.div
                        initial={{ width: 0 }}
                        whileInView={{ width: '23.4%' }}
                        viewport={{ once: true }}
                        transition={{ duration: 1.5, delay: 0.5, ease: 'easeOut' }}
                        className="progress-fill bg-gradient-to-r from-red-500 to-red-400"
                      />
                    </div>
                  </div>
                  {/* Evidence items */}
                  {[
                    { text: 'No peer-reviewed evidence found', status: false },
                    { text: 'WHO contradicts this claim', status: false },
                    { text: '3 fact-checkers rate FALSE', status: false },
                  ].map((item, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: 20 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: 0.8 + i * 0.15 }}
                      className="flex items-center gap-2 text-sm"
                    >
                      <CheckCircle2 className={`w-4 h-4 ${item.status ? 'text-emerald-400' : 'text-red-400'}`} />
                      <span className="text-white/60">{item.text}</span>
                    </motion.div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ════════ FEATURES BENTO GRID ════════ */}
      <section id="features" className="relative py-24 px-4">
        <div className="max-w-6xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center mb-16"
          >
            <span className="section-label mb-3 block">Platform Capabilities</span>
            <h2 className="text-4xl sm:text-5xl font-bold font-display tracking-tight mb-4">
              Everything you need to <span className="gradient-text">fight misinformation</span>
            </h2>
            <p className="text-lg text-white/40 max-w-xl mx-auto">
              A complete toolkit for organizations serious about content integrity and truth verification.
            </p>
          </motion.div>

          <div className="bento-grid">
            {features.map((feature, i) => (
              <FeatureCard key={feature.title} {...feature} delay={i * 0.1} />
            ))}
          </div>
        </div>
      </section>

      {/* ════════ HOW IT WORKS ════════ */}
      <section className="relative py-24 px-4">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <span className="section-label mb-3 block">How It Works</span>
            <h2 className="text-4xl sm:text-5xl font-bold font-display tracking-tight mb-4">
              Three steps to <span className="gradient-text">verified truth</span>
            </h2>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-8 md:gap-12 relative">
            {/* Connection line */}
            <div className="hidden md:block absolute top-10 left-[20%] right-[20%] h-px bg-gradient-to-r from-transparent via-brand-500/30 to-transparent" />
            
            <StepCard
              number={1}
              icon={FileSearch}
              title="Upload Content"
              description="Submit any text, image, audio, video, or URL for analysis through our secure multimodal pipeline."
              delay={0}
            />
            <StepCard
              number={2}
              icon={Brain}
              title="AI Analysis"
              description="Our 5-stage pipeline processes content through detection, verification, and cross-signal correlation engines."
              delay={0.2}
            />
            <StepCard
              number={3}
              icon={ShieldCheck}
              title="Get Verified Results"
              description="Receive a comprehensive report with trust score, evidence citations, and actionable counter-narratives."
              delay={0.4}
            />
          </div>
        </div>
      </section>

      {/* ════════ TRUST & SECURITY ════════ */}
      <section className="relative py-24 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <span className="section-label mb-3 block">Trust & Security</span>
            <h2 className="text-4xl sm:text-5xl font-bold font-display tracking-tight mb-4">
              Built for <span className="gradient-text">enterprise trust</span>
            </h2>
            <p className="text-lg text-white/40 max-w-xl mx-auto mb-12">
              Security-first architecture designed for organizations that demand the highest standards.
            </p>
          </motion.div>

          <div className="flex flex-wrap items-center justify-center gap-4">
            {[
              { icon: Lock, label: 'End-to-End Encrypted' },
              { icon: ShieldCheck, label: 'SOC2 Ready' },
              { icon: Globe, label: 'GDPR Compliant' },
              { icon: Fingerprint, label: 'Zero-Trust Auth' },
              { icon: BarChart3, label: 'Full Audit Trail' },
            ].map((badge, i) => (
              <motion.div
                key={badge.label}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="security-badge rounded-xl"
              >
                <badge.icon className="w-5 h-5 text-brand-400" />
                <span>{badge.label}</span>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════ CTA SECTION ════════ */}
      <section className="relative py-24 px-4">
        <div className="max-w-3xl mx-auto">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="glass-card p-12 md:p-16 text-center relative overflow-hidden"
          >
            {/* Background glow */}
            <div className="absolute inset-0 bg-gradient-to-br from-brand-500/10 via-transparent to-cyan-500/10 pointer-events-none" />
            
            <div className="relative z-10">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-500 to-cyan-500 flex items-center justify-center mx-auto mb-6 shadow-xl shadow-brand-500/25 glow-pulse">
                <Shield className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold font-display tracking-tight mb-4">
                Ready to defend against misinformation?
              </h2>
              <p className="text-lg text-white/50 mb-8 max-w-lg mx-auto">
                Join organizations worldwide using TruthShield to protect their audiences from false and misleading content.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link to="/login" className="btn-primary-lg flex items-center gap-2 group">
                  Start Free Trial
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </Link>
                <Link to="/login" className="btn-secondary-lg flex items-center gap-2">
                  <Zap className="w-5 h-5" />
                  Enterprise Demo
                </Link>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ════════ FOOTER ════════ */}
      <footer className="border-t border-white/5 py-12 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            {/* Brand */}
            <div className="md:col-span-1">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-cyan-500 flex items-center justify-center">
                  <Shield className="w-4 h-4 text-white" />
                </div>
                <span className="font-bold font-display gradient-text">TruthShield</span>
              </div>
              <p className="text-sm text-white/40 leading-relaxed">
                AI-powered misinformation detection platform for the modern enterprise.
              </p>
            </div>
            {/* Links */}
            {[
              { title: 'Product', links: ['Features', 'Pricing', 'API Docs', 'Changelog'] },
              { title: 'Company', links: ['About', 'Blog', 'Careers', 'Contact'] },
              { title: 'Legal', links: ['Privacy', 'Terms', 'Security', 'Compliance'] },
            ].map((col) => (
              <div key={col.title}>
                <h4 className="text-sm font-semibold mb-4">{col.title}</h4>
                <ul className="space-y-2">
                  {col.links.map((link) => (
                    <li key={link}>
                      <span className="text-sm text-white/40 hover:text-white/70 cursor-pointer transition-colors">
                        {link}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="border-t border-white/5 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
            <span className="text-xs text-white/30">© 2025 TruthShield. All rights reserved.</span>
            <div className="flex items-center gap-4">
              <span className="text-xs text-white/30">Powered by AI</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs text-white/30">All systems operational</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
