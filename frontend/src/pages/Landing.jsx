import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import InteractiveCard from '../components/InteractiveCard';

import { 
  Shield, Zap, Globe, Users, Lock, Brain, 
  ArrowRight, CheckCircle2, Sparkles, Eye, 
  FileSearch, BarChart3, ChevronRight, Play,
  ShieldCheck, Cpu, Database, Fingerprint, Star,
  Check, Info, MessageSquare, Terminal, Heart
} from 'lucide-react';

/* ─────────── 3D-Like Rotating Cyber Sphere ─────────── */
function IntelligenceSphere() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;
    let angleX = 0.003;
    let angleY = 0.003;
    
    // Create points on a sphere
    const points = [];
    const numPoints = 180;
    const radius = 120;

    for (let i = 0; i < numPoints; i++) {
      const theta = Math.acos(Math.random() * 2 - 1);
      const phi = Math.random() * Math.PI * 2;
      
      points.push({
        x: radius * Math.sin(theta) * Math.cos(phi),
        y: radius * Math.sin(theta) * Math.sin(phi),
        z: radius * Math.cos(theta)
      });
    }

    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = canvas.offsetHeight * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };
    resize();
    window.addEventListener('resize', resize);

    const rotateX = (p, angle) => {
      const rad = angle;
      const cos = Math.cos(rad);
      const sin = Math.sin(rad);
      const y = p.y * cos - p.z * sin;
      const z = p.y * sin + p.z * cos;
      return { x: p.x, y, z };
    };

    const rotateY = (p, angle) => {
      const rad = angle;
      const cos = Math.cos(rad);
      const sin = Math.sin(rad);
      const x = p.x * cos + p.z * sin;
      const z = -p.x * sin + p.z * cos;
      return { x, y: p.y, z };
    };

    const draw = () => {
      const w = canvas.offsetWidth;
      const h = canvas.offsetHeight;
      ctx.clearRect(0, 0, w, h);
      ctx.translate(w / 2, h / 2);

      // Rotate and project points
      const projected = points.map(p => {
        const p1 = rotateX(p, angleX);
        const p2 = rotateY(p1, angleY);
        
        // Update positions back to object
        p.x = p2.x;
        p.y = p2.y;
        p.z = p2.z;

        // Simple perspective projection
        const fov = 350;
        const scale = fov / (fov + p2.z);
        return {
          x: p2.x * scale,
          y: p2.y * scale,
          z: p2.z,
          opacity: (p2.z + radius) / (radius * 2) * 0.7 + 0.1
        };
      });

      // Draw connection synapses
      ctx.lineWidth = 0.5;
      for (let i = 0; i < projected.length; i += 4) {
        const p1 = projected[i];
        for (let j = i + 1; j < projected.length; j += 15) {
          const p2 = projected[j];
          const dist = Math.hypot(p1.x - p2.x, p1.y - p2.y);
          if (dist < 75) {
            ctx.beginPath();
            ctx.strokeStyle = `rgba(125, 211, 252, ${p1.opacity * 0.15 * (1 - dist / 75)})`;
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
      }

      // Draw projected nodes
      projected.forEach(p => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.max(1, (p.z + radius) / radius * 2.2), 0, Math.PI * 2);
        
        // Dynamic ice-blue to purple color depending on depth
        const glow = p.z > 0 ? 'rgba(125, 211, 252, ' : 'rgba(139, 92, 246, ';
        ctx.fillStyle = `${glow}${p.opacity * 0.85})`;
        ctx.fill();

        // Node center spot
        if (p.z > 40) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, 0.7, 0, Math.PI * 2);
          ctx.fillStyle = '#ffffff';
          ctx.fill();
        }
      });

      ctx.translate(-w / 2, -h / 2);
      animId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return <canvas ref={canvasRef} className="w-full h-full max-w-[420px] max-h-[420px] mx-auto aspect-square" />;
}

