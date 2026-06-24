import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useTranslation } from 'react-i18next';
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
  const { t, i18n } = useTranslation();
  const [activeTab, setActiveTab] = useState('text');
  const [inputText, setInputText] = useState("Breaking: Scientific journal claims quantum computer model completely cracks standard blockchain encryption keys.");

  useEffect(() => {
    if (i18n.language === 'hi') {
      setInputText("ताज़ा खबर: वैज्ञानिक पत्रिका का दावा है कि क्वांटम कंप्यूटर मॉडल मानक ब्लॉकचेन एन्क्रिप्शन कुंजी को पूरी तरह से क्रैक कर देता है।");
    } else if (i18n.language === 'ta') {
      setInputText("முக்கிய செய்தி: குவாண்டம் கணினி மாதிரி நிலையான பிளாக்செயின் குறியாக்க விசைகளை முற்றிலும் உடைக்கிறது என்று அறிவியல் இதழ் கூறுகிறது.");
    } else {
      setInputText("Breaking: Scientific journal claims quantum computer model completely cracks standard blockchain encryption keys.");
    }
  }, [i18n.language]);
  const [demoState, setDemoState] = useState('idle'); // idle | processing | result
  const [currentDemoStage, setCurrentDemoStage] = useState(0);

  const demoStages = [
    t('landing.stage_0') || 'Decompressing and segmenting file streams...',
    t('landing.stage_1') || 'Extracting metadata, source structures & claim vectors...',
    t('landing.stage_2') || 'Cross-referencing global credibility consensus databases...',
    t('landing.stage_3') || 'Performing cross-signal sentiment & semantic consistency runs...',
    t('landing.stage_4') || 'Synthesizing ultimate fact verdict & counter-narrative...'
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
              <span className="text-[10px] font-bold uppercase tracking-wider text-sky-300">{t('landing.hero_badge')}</span>
            </motion.div>

            {/* Giant Title */}
            <motion.h1
              initial={{ opacity: 0, y: 25 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="text-5xl sm:text-6xl lg:text-7xl font-bold font-display tracking-tight leading-[1.05] text-white"
            >
              {t('landing.hero_title_1')} <br/>
              <span className="gradient-text-hero electric-text">{t('landing.hero_title_2')}</span>
            </motion.h1>

            {/* Subheadline */}
            <motion.p
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="text-base sm:text-lg text-white/50 max-w-xl leading-relaxed font-sans text-balance"
            >
              {t('landing.hero_subtitle')}
            </motion.p>

            {/* CTAs */}
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3 }}
              className="flex flex-wrap items-center gap-4 pt-2"
            >
              <Link to="/login" className="btn-primary-lg flex items-center gap-2 group text-sm">
                {t('landing.btn_start')}
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </Link>
              <a href="#demo" className="btn-secondary-lg flex items-center gap-2 text-sm">
                <Play className="w-4 h-4 text-sky-400 fill-sky-400/20" />
                {t('landing.btn_demo')}
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
                { val: '2.1M+', label: t('landing.claims_analyzed') },
                { val: '99.4%', label: t('landing.audited_accuracy') },
                { val: '0.4s', label: t('landing.inference_velocity') },
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
            <span className="section-label">{t('landing.interactive_experience')}</span>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold font-display tracking-tight text-white leading-none">
              {t('landing.demo_title')}
            </h2>
            <p className="text-sm sm:text-base text-white/45 max-w-lg mx-auto">
              {t('landing.demo_subtitle')}
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
                      <label className="text-xs font-semibold text-white/40 uppercase tracking-widest">{t('landing.demo_label')}</label>
                      <textarea
                        value={inputText}
                        onChange={(e) => setInputText(e.target.value)}
                        className="input-field h-24 text-sm font-sans"
                        placeholder={t('analyze.text_placeholder')}
                      />
                    </div>
                    <div className="flex justify-between items-center">
                      <div className="flex gap-3 text-xs text-white/30">
                        <span>{t('landing.nlp_model')}</span>
                        <span>{t('landing.rag_active')}</span>
                      </div>
                      <button
                        onClick={handleRunDemo}
                        className="btn-primary flex items-center gap-2 text-xs py-2 px-5"
                      >
                        {t('landing.demo_btn_run')}
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
                      <p className="text-sm font-semibold text-white/70">{t('landing.processing_claim')}</p>
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
                      <span className="text-[10px] font-bold text-white/40 uppercase tracking-widest mb-4">{t('landing.demo_verdict')}</span>
                      
                      <div className="relative w-32 h-32 flex items-center justify-center mb-4">
                        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                          <circle cx="50" cy="50" r="40" fill="transparent" stroke="rgba(255,255,255,0.04)" strokeWidth="6" />
                          <circle cx="50" cy="50" r="40" fill="transparent" stroke="#ef4444" strokeWidth="6" strokeDasharray="251" strokeDashoffset="210" />
                        </svg>
                        <div className="absolute text-center">
                          <p className="text-xs font-bold text-red-400">{t('verdicts.FALSE')}</p>
                          <p className="text-xl font-extrabold font-display text-white">16%</p>
                          <p className="text-[9px] text-white/30">{t('report.trust_score')}</p>
                        </div>
                      </div>
                      <p className="text-xs text-white/50 text-center font-medium">{t('landing.manipulated_combination')}</p>
                    </div>

                    {/* Right: Explanations & Sources */}
                    <div className="space-y-4">
                      <div className="space-y-1">
                        <span className="text-[10px] font-semibold text-sky-400 uppercase tracking-widest">{t('landing.demo_verdict_summary')}</span>
                        <p className="text-xs text-white/75 leading-relaxed">
                          {t('landing.demo_summary_desc')}
                        </p>
                      </div>
                      <div className="space-y-2">
                        <span className="text-[10px] font-semibold text-white/40 uppercase tracking-widest">{t('landing.demo_evidence')}</span>
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
                        <button onClick={handleResetDemo} className="btn-secondary text-[11px] py-1.5 px-4">
                          {t('landing.demo_btn_another')}
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
            <span className="section-label">{t('landing.bento_badge')}</span>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold font-display tracking-tight text-white leading-none">
              {t('landing.bento_title')}
            </h2>
            <p className="text-sm text-white/40 max-w-lg mx-auto">
              {t('landing.bento_subtitle')}
            </p>
          </div>

          {/* Bento grid layout */}
          <div className="bento-grid">
            <InteractiveCard className="border border-white/5 bg-[#030712]/40 backdrop-blur-xl">
              <div className="p-8 space-y-4">
                <div className="w-10 h-10 rounded-xl bg-sky-500/10 flex items-center justify-center">
                  <Brain className="w-5 h-5 text-sky-400" />
                </div>
                <h3 className="text-lg font-bold text-white">{t('landing.bento_multimodal')}</h3>
                <p className="text-xs text-white/50 leading-relaxed">
                  {t('landing.bento_multimodal_desc')}
                </p>
              </div>
            </InteractiveCard>

            <InteractiveCard className="border border-white/5 bg-[#030712]/40 backdrop-blur-xl bento-wide">
              <div className="p-8 space-y-4">
                <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
                  <Database className="w-5 h-5 text-purple-400" />
                </div>
                <h3 className="text-lg font-bold text-white">{t('landing.bento_rag')}</h3>
                <p className="text-xs text-white/50 leading-relaxed">
                  {t('landing.bento_rag_desc')}
                </p>
              </div>
            </InteractiveCard>

            <InteractiveCard className="border border-white/5 bg-[#030712]/40 backdrop-blur-xl bento-wide">
              <div className="p-8 space-y-4">
                <div className="w-10 h-10 rounded-xl bg-cyan-500/10 flex items-center justify-center">
                  <Globe className="w-5 h-5 text-cyan-400" />
                </div>
                <h3 className="text-lg font-bold text-white">{t('landing.bento_hotspots')}</h3>
                <p className="text-xs text-white/50 leading-relaxed">
                  {t('landing.bento_hotspots_desc')}
                </p>
              </div>
            </InteractiveCard>

            <InteractiveCard className="border border-white/5 bg-[#030712]/40 backdrop-blur-xl">
              <div className="p-8 space-y-4">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                  <ShieldCheck className="w-5 h-5 text-emerald-400" />
                </div>
                <h3 className="text-lg font-bold text-white">{t('landing.bento_audit')}</h3>
                <p className="text-xs text-white/50 leading-relaxed">
                  {t('landing.bento_audit_desc')}
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
            <span className="section-label">{t('landing.pipeline_badge')}</span>
            <h2 className="text-3xl sm:text-4xl font-bold font-display text-white">
              {t('landing.pipeline_title')}
            </h2>
          </div>

          <div className="grid md:grid-cols-5 gap-4">
            {[
              { num: '01', title: t('landing.stage_title_0'), desc: t('landing.stage_desc_0'), color: 'border-sky-500/20 text-sky-400' },
              { num: '02', title: t('landing.stage_title_1'), desc: t('landing.stage_desc_1'), color: 'border-cyan-500/20 text-cyan-400' },
              { num: '03', title: t('landing.stage_title_2'), desc: t('landing.stage_desc_2'), color: 'border-indigo-500/20 text-indigo-400' },
              { num: '04', title: t('landing.stage_title_3'), desc: t('landing.stage_desc_3'), color: 'border-purple-500/20 text-purple-400' },
              { num: '05', title: t('landing.stage_title_4'), desc: t('landing.stage_desc_4'), color: 'border-pink-500/20 text-pink-400' },
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
            <span className="section-label">{t('landing.testimonials_badge')}</span>
            <h2 className="text-3xl font-bold font-display text-white">{t('landing.testimonials_title')}</h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {[
              { quote: t('landing.testimonial_quote_0'), author: t('landing.testimonial_author_0'), org: t('landing.testimonial_org_0') },
              { quote: t('landing.testimonial_quote_1'), author: t('landing.testimonial_author_1'), org: t('landing.testimonial_org_1') },
              { quote: t('landing.testimonial_quote_2'), author: t('landing.testimonial_author_2'), org: t('landing.testimonial_org_2') },
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
            <span className="section-label">{t('landing.pricing_badge')}</span>
            <h2 className="text-3xl font-bold font-display text-white">{t('landing.pricing_title')}</h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto items-stretch">
            {[
              { plan: 'Developer', price: '$0', desc: t('landing.pricing_dev_desc'), features: [t('landing.pricing_feature_0'), t('landing.pricing_feature_1'), t('landing.pricing_feature_2'), t('landing.pricing_feature_3')] },
              { plan: 'Professional', price: '$149', desc: t('landing.pricing_pro_desc'), features: [t('landing.pricing_feature_4'), t('landing.pricing_feature_5'), t('landing.pricing_feature_6'), t('landing.pricing_feature_7'), t('landing.pricing_feature_8')], highlighted: true },
              { plan: 'Enterprise', price: t('landing.pricing_custom'), desc: t('landing.pricing_ent_desc'), features: [t('landing.pricing_feature_9'), t('landing.pricing_feature_10'), t('landing.pricing_feature_11'), t('landing.pricing_feature_12'), t('landing.pricing_feature_13')] },
            ].map(tier => (
              <InteractiveCard
                key={tier.plan}
                className={`border bg-[#030712]/40 backdrop-blur-xl ${tier.highlighted ? 'border-sky-400/40 bg-sky-500/[0.02]' : 'border-white/5'}`}
                tiltIntensity={10}
              >
                <div className="p-8 flex flex-col justify-between space-y-8 h-full relative overflow-hidden">
                  {tier.highlighted && (
                    <div className="absolute top-0 right-0 bg-sky-400 text-slate-950 font-bold text-[9px] uppercase px-3 py-1 rounded-bl-lg">
                      {t('landing.pricing_recommended')}
                    </div>
                  )}
                  <div className="space-y-4">
                    <h4 className="text-lg font-bold text-white">{tier.plan}</h4>
                    <div className="flex items-baseline gap-1">
                      <span className="text-4xl font-extrabold text-white">{tier.price}</span>
                      {tier.price !== t('landing.pricing_custom') && <span className="text-xs text-white/30">{t('landing.pricing_mo')}</span>}
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
                    {t('landing.pricing_btn_start')}
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
              <h2 className="text-3xl font-bold font-display text-white">{t('landing.cta_title')}</h2>
              <p className="text-xs sm:text-sm text-white/40 max-w-md mx-auto leading-relaxed">
                {t('landing.cta_desc')}
              </p>
              <div className="flex justify-center gap-4">
                <Link to="/login" className="btn-primary text-xs py-2 px-6">
                  {t('landing.cta_btn_free')}
                </Link>
                <Link to="/login" className="btn-secondary text-xs py-2 px-6">
                  {t('landing.cta_btn_sales')}
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
            <span className="font-bold font-display text-white">{t('app_name')}</span>
          </div>
          
          <div className="flex flex-wrap justify-center gap-6 text-xs text-white/30">
            <span className="hover:text-white/60 cursor-pointer">{t('landing.footer_link_suite')}</span>
            <span className="hover:text-white/60 cursor-pointer">{t('landing.footer_link_api')}</span>
            <span className="hover:text-white/60 cursor-pointer">{t('landing.footer_link_db')}</span>
            <span className="hover:text-white/60 cursor-pointer">{t('landing.footer_link_compliance')}</span>
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