/* ─────────── Landing Page ─────────── */
export default function Landing() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('text');
  const [inputText, setInputText] = useState("Breaking: Scientific journal claims quantum computer model completely cracks standard blockchain encryption keys.");
  const [demoState, setDemoState] = useState('idle'); // idle | processing | result
  const [currentDemoStage, setCurrentDemoStage] = useState(0);

  const demoStages = [
    'Decompressing and segmenting file streams...',
    'Extracting metadata, source structures & claim vectors...',
    'Cross-referencing global credibility consensus databases...',
    'Performing cross-signal sentiment & semantic consistency runs...',
    'Synthesizing ultimate fact verdict & counter-narrative...'
  ];

  const handleRunDemo = () => {
    if (demoState !== 'idle') return;
    setDemoState('processing');
    setCurrentDemoStage(0);

    const interval = setInterval(() => {
      setCurrentDemoStage(prev => {
        if (prev < demoStages.length - 1) {
          return prev + 1;
        } else {
          clearInterval(interval);
          setDemoState('result');
          return prev;
        }
      });
    }, 1200);
  };

  const handleResetDemo = () => {
    setDemoState('idle');
    setCurrentDemoStage(0);
  };

  return (
    <div className="relative -mt-20 overflow-hidden">
      
      {/* ════════ HERO SECTION ════════ */}
      <section className="relative min-h-screen flex items-center justify-center pt-28 pb-16 px-4">
        <div className="max-w-7xl mx-auto w-full grid lg:grid-cols-12 gap-12 items-center relative z-10">
          
          {/* Hero left text */}
          <div className="lg:col-span-7 space-y-6 text-left">
            {/* Status badge */}
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-sky-500/10 border border-sky-400/30 electric-glow"
            >
              <Sparkles className="w-3.5 h-3.5 text-sky-400" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-sky-300">Arctic v2.4 Live Threat Engine</span>
            </motion.div>

            {/* Giant Title */}
            <motion.h1
              initial={{ opacity: 0, y: 25 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="text-5xl sm:text-6xl lg:text-7xl font-bold font-display tracking-tight leading-[1.05] text-white"
            >
              See Through <br/>
              <span className="gradient-text-hero electric-text">Digital Deception.</span>
            </motion.h1>

            {/* Subheadline */}
            <motion.p
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="text-base sm:text-lg text-white/50 max-w-xl leading-relaxed font-sans text-balance"
            >
              AI-powered misinformation intelligence across text, image, audio, video, and web. 
              Deploy the Arctic security suite to defend truth and verify global records instantly.
            </motion.p>

            {/* CTAs */}
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3 }}
              className="flex flex-wrap items-center gap-4 pt-2"
            >
              <Link to="/login" className="btn-primary-lg flex items-center gap-2 group text-sm">
                Start Analyzing
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </Link>
              <a href="#demo" className="btn-secondary-lg flex items-center gap-2 text-sm">
                <Play className="w-4 h-4 text-sky-400 fill-sky-400/20" />
                Watch Demo
              </a>
            </motion.div>

            {/* Quick Metrics */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="grid grid-cols-3 gap-6 pt-8 border-t border-white/5 max-w-lg"
            >
              {[
                { val: '2.1M+', label: 'Claims Analyzed' },
                { val: '99.4%', label: 'Audited Accuracy' },
                { val: '0.4s', label: 'Inference Velocity' },
              ].map(metric => (
                <div key={metric.label}>
                  <p className="text-xl font-bold font-display text-white">{metric.val}</p>
                  <p className="text-[10px] text-white/30 uppercase tracking-widest mt-0.5">{metric.label}</p>
                </div>
              ))}
            </motion.div>
          </div>

          {/* Hero right visualization */}
          <div className="lg:col-span-5 flex justify-center items-center">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.8, ease: 'easeOut' }}
              className="relative w-full flex items-center justify-center"
            >
              {/* Rotating outer orbit rings */}
              <div className="absolute w-[440px] h-[440px] rounded-full border border-white/5 animate-pulse-slow" />
              <div className="absolute w-[360px] h-[360px] rounded-full border border-sky-500/10 border-dashed animate-spin" style={{ animationDuration: '30s' }} />
              <div className="absolute w-[280px] h-[280px] rounded-full border border-purple-500/10 animate-spin" style={{ animationDuration: '20s', animationDirection: 'reverse' }} />
              
              <IntelligenceSphere />
            </motion.div>
          </div>

        </div>
      </section>

      {/* ════════ LIVE DEMO SECTION ════════ */}
      <section id="demo" className="relative py-24 px-4 border-t border-white/5 bg-white/[0.01]">
        <div className="max-w-5xl mx-auto text-center space-y-12">
          
          <div className="space-y-4">
            <span className="section-label">Interactive Experience</span>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold font-display tracking-tight text-white leading-none">
              Deploy the Arctic Pipeline
            </h2>
            <p className="text-sm sm:text-base text-white/45 max-w-lg mx-auto">
              Paste a suspected claim vector or upload media to test TruthShield's decision layers in real-time.
            </p>
          </div>

          {/* Browser Chrome Simulator */}
          <InteractiveCard className="border border-white/10 shadow-2xl bg-[#030712]/40 backdrop-blur-xl laser-sweep">
            <motion.div

              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="overflow-hidden text-left"
            >
            {/* Header chrome buttons */}
            <div className="flex items-center justify-between px-4 py-3.5 bg-[#071124]/50 border-b border-white/5">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-500/40" />
                <div className="w-3 h-3 rounded-full bg-amber-500/40" />
                <div className="w-3 h-3 rounded-full bg-emerald-500/40" />
              </div>
              <div className="flex items-center gap-1.5 px-3 py-1 bg-white/5 rounded-lg text-[10px] text-white/30 font-mono">
                <Terminal className="w-3 h-3 text-sky-400" />
                terminal://arctic-intelligence-cluster-12
              </div>
              <div className="w-12" />
            </div>

            {/* Simulator Workspace */}
            <div className="p-6 md:p-8 min-h-[340px] flex flex-col justify-between">
              <AnimatePresence mode="wait">
                
                {/* IDLE state */}
                {demoState === 'idle' && (
                  <motion.div
                    key="idle"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="space-y-6 flex-1 flex flex-col justify-between"
                  >
                    <div className="space-y-3">
                      <label className="text-xs font-semibold text-white/40 uppercase tracking-widest">Verify Claim Input</label>
                      <textarea
                        value={inputText}
                        onChange={(e) => setInputText(e.target.value)}
                        className="input-field h-24 text-sm font-sans"
                        placeholder="Type claims or paste news articles..."
                      />
                    </div>
                    <div className="flex justify-between items-center">
                      <div className="flex gap-3 text-xs text-white/30">
                        <span>🚀 NLP Model: Transformer 5B</span>
                        <span>⚡ pgvector RAG: Active</span>
                      </div>
                      <button
                        onClick={handleRunDemo}
                        className="btn-primary flex items-center gap-2 text-xs py-2 px-5"
                      >
                        Run Pipeline
                        <Zap className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </motion.div>
                )}

                {/* PROCESSING state */}
                {demoState === 'processing' && (
                  <motion.div
                    key="processing"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="space-y-6 flex-1 flex flex-col justify-center"
                  >
                    <div className="space-y-2 text-center">
                      <div className="w-8 h-8 rounded-full border-2 border-sky-400 border-t-transparent animate-spin mx-auto mb-4" />
                      <p className="text-sm font-semibold text-white/70">Processing Claim Vector</p>
                      <p className="text-xs text-sky-400 font-mono animate-pulse">{demoStages[currentDemoStage]}</p>
                    </div>
                    <div className="w-full max-w-md mx-auto progress-bar">
                      <motion.div 
                        className="progress-fill bg-gradient-to-r from-sky-500 to-purple-500"
                        initial={{ width: '0%' }}
                        animate={{ width: `${(currentDemoStage + 1) * 20}%` }}
                        transition={{ duration: 0.5 }}
                      />
                    </div>
                  </motion.div>
                )}

                {/* RESULT state */}
                {demoState === 'result' && (
                  <motion.div
                    key="result"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="grid md:grid-cols-2 gap-8 flex-1 items-center"
                  >
                    {/* Left: Score Gauge */}
                    <div className="flex flex-col items-center justify-center p-6 bg-white/[0.02] border border-white/5 rounded-xl">
                      <span className="text-[10px] font-bold text-white/40 uppercase tracking-widest mb-4">Verdict Output</span>
                      
                      <div className="relative w-32 h-32 flex items-center justify-center mb-4">
                        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                          <circle cx="50" cy="50" r="40" fill="transparent" stroke="rgba(255,255,255,0.04)" strokeWidth="6" />
                          <circle cx="50" cy="50" r="40" fill="transparent" stroke="#ef4444" strokeWidth="6" strokeDasharray="251" strokeDashoffset="210" />
                        </svg>
                        <div className="absolute text-center">
                          <p className="text-xs font-bold text-red-400">FALSE</p>
                          <p className="text-xl font-extrabold font-display text-white">16%</p>
                          <p className="text-[9px] text-white/30">Trust Score</p>
                        </div>
                      </div>
                      <p className="text-xs text-white/50 text-center font-medium">Manipulated Fact Combination</p>
                    </div>

                    {/* Right: Explanations & Sources */}
                    <div className="space-y-4">
                      <div className="space-y-1">
                        <span className="text-[10px] font-semibold text-sky-400 uppercase tracking-widest">AI Verdict Summary</span>
                        <p className="text-xs text-white/75 leading-relaxed">
                          Semantic matching identifies that quantum cracks on active block chain keys have not occurred. Peer-reviewed studies confirm current encryption remains unbroken by current models.
                        </p>
                      </div>
                      <div className="space-y-2">
                        <span className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">Linked Counter-Evidence</span>
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-2 text-[11px] text-white/50 bg-white/5 p-2 rounded-lg border border-white/5">
                            <Info className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                            <span>NIST Cryptography Consensus 2026</span>
                            <span className="text-[9px] text-emerald-400 font-bold ml-auto">98% CRED</span>
                          </div>
                          <div className="flex items-center gap-2 text-[11px] text-white/50 bg-white/5 p-2 rounded-lg border border-white/5">
                            <Info className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                            <span>IEEE Security & Privacy Journal 2025</span>
                            <span className="text-[9px] text-emerald-400 font-bold ml-auto">96% CRED</span>
                          </div>
                        </div>
                      </div>
                      <div className="pt-2">
                        <button
                          onClick={handleResetDemo}
                          className="btn-secondary text-[11px] py-1.5 px-4"
                        >
                          Verify Another
                        </button>
                      </div>
                    </div>
                  </motion.div>
                )}

              </AnimatePresence>
            </div>

            </motion.div>
          </InteractiveCard>
        </div>
      </section>

      {/* ════════ BENTO GRID FEATURES ════════ */}
      <section className="relative py-24 px-4">
        <div className="max-w-6xl mx-auto space-y-16">
          <div className="text-center space-y-4">
            <span className="section-label">Capabilities</span>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold font-display tracking-tight text-white leading-none">
              Arctic Security Infrastructure
            </h2>
            <p className="text-sm text-white/40 max-w-lg mx-auto">
              Precision built components that safeguard fact credibility, analyze media parameters, and block threat actors.
            </p>
          </div>

          {/* Bento grid layout */}
          <div className="bento-grid">
            <InteractiveCard className="border border-white/5 bg-[#030712]/40 backdrop-blur-xl">
              <div className="p-8 space-y-4">
                <div className="w-10 h-10 rounded-xl bg-sky-500/10 flex items-center justify-center">
                  <Brain className="w-5 h-5 text-sky-400" />
                </div>
                <h3 className="text-lg font-bold text-white">Multimodal Parsing</h3>
                <p className="text-xs text-white/50 leading-relaxed">
                  Seamless ingestion of audio files, deepfake video streams, complex text transcripts, and public domain urls.
                </p>
              </div>
            </InteractiveCard>

            <InteractiveCard className="border border-white/5 bg-[#030712]/40 backdrop-blur-xl bento-wide">
              <div className="p-8 space-y-4">
                <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
                  <Database className="w-5 h-5 text-purple-400" />
                </div>
                <h3 className="text-lg font-bold text-white">Semantic pgvector Matching</h3>
                <p className="text-xs text-white/50 leading-relaxed">
                  Connects directly to verified fact clusters, indexing context-heavy records in sub-second speeds using vectorized embeddings.
                </p>
              </div>
            </InteractiveCard>

            <InteractiveCard className="border border-white/5 bg-[#030712]/40 backdrop-blur-xl bento-wide">
              <div className="p-8 space-y-4">
                <div className="w-10 h-10 rounded-xl bg-cyan-500/10 flex items-center justify-center">
                  <Globe className="w-5 h-5 text-cyan-400" />
                </div>
                <h3 className="text-lg font-bold text-white">Global Threat Hotspots</h3>
                <p className="text-xs text-white/50 leading-relaxed">
                  Maps geographic vectors of disinformation in real-time. Detect coordinated bot networks and virality surges before they go viral.
                </p>
              </div>
            </InteractiveCard>

            <InteractiveCard className="border border-white/5 bg-[#030712]/40 backdrop-blur-xl">
              <div className="p-8 space-y-4">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                  <ShieldCheck className="w-5 h-5 text-emerald-400" />
                </div>
                <h3 className="text-lg font-bold text-white">Audit Trails</h3>
                <p className="text-xs text-white/50 leading-relaxed">
                  Maintains a fully cryptographically secure record of workspace activities, ensuring SOC2-ready accountability.
                </p>
              </div>
            </InteractiveCard>
          </div>
        </div>
      </section>

      {/* ════════ AI ARCHITECTURE / PIPELINE ════════ */}
      <section className="relative py-24 px-4 border-t border-white/5 bg-white/[0.005]">
        <div className="max-w-4xl mx-auto space-y-12 text-center">
          <div className="space-y-4">
            <span className="section-label">AI Architecture</span>
            <h2 className="text-3xl sm:text-4xl font-bold font-display text-white">
              The 5-Stage Verification Core
            </h2>
          </div>

          <div className="grid md:grid-cols-5 gap-4">
            {[
              { num: '01', title: 'Ingestion', desc: 'Accept text, file bytes or URL metadata.', color: 'border-sky-500/20 text-sky-400' },
              { num: '02', title: 'Extraction', desc: 'Identify claims, entities, and voice clones.', color: 'border-cyan-500/20 text-cyan-400' },
              { num: '03', title: 'Verification', desc: 'Query pgvector facts for matching evidence.', color: 'border-indigo-500/20 text-indigo-400' },
              { num: '04', title: 'Scoring', desc: 'Aggregate results into trust percentages.', color: 'border-purple-500/20 text-purple-400' },
              { num: '05', title: 'Reporting', desc: 'Output explainable briefings and counter-facts.', color: 'border-pink-500/20 text-pink-400' },
            ].map(stage => (
              <div key={stage.num} className={`glass-card p-5 space-y-3 border ${stage.color}`}>
                <div className="text-2xl font-bold font-mono">{stage.num}</div>
                <h4 className="text-sm font-bold text-white">{stage.title}</h4>
                <p className="text-[10px] text-white/40 leading-relaxed">{stage.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════ TESTIMONIALS SECTION ════════ */}
      <section className="relative py-24 px-4">
        <div className="max-w-5xl mx-auto space-y-12">
          <div className="text-center space-y-3">
            <span className="section-label">Audited Trust</span>
            <h2 className="text-3xl font-bold font-display text-white">What Intelligence Teams Say</h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {[
              { quote: 'TruthShield transformed how we verify active press streams. The pgvector RAG works at speeds typical databases cannot match.', author: 'Director of Intelligence', org: 'Cyber Defense Center' },
              { quote: 'The deepfake audio mapping and spectral analysis saved our PR teams hours of manual verification. Essential product.', author: 'Chief Information Officer', org: 'Nexus Global Media' },
              { quote: 'Onboarding our regional analyst teams was seamless. RBAC workspaces are clean, secure, and compliant.', author: 'SecOps Architect', org: 'Arctic Intelligence Hub' },
            ].map((test, idx) => (
              <div key={idx} className="glass-card p-6 flex flex-col justify-between space-y-6">
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map(s => <Star key={s} className="w-3.5 h-3.5 fill-sky-400 text-sky-400" />)}
                </div>
                <p className="text-xs text-white/70 leading-relaxed italic font-medium">"{test.quote}"</p>
                <div>
                  <p className="text-xs font-bold text-white">{test.author}</p>
                  <p className="text-[10px] text-white/30 uppercase mt-0.5">{test.org}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════ PRICING SECTION ════════ */}
      <section className="relative py-24 px-4 border-t border-white/5 bg-white/[0.005]">
        <div className="max-w-5xl mx-auto space-y-12">
          <div className="text-center space-y-3">
            <span className="section-label">Pricing Tiers</span>
            <h2 className="text-3xl font-bold font-display text-white">Predictable Enterprise Pricing</h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto items-stretch">
            {[
              { plan: 'Developer', price: '$0', desc: 'Test pipeline integrations and run basic claim scans.', features: ['100 scans / month', 'Text & Web URL analysis', 'Basic API access', 'Community support'] },
              { plan: 'Professional', price: '$149', desc: 'Deploy automated NLP systems and analyze large media uploads.', features: ['5,000 scans / month', 'Multimodal (Image/Audio/Video)', 'Advanced pgvector RAG', 'Standard API Keys', 'Priority SecOps support'], highlighted: true },
              { plan: 'Enterprise', price: 'Custom', desc: 'Scale threat verification with dedicated servers & custom databases.', features: ['Unlimited scans', 'Dedicated RAG fact cluster', 'Custom LLM fine-tuning', 'Full audit logs & RBAC', '99.9% uptime SLA'] },
            ].map(tier => (
              <InteractiveCard
                key={tier.plan}
                className={`border bg-[#030712]/40 backdrop-blur-xl ${tier.highlighted ? 'border-sky-400/40 bg-sky-500/[0.02]' : 'border-white/5'}`}
                tiltIntensity={10}
              >
                <div className="p-8 flex flex-col justify-between space-y-8 h-full relative overflow-hidden">
                  {tier.highlighted && (
                    <div className="absolute top-0 right-0 bg-sky-400 text-slate-950 font-bold text-[9px] uppercase px-3 py-1 rounded-bl-lg">
                      Recommended
                    </div>
                  )}
                  <div className="space-y-4">
                    <h4 className="text-lg font-bold text-white">{tier.plan}</h4>
                    <div className="flex items-baseline gap-1">
                      <span className="text-4xl font-extrabold text-white">{tier.price}</span>
                      {tier.price !== 'Custom' && <span className="text-xs text-white/30">/mo</span>}
                    </div>
                    <p className="text-xs text-white/40 leading-relaxed">{tier.desc}</p>
                  </div>

                  <div className="border-t border-white/5 pt-6 space-y-3 flex-1">
                    {tier.features.map(f => (
                      <div key={f} className="flex items-center gap-2 text-xs text-white/70">
                        <Check className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                        <span>{f}</span>
                      </div>
                    ))}
                  </div>

                  <button className={`w-full text-xs font-semibold py-2.5 rounded-xl transition-all ${tier.highlighted ? 'btn-primary' : 'btn-secondary'}`}>
                    Get Started
                  </button>
                </div>
              </InteractiveCard>
            ))}
          </div>
        </div>
      </section>

      {/* ════════ CALL TO ACTION ════════ */}
      <section className="relative py-24 px-4">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="glass-card p-12 text-center relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-sky-500/5 via-transparent to-purple-500/5" />
            <div className="relative z-10 space-y-6">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-sky-500 to-indigo-500 flex items-center justify-center mx-auto shadow-lg shadow-sky-500/20">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <h2 className="text-3xl font-bold font-display text-white">Join the TruthShield Network</h2>
              <p className="text-xs sm:text-sm text-white/40 max-w-md mx-auto leading-relaxed">
                Connect your media rooms and intelligence divisions to our low-latency validation clusters today.
              </p>
              <div className="flex justify-center gap-4">
                <Link to="/login" className="btn-primary text-xs py-2 px-6">
                  Create Free Account
                </Link>
                <Link to="/login" className="btn-secondary text-xs py-2 px-6">
                  Contact Sales
                </Link>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ════════ FOOTER ════════ */}
      <footer className="border-t border-white/5 py-12 px-4 bg-[#020617]">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6 text-center md:text-left">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-sky-500 to-cyan-500 flex items-center justify-center">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold font-display text-white">TruthShield</span>
          </div>
          
          <div className="flex flex-wrap justify-center gap-6 text-xs text-white/30">
            <span className="hover:text-white/60 cursor-pointer">Security Suite</span>
            <span className="hover:text-white/60 cursor-pointer">API Integration</span>
            <span className="hover:text-white/60 cursor-pointer">Fact Check Database</span>
            <span className="hover:text-white/60 cursor-pointer">Compliance</span>
          </div>

          <div className="flex items-center gap-2 text-[10px] text-white/20">
            <span>© 2026 TruthShield Inc.</span>
            <span>·</span>
            <span>All systems operational</span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          </div>
        </div>
      </footer>

    </div>
  );
}
