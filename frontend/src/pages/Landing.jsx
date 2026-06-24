import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import InteractiveCard from '../components/InteractiveCard';

import { 
  Shield, Zap, Globe, Users, Lock, Brain, 
  ArrowRight, CheckCircle2, Sparkles, Eye, 
  FileSearch, BarChart3, ChevronRight, Play,
  ShieldCheck, Cpu, Database, Fingerprint, Star,
  Check, Info, MessageSquare, Terminal, Heart,
  Settings, PlayCircle, Layers, Radio, Network, GitMerge, FileText, AlertTriangle, RefreshCw,
  Plus, Trash2, X, Sliders, PlaySquare, FileCode
} from 'lucide-react';

/* ─────────── 3D-Like Rotating Cyber Sphere ─────────── */
function IntelligenceSphere() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;
    let angleX = 0.002;
    let angleY = 0.0025;
    
    // Create points on a sphere
    const points = [];
    const numPoints = 120;
    const radius = 100;

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
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      return { x: p.x, y: p.y * cos - p.z * sin, z: p.y * sin + p.z * cos };
    };

    const rotateY = (p, angle) => {
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      return { x: p.x * cos + p.z * sin, y: p.y, z: -p.x * sin + p.z * cos };
    };

    const draw = () => {
      const w = canvas.offsetWidth;
      const h = canvas.offsetHeight;
      if (w === 0 || h === 0) return;
      ctx.clearRect(0, 0, w, h);
      ctx.translate(w / 2, h / 2);

      // Rotate and project points
      const projected = points.map(p => {
        const p1 = rotateX(p, angleX);
        const p2 = rotateY(p1, angleY);
        
        p.x = p2.x;
        p.y = p2.y;
        p.z = p2.z;

        const fov = 300;
        const scale = fov / (fov + p2.z);
        return {
          x: p2.x * scale,
          y: p2.y * scale,
          z: p2.z,
          opacity: (p2.z + radius) / (radius * 2) * 0.5 + 0.2
        };
      });

      // Draw connections
      ctx.lineWidth = 0.5;
      for (let i = 0; i < projected.length; i += 4) {
        const p1 = projected[i];
        for (let j = i + 1; j < projected.length; j += 12) {
          const p2 = projected[j];
          const dist = Math.hypot(p1.x - p2.x, p1.y - p2.y);
          if (dist < 60) {
            ctx.beginPath();
            ctx.strokeStyle = `rgba(255, 23, 68, ${p1.opacity * 0.12 * (1 - dist / 60)})`;
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
      }

      // Draw nodes
      projected.forEach(p => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.max(1, (p.z + radius) / radius * 2), 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 23, 68, ${p.opacity * 0.8})`;
        ctx.fill();

        if (p.z > 50) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, 0.5, 0, Math.PI * 2);
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

  return <canvas ref={canvasRef} className="w-full h-full max-w-[340px] max-h-[340px] mx-auto aspect-square" />;
}

/* ─────────── Landing Page ─────────── */
export default function Landing() {
  const navigate = useNavigate();

  // Stats Counters
  const [scansCount, setScansCount] = useState(142385);
  const [threatsCount, setThreatsCount] = useState(8394);

  useEffect(() => {
    const interval = setInterval(() => {
      setScansCount(c => c + Math.floor(Math.random() * 3) + 1);
      if (Math.random() > 0.7) {
        setThreatsCount(t => t + 1);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  // ════════ INTERACTIVE WORKFLOW STATES (n8n style) ════════
  const [nodes, setNodes] = useState([
    { id: 'trigger', type: 'trigger', label: 'Ingestion Trigger', x: 40, y: 140, config: { source: 'Claim Form Input', claim: 'Bleach cures COVID-19' } },
    { id: 'extractor', type: 'extractor', label: 'Claim Extractor', x: 230, y: 140, config: { model: 'Gemini-2.0-Flash', language: 'en' } },
    { id: 'search', type: 'search', label: 'Evidence Retriever', x: 420, y: 140, config: { engine: 'Brave Search API', maxResults: 5 } },
    { id: 'verdict', type: 'verdict', label: 'Verdict Engine', x: 610, y: 140, config: { threshold: 75, factCheckWeight: 40, webConsensusWeight: 25 } }
  ]);

  const [connections, setConnections] = useState([
    { from: 'trigger', to: 'extractor' },
    { from: 'extractor', to: 'search' },
    { from: 'search', to: 'verdict' }
  ]);

  const [selectedNodeId, setSelectedNodeId] = useState('trigger');
  const [draggingNodeId, setDraggingNodeId] = useState(null);
  const [execState, setExecState] = useState('idle'); // idle | running | finished
  const [activeNodeId, setActiveNodeId] = useState(null);
  const [completedNodeIds, setCompletedNodeIds] = useState([]);
  const [logEntries, setLogEntries] = useState([]);
  const [pulsePosition, setPulsePosition] = useState(0); // 0 to 1 progress along lines
  
  const dragOffset = useRef({ x: 0, y: 0 });
  const canvasRef = useRef(null);

  // Drag handlers
  const handleNodeMouseDown = (e, nodeId) => {
    if (execState === 'running') return;
    e.stopPropagation();
    setSelectedNodeId(nodeId);
    setDraggingNodeId(nodeId);
    const node = nodes.find(n => n.id === nodeId);
    if (node && canvasRef.current) {
      const rect = canvasRef.current.getBoundingClientRect();
      dragOffset.current = {
        x: (e.clientX - rect.left) - node.x,
        y: (e.clientY - rect.top) - node.y
      };
    }
  };

  const handleCanvasMouseMove = (e) => {
    if (!draggingNodeId || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const newX = (e.clientX - rect.left) - dragOffset.current.x;
    const newY = (e.clientY - rect.top) - dragOffset.current.y;

    // Boundaries inside 800x400 canvas
    const boundX = Math.max(10, Math.min(rect.width - 150, newX));
    const boundY = Math.max(10, Math.min(rect.height - 90, newY));

    setNodes(prev => prev.map(n => n.id === draggingNodeId ? { ...n, x: boundX, y: boundY } : n));
  };

  const handleCanvasMouseUp = () => {
    setDraggingNodeId(null);
  };

  // Node Actions (Add / Delete)
  const addNode = (type) => {
    if (nodes.length >= 8) {
      alert("Maximum node count reached for this simulation.");
      return;
    }
    const id = `${type}_${Math.floor(Math.random() * 1000)}`;
    let label = 'New Node';
    let config = {};

    switch (type) {
      case 'slack':
        label = 'Slack Notification';
        config = { channel: '#threat-alerts', format: 'JSON Block' };
        break;
      case 'email':
        label = 'Email Dispatcher';
        config = { recipient: 'security@firm.com', priority: 'HIGH' };
        break;
      case 'discord':
        label = 'Discord Alert';
        config = { webhookUrl: 'https://discord.com/api/...', tagEveryone: false };
        break;
      case 'db_sync':
        label = 'Database Sync';
        config = { table: 'audit_logs', retentionDays: 90 };
        break;
    }

    const lastNode = nodes[nodes.length - 1];
    const newX = lastNode ? Math.min(700, lastNode.x + 130) : 100;
    const newY = lastNode ? Math.min(300, lastNode.y + 40) : 150;

    const newNode = { id, type, label, x: newX, y: newY, config };
    setNodes(prev => [...prev, newNode]);

    if (lastNode) {
      setConnections(prev => [...prev, { from: lastNode.id, to: id }]);
    }
    setSelectedNodeId(id);
    setLogEntries(prev => [...prev, `[CANVAS] Appended node: ${label}`]);
  };

  const deleteNode = (nodeId) => {
    if (nodes.length <= 2) {
      alert("At least 2 nodes are required for verification flow.");
      return;
    }
    setNodes(prev => prev.filter(n => n.id !== nodeId));
    setConnections(prev => prev.filter(c => c.from !== nodeId && c.to !== nodeId));
    if (selectedNodeId === nodeId) {
      setSelectedNodeId(nodes.find(n => n.id !== nodeId)?.id || '');
    }
    setLogEntries(prev => [...prev, `[CANVAS] Removed node ID: ${nodeId}`]);
  };

  // Node Property Editing
  const updateNodeConfig = (nodeId, key, value) => {
    setNodes(prev => prev.map(n => {
      if (n.id === nodeId) {
        return {
          ...n,
          config: {
            ...n.config,
            [key]: value
          }
        };
      }
      return n;
    }));
  };

  // Load Presets
  const applyPreset = (presetName) => {
    resetWorkflow();
    if (presetName === 'standard') {
      setNodes([
        { id: 'trigger', type: 'trigger', label: 'Ingestion Trigger', x: 40, y: 140, config: { source: 'Claim Form Input', claim: 'Bleach cures COVID-19' } },
        { id: 'extractor', type: 'extractor', label: 'Claim Extractor', x: 230, y: 140, config: { model: 'Gemini-2.0-Flash', language: 'en' } },
        { id: 'search', type: 'search', label: 'Evidence Retriever', x: 420, y: 140, config: { engine: 'Brave Search API', maxResults: 5 } },
        { id: 'verdict', type: 'verdict', label: 'Verdict Engine', x: 610, y: 140, config: { threshold: 75, factCheckWeight: 40, webConsensusWeight: 25 } }
      ]);
      setConnections([
        { from: 'trigger', to: 'extractor' },
        { from: 'extractor', to: 'search' },
        { from: 'search', to: 'verdict' }
      ]);
      setSelectedNodeId('trigger');
    } else if (presetName === 'alert') {
      setNodes([
        { id: 'trigger', type: 'trigger', label: 'Ingestion Trigger', x: 30, y: 140, config: { source: 'Security Webhook', claim: 'Ransomware threat at server 2' } },
        { id: 'extractor', type: 'extractor', label: 'Extractor Node', x: 190, y: 140, config: { model: 'Gemini-1.5-Pro', language: 'en' } },
        { id: 'verdict', type: 'verdict', label: 'Verdict Synthesizer', x: 350, y: 140, config: { threshold: 60, factCheckWeight: 30, webConsensusWeight: 30 } },
        { id: 'slack_alert', type: 'slack', label: 'Slack Alert Dispatch', x: 510, y: 80, config: { channel: '#security-ops', format: 'Text Block' } },
        { id: 'discord_alert', type: 'discord', label: 'Discord Dispatch', x: 510, y: 220, config: { webhookUrl: 'https://discord.com/api/...', tagEveryone: true } }
      ]);
      setConnections([
        { from: 'trigger', to: 'extractor' },
        { from: 'extractor', to: 'verdict' },
        { from: 'verdict', to: 'slack_alert' },
        { from: 'verdict', to: 'discord_alert' }
      ]);
      setSelectedNodeId('trigger');
    } else if (presetName === 'db') {
      setNodes([
        { id: 'trigger', type: 'trigger', label: 'API Ingest API', x: 40, y: 140, config: { source: 'REST API Gateway', claim: 'COVID vaccination contains microchips' } },
        { id: 'search', type: 'search', label: 'Evidence Crawler', x: 230, y: 140, config: { engine: 'Google CSE API', maxResults: 8 } },
        { id: 'verdict', type: 'verdict', label: 'Verdict Engine', x: 420, y: 140, config: { threshold: 80, factCheckWeight: 50, webConsensusWeight: 10 } },
        { id: 'db_sync', type: 'db_sync', label: 'Database Archiver', x: 610, y: 140, config: { table: 'truthshield_scans', retentionDays: 120 } }
      ]);
      setConnections([
        { from: 'trigger', to: 'search' },
        { from: 'search', to: 'verdict' },
        { from: 'verdict', to: 'db_sync' }
      ]);
      setSelectedNodeId('trigger');
    }
  };

  // Workflow Simulator Engine
  const executeWorkflow = () => {
    if (execState === 'running') return;
    setExecState('running');
    setCompletedNodeIds([]);
    setLogEntries([]);
    setPulsePosition(0);

    const triggerNode = nodes.find(n => n.type === 'trigger');
    const claimToVerify = triggerNode?.config?.claim || 'Unknown payload';

    // Step sequences
    let stepIndex = 0;

    const runStep = () => {
      if (stepIndex >= nodes.length) {
        setExecState('finished');
        setActiveNodeId(null);
        return;
      }

      const node = nodes[stepIndex];
      setActiveNodeId(node.id);
      setLogEntries(prev => [...prev, `[SYSTEM] EXECUTING NODE: ${node.label} (${node.id.toUpperCase()})...`]);

      // Populate logs depending on node configuration
      setTimeout(() => {
        let nodeDetailsLog = `[DATA] Configuration processed successfully.`;
        if (node.type === 'trigger') {
          nodeDetailsLog = `[PAYLOAD] Ingested input from "${node.config.source}". Content: "${claimToVerify}"`;
        } else if (node.type === 'extractor') {
          nodeDetailsLog = `[NLP] Model "${node.config.model}" split payload into checkable factual vectors in [${node.config.language}].`;
        } else if (node.type === 'search') {
          nodeDetailsLog = `[CRAWLER] Triggered engine "${node.config.engine}". Retrieved ${node.config.maxResults} evidence references.`;
        } else if (node.type === 'verdict') {
          nodeDetailsLog = `[VERDICT] Checked consensus against threshold (${node.config.threshold}%). Synthesized stance score: 32%.`;
        } else if (node.type === 'slack') {
          nodeDetailsLog = `[ALERT] Pushed alert payload to Slack channel "${node.config.channel}" in ${node.config.format} format.`;
        } else if (node.type === 'discord') {
          nodeDetailsLog = `[ALERT] Dispatched Discord webhook notification. Alert tag everyone = ${node.config.tagEveryone ? 'TRUE' : 'FALSE'}.`;
        } else if (node.type === 'db_sync') {
          nodeDetailsLog = `[DATABASE] Synced scan audit logs to PostgreSQL table "${node.config.table}". Retention = ${node.config.retentionDays} days.`;
        } else if (node.type === 'email') {
          nodeDetailsLog = `[ALERT] Sent encrypted alert email report to "${node.config.recipient}". Priority = ${node.config.priority}.`;
        }

        setCompletedNodeIds(prev => [...prev, node.id]);
        setLogEntries(prev => [
          ...prev,
          `[SUCCESS] Node "${node.label}" completed execution successfully.`,
          nodeDetailsLog
        ]);

        stepIndex++;
        runStep();
      }, 1400);
    };

    runStep();
  };

  const resetWorkflow = () => {
    setExecState('idle');
    setActiveNodeId(null);
    setCompletedNodeIds([]);
    setLogEntries([]);
    setPulsePosition(0);
  };

  // SVG curved connector helper
  const drawPath = (c) => {
    const fromNode = nodes.find(n => n.id === c.from);
    const toNode = nodes.find(n => n.id === c.to);
    if (!fromNode || !toNode) return '';

    // Node is 144px wide (w-36), 84px high
    const startX = fromNode.x + 144;
    const startY = fromNode.y + 42;
    const endX = toNode.x;
    const endY = toNode.y + 42;

    const controlOffset = Math.max(40, Math.abs(endX - startX) * 0.4);
    const cp1x = startX + controlOffset;
    const cp1y = startY;
    const cp2x = endX - controlOffset;
    const cp2y = endY;

    return `M ${startX},${startY} C ${cp1x},${cp1y} ${cp2x},${cp2y} ${endX},${endY}`;
  };

  return (
    <div className="relative -mt-20 overflow-hidden bg-black text-white selection:bg-red-500/35">
      {/* Subtle Grid System */}
      <div className="absolute inset-0 bg-grid opacity-20 pointer-events-none z-0" />
      
      {/* ════════ HERO COMMAND CENTER ════════ */}
      <section className="relative min-h-screen flex items-center justify-center pt-28 pb-16 px-4 z-10">
        <div className="max-w-7xl mx-auto w-full grid lg:grid-cols-12 gap-12 items-center">
          
          {/* Hero left text */}
          <div className="lg:col-span-7 space-y-6 text-left">
            {/* Status badge */}
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-950/40 border border-red-500/25 shadow-[0_0_15px_rgba(255,23,68,0.05)]"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
              </span>
              <span className="text-[10px] font-bold uppercase tracking-widest text-red-400 font-display">SOC Core v3.0 Threat Engine</span>
            </motion.div>

            {/* Giant Title */}
            <motion.h1
              initial={{ opacity: 0, y: 25 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="text-5xl sm:text-6xl lg:text-7xl font-black font-display tracking-tight leading-[1.05]"
            >
              ORCHESTRATE <br/>
              <span className="gradient-text font-black font-display text-glow">AI TRUTH</span>
            </motion.h1>

            {/* Subheadline */}
            <motion.p
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="text-sm sm:text-base text-white/50 max-w-xl leading-relaxed font-sans"
            >
              Unify facts, automate threat mapping, and configure node-based ingestion pipelines. 
              The ultimate mission-critical cybersecurity system built for validating digital truth.
            </motion.p>

            {/* CTAs */}
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3 }}
              className="flex flex-wrap items-center gap-4 pt-2"
            >
              <Link to="/login" className="btn-primary flex items-center gap-2 text-xs font-bold tracking-widest px-6 py-3.5 uppercase rounded-xl shadow-[0_0_20px_rgba(255,23,68,0.2)]">
                Start Ingesting
                <ArrowRight className="w-4 h-4" />
              </Link>
              <a href="#simulator" className="btn-secondary flex items-center gap-2 text-xs font-bold tracking-widest px-6 py-3.5 uppercase rounded-xl">
                <PlayCircle className="w-4 h-4 text-red-500 animate-pulse" />
                Build Workflows
              </a>
            </motion.div>

            {/* Quick Metrics */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4 }}
              className="grid grid-cols-3 gap-6 pt-8 border-t border-white/[0.06] max-w-lg"
            >
              <div>
                <p className="text-xl font-bold font-display text-white font-mono">{scansCount.toLocaleString()}</p>
                <p className="text-[9px] text-white/35 uppercase tracking-widest mt-0.5">Automated Runs</p>
              </div>
              <div>
                <p className="text-xl font-bold font-display text-red-500 font-mono">{threatsCount.toLocaleString()}</p>
                <p className="text-[9px] text-white/35 uppercase tracking-widest mt-0.5">Threats Mitigated</p>
              </div>
              <div>
                <p className="text-xl font-bold font-display text-white font-mono">&lt; 0.3s</p>
                <p className="text-[9px] text-white/35 uppercase tracking-widest mt-0.5">Signal Latency</p>
              </div>
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
              <div className="absolute w-[360px] h-[360px] rounded-full border border-red-500/10 border-dashed animate-spin" style={{ animationDuration: '30s' }} />
              <div className="absolute w-[280px] h-[280px] rounded-full border border-red-950/20 animate-spin" style={{ animationDuration: '20s', animationDirection: 'reverse' }} />
              
              <IntelligenceSphere />
            </motion.div>
          </div>

        </div>
      </section>

      {/* ════════ INTERACTIVE WORKFLOW SIMULATOR (n8n Style) ════════ */}
      <section id="simulator" className="relative py-24 px-4 border-t border-white/5 bg-white/[0.01]">
        <div className="max-w-7xl mx-auto space-y-12">
          
          <div className="text-center space-y-3">
            <span className="text-[10px] font-bold text-red-500 uppercase tracking-[0.2em] font-display">Automation Workspace</span>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black font-display tracking-tight text-white leading-none">
              Deploy Visual Pipelines
            </h2>
            <p className="text-sm text-white/45 max-w-xl mx-auto">
              Build custom pipelines connecting ingestion triggers to AI models, evidence crawlers, and decision aggregates. Drag nodes, select templates, and edit settings in real-time.
            </p>
          </div>

          {/* Preset Template Selector */}
          <div className="flex flex-wrap items-center justify-center gap-3">
            <span className="text-[10px] font-bold uppercase tracking-widest text-white/40 mr-2 font-mono">Load Presets:</span>
            <button 
              onClick={() => applyPreset('standard')} 
              className="px-3.5 py-1.5 rounded-lg border border-red-500/25 bg-red-950/10 hover:bg-red-950/30 text-red-400 text-xs font-semibold"
            >
              Standard Audit
            </button>
            <button 
              onClick={() => applyPreset('alert')} 
              className="px-3.5 py-1.5 rounded-lg border border-white/10 bg-white/[0.02] hover:bg-white/[0.06] text-white/80 text-xs font-semibold"
            >
              Alert Engine
            </button>
            <button 
              onClick={() => applyPreset('db')} 
              className="px-3.5 py-1.5 rounded-lg border border-white/10 bg-white/[0.02] hover:bg-white/[0.06] text-white/80 text-xs font-semibold"
            >
              Database Archiver
            </button>
          </div>

          <InteractiveCard className="border border-red-500/10 shadow-2xl bg-black/80 backdrop-blur-xl rounded-3xl overflow-hidden min-h-[560px]">
            <div className="grid lg:grid-cols-12">
              
              {/* Left Canvas Panel (8 cols) */}
              <div 
                ref={canvasRef}
                onMouseMove={handleCanvasMouseMove}
                onMouseUp={handleCanvasMouseUp}
                className="lg:col-span-8 p-6 lg:p-8 border-b lg:border-b-0 lg:border-r border-white/5 relative min-h-[460px] overflow-hidden select-none"
              >
                {/* Dots background */}
                <div className="absolute inset-0 bg-[radial-gradient(#ffffff08_1px,transparent_1px)] [background-size:16px_16px] pointer-events-none" />

                {/* Top Control Bar */}
                <div className="relative z-20 flex items-center justify-between mb-6">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-red-500/20 flex items-center justify-center">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />
                    </span>
                    <span className="text-[10px] font-bold font-mono tracking-widest text-white/50">WORKFLOW_CANVAS_ACTIVE</span>
                  </div>

                  <div className="flex items-center gap-2">
                    {execState === 'running' ? (
                      <button disabled className="px-4 py-1.5 rounded-lg bg-red-950/20 border border-red-500/20 text-red-400 text-xs font-bold flex items-center gap-1.5">
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        Executing...
                      </button>
                    ) : (
                      <button onClick={executeWorkflow} className="px-4 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-lg shadow-red-500/20 hover:shadow-red-500/40 transition-all duration-300">
                        <Play className="w-3.5 h-3.5 fill-white" />
                        Test Workflow
                      </button>
                    )}
                    <button onClick={resetWorkflow} className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 hover:border-white/20 text-white/60 hover:text-white text-xs font-semibold">
                      Reset
                    </button>
                  </div>
                </div>

                {/* Node Palette Options */}
                <div className="relative z-20 flex flex-wrap items-center gap-2 mb-8 bg-white/[0.02] border border-white/[0.06] p-2.5 rounded-xl max-w-max">
                  <span className="text-[9px] font-bold font-mono text-white/40 uppercase px-2">Add Node:</span>
                  <button onClick={() => addNode('slack')} className="flex items-center gap-1 text-[10px] bg-red-950/20 border border-red-500/20 hover:bg-red-950/40 text-red-400 px-2.5 py-1 rounded-md font-semibold">
                    <Plus className="w-3 h-3" /> Slack Alert
                  </button>
                  <button onClick={() => addNode('discord')} className="flex items-center gap-1 text-[10px] bg-red-950/20 border border-red-500/20 hover:bg-red-950/40 text-red-400 px-2.5 py-1 rounded-md font-semibold">
                    <Plus className="w-3 h-3" /> Discord Alert
                  </button>
                  <button onClick={() => addNode('email')} className="flex items-center gap-1 text-[10px] bg-red-950/20 border border-red-500/20 hover:bg-red-950/40 text-red-400 px-2.5 py-1 rounded-md font-semibold">
                    <Plus className="w-3 h-3" /> Email Alert
                  </button>
                  <button onClick={() => addNode('db_sync')} className="flex items-center gap-1 text-[10px] bg-red-950/20 border border-red-500/20 hover:bg-red-950/40 text-red-400 px-2.5 py-1 rounded-md font-semibold">
                    <Plus className="w-3 h-3" /> Database Sync
                  </button>
                </div>

                {/* Canvas Area Container */}
                <div className="relative w-full h-[320px] border border-white/5 bg-black/40 rounded-2xl overflow-hidden">
                  
                  {/* Grid overlay */}
                  <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.015)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.015)_1px,transparent_1px)] bg-[size:20px_20px] pointer-events-none" />

                  {/* SVG Paths representing connections */}
                  <svg className="absolute inset-0 w-full h-full pointer-events-none z-0">
                    {connections.map((c, i) => {
                      const pathData = drawPath(c);
                      const isLineProcessing = activeNodeId === c.from || (completedNodeIds.includes(c.from) && !completedNodeIds.includes(c.to));
                      const isLineSuccess = completedNodeIds.includes(c.from) && completedNodeIds.includes(c.to);

                      return (
                        <g key={i}>
                          {/* Base line */}
                          <path 
                            d={pathData} 
                            stroke="rgba(255,255,255,0.05)" 
                            strokeWidth="2.5" 
                            fill="none" 
                          />
                          {/* Energetic pulse line when running */}
                          {execState === 'running' && isLineProcessing && (
                            <path 
                              d={pathData} 
                              stroke="#FF1744" 
                              strokeWidth="2.5" 
                              strokeDasharray="8,6" 
                              className="animate-[dash_6s_linear_infinite]" 
                              fill="none" 
                            />
                          )}
                          {/* Green success line */}
                          {isLineSuccess && (
                            <path 
                              d={pathData} 
                              stroke="#10B981" 
                              strokeWidth="2.5" 
                              fill="none" 
                            />
                          )}
                        </g>
                      );
                    })}
                  </svg>

                  {/* Render Draggable Nodes */}
                  {nodes.map((node) => {
                    const isActive = activeNodeId === node.id;
                    const isSuccess = completedNodeIds.includes(node.id);
                    const isSelected = selectedNodeId === node.id;

                    let nodeIcon = <Layers className="w-4 h-4" />;
                    if (node.type === 'trigger') nodeIcon = <Radio className="w-4 h-4" />;
                    if (node.type === 'extractor') nodeIcon = <GitMerge className="w-4 h-4" />;
                    if (node.type === 'search') nodeIcon = <Globe className="w-4 h-4" />;
                    if (node.type === 'verdict') nodeIcon = <Brain className="w-4 h-4" />;
                    if (node.type === 'slack' || node.type === 'discord' || node.type === 'email') nodeIcon = <AlertTriangle className="w-4 h-4" />;
                    if (node.type === 'db_sync') nodeIcon = <Database className="w-4 h-4" />;

                    return (
                      <div
                        key={node.id}
                        onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
                        className={`absolute w-36 p-3 rounded-xl border transition-all cursor-grab active:cursor-grabbing z-10 flex flex-col items-center text-center ${
                          isSelected 
                            ? 'border-red-500 bg-red-950/20 shadow-[0_0_20px_rgba(255,23,68,0.25)] scale-105' 
                            : isActive 
                            ? 'border-yellow-500 bg-yellow-950/15 shadow-[0_0_15px_rgba(245,158,11,0.2)] animate-pulse'
                            : isSuccess
                            ? 'border-emerald-500/40 bg-emerald-950/5'
                            : 'border-white/10 bg-black/60 hover:border-white/20'
                        }`}
                        style={{ left: `${node.x}px`, top: `${node.y}px` }}
                      >
                        {/* Node Sockets */}
                        <div className="absolute top-1/2 -translate-y-1/2 -left-1 w-2 h-2 rounded-full bg-white/20 border border-black" />
                        <div className="absolute top-1/2 -translate-y-1/2 -right-1 w-2 h-2 rounded-full bg-white/20 border border-black" />

                        {/* Top action handle */}
                        <div className="w-full flex items-center justify-between mb-1.5">
                          <span className={`w-1.5 h-1.5 rounded-full ${
                            isSuccess ? 'bg-emerald-400' : isActive ? 'bg-yellow-400' : 'bg-white/20'
                          }`} />
                          
                          {/* Trash button */}
                          {node.type !== 'trigger' && node.type !== 'verdict' && (
                            <button 
                              onClick={(e) => {
                                e.stopPropagation();
                                deleteNode(node.id);
                              }}
                              className="text-white/20 hover:text-red-500 p-0.5 transition-colors"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          )}
                        </div>

                        {/* Icon */}
                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center mb-1.5 ${
                          isSuccess 
                            ? 'bg-emerald-500/15 text-emerald-400' 
                            : isSelected 
                            ? 'bg-red-500/20 text-red-500' 
                            : 'bg-white/5 text-white/50'
                        }`}>
                          {nodeIcon}
                        </div>

                        <span className="text-[10px] font-bold uppercase tracking-wider block text-white/90 truncate max-w-full">
                          {node.label}
                        </span>
                        <span className="text-[8px] text-white/30 font-mono truncate max-w-full">
                          {node.type.toUpperCase()}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Right Settings / Output Panel (4 cols) */}
              <div className="lg:col-span-4 p-6 bg-black/40 flex flex-col h-[520px] border-t lg:border-t-0 border-white/5 overflow-hidden">
                
                {/* Node Config Tab */}
                <div className="flex-1 flex flex-col overflow-hidden">
                  
                  {/* Selected Node Properties Title */}
                  <div className="flex items-center gap-2 pb-3 border-b border-white/5 mb-4">
                    <Sliders className="w-4 h-4 text-red-500" />
                    <span className="text-xs font-bold font-mono tracking-widest text-white/70">
                      NODE_CONFIG_SHEET
                    </span>
                  </div>

                  {/* Properties Form Wrapper */}
                  <div className="flex-1 overflow-y-auto space-y-4 pr-1 scrollbar-thin text-xs text-white/80">
                    {selectedNodeId ? (
                      (() => {
                        const sNode = nodes.find(n => n.id === selectedNodeId);
                        if (!sNode) return <p className="text-white/30 font-mono text-[10px]">Select a node to edit.</p>;
                        
                        return (
                          <div className="space-y-3.5">
                            <div>
                              <label className="text-[9px] uppercase tracking-wider text-white/40 block mb-1 font-mono">Node Label</label>
                              <input 
                                type="text" 
                                value={sNode.label}
                                onChange={(e) => {
                                  setNodes(prev => prev.map(n => n.id === sNode.id ? { ...n, label: e.target.value } : n));
                                }}
                                className="w-full bg-black/60 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-red-500"
                              />
                            </div>

                            {/* Dynamic configuration inputs depending on node type */}
                            {sNode.type === 'trigger' && (
                              <>
                                <div>
                                  <label className="text-[9px] uppercase tracking-wider text-white/40 block mb-1 font-mono">Ingest Source</label>
                                  <select 
                                    value={sNode.config.source}
                                    onChange={(e) => updateNodeConfig(sNode.id, 'source', e.target.value)}
                                    className="w-full bg-black/60 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-red-500"
                                  >
                                    <option value="Claim Form Input">Claim Form Input</option>
                                    <option value="REST API Gateway">REST API Gateway</option>
                                    <option value="Security Webhook">Security Webhook</option>
                                    <option value="RSS News Stream">RSS News Stream</option>
                                  </select>
                                </div>
                                <div>
                                  <label className="text-[9px] uppercase tracking-wider text-white/40 block mb-1 font-mono">Factual Text Payload</label>
                                  <textarea 
                                    rows="3"
                                    value={sNode.config.claim}
                                    onChange={(e) => updateNodeConfig(sNode.id, 'claim', e.target.value)}
                                    className="w-full bg-black/60 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-red-500 resize-none"
                                  />
                                </div>
                              </>
                            )}

                            {sNode.type === 'extractor' && (
                              <>
                                <div>
                                  <label className="text-[9px] uppercase tracking-wider text-white/40 block mb-1 font-mono">LLM Core Model</label>
                                  <select 
                                    value={sNode.config.model}
                                    onChange={(e) => updateNodeConfig(sNode.id, 'model', e.target.value)}
                                    className="w-full bg-black/60 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-red-500"
                                  >
                                    <option value="Gemini-2.0-Flash">Gemini 2.0 Flash (Fast)</option>
                                    <option value="Gemini-1.5-Pro">Gemini 1.5 Pro (Deep)</option>
                                    <option value="DistilBERT Fallback">DistilBERT (Local)</option>
                                  </select>
                                </div>
                                <div>
                                  <label className="text-[9px] uppercase tracking-wider text-white/40 block mb-1 font-mono">Language</label>
                                  <input 
                                    type="text" 
                                    value={sNode.config.language}
                                    onChange={(e) => updateNodeConfig(sNode.id, 'language', e.target.value)}
                                    className="w-full bg-black/60 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-red-500"
                                  />
                                </div>
                              </>
                            )}

                            {sNode.type === 'search' && (
                              <>
                                <div>
                                  <label className="text-[9px] uppercase tracking-wider text-white/40 block mb-1 font-mono">Crawler Search Engine</label>
                                  <select 
                                    value={sNode.config.engine}
                                    onChange={(e) => updateNodeConfig(sNode.id, 'engine', e.target.value)}
                                    className="w-full bg-black/60 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-red-500"
                                  >
                                    <option value="Brave Search API">Brave Search API</option>
                                    <option value="Google CSE API">Google Custom Search</option>
                                    <option value="DuckDuckGo Crawler">DuckDuckGo Crawler</option>
                                  </select>
                                </div>
                                <div>
                                  <label className="text-[9px] uppercase tracking-wider text-white/40 block mb-1 font-mono">Max Results ({sNode.config.maxResults})</label>
                                  <input 
                                    type="range" 
                                    min="1" 
                                    max="10" 
                                    value={sNode.config.maxResults}
                                    onChange={(e) => updateNodeConfig(sNode.id, 'maxResults', parseInt(e.target.value))}
                                    className="w-full accent-red-500"
                                  />
                                </div>
                              </>
                            )}

                            {sNode.type === 'verdict' && (
                              <>
                                <div>
                                  <label className="text-[9px] uppercase tracking-wider text-white/40 block mb-1 font-mono">Audit Stance Threshold ({sNode.config.threshold}%)</label>
                                  <input 
                                    type="range" 
                                    min="50" 
                                    max="95" 
                                    value={sNode.config.threshold}
                                    onChange={(e) => updateNodeConfig(sNode.id, 'threshold', parseInt(e.target.value))}
                                    className="w-full accent-red-500"
                                  />
                                </div>
                                <div>
                                  <label className="text-[9px] uppercase tracking-wider text-white/40 block mb-1 font-mono">Fact-Check Weight ({sNode.config.factCheckWeight}%)</label>
                                  <input 
                                    type="range" 
                                    min="10" 
                                    max="70" 
                                    value={sNode.config.factCheckWeight}
                                    onChange={(e) => updateNodeConfig(sNode.id, 'factCheckWeight', parseInt(e.target.value))}
                                    className="w-full accent-red-500"
                                  />
                                </div>
                              </>
                            )}

                            {sNode.type === 'slack' && (
                              <>
                                <div>
                                  <label className="text-[9px] uppercase tracking-wider text-white/40 block mb-1 font-mono">Channel</label>
                                  <input 
                                    type="text" 
                                    value={sNode.config.channel}
                                    onChange={(e) => updateNodeConfig(sNode.id, 'channel', e.target.value)}
                                    className="w-full bg-black/60 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-red-500"
                                  />
                                </div>
                              </>
                            )}

                            {sNode.type === 'discord' && (
                              <>
                                <div>
                                  <label className="text-[9px] uppercase tracking-wider text-white/40 block mb-1 font-mono">Alert Tag Everyone</label>
                                  <select 
                                    value={sNode.config.tagEveryone ? 'true' : 'false'}
                                    onChange={(e) => updateNodeConfig(sNode.id, 'tagEveryone', e.target.value === 'true')}
                                    className="w-full bg-black/60 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-red-500"
                                  >
                                    <option value="false">FALSE</option>
                                    <option value="true">TRUE</option>
                                  </select>
                                </div>
                              </>
                            )}

                            {sNode.type === 'db_sync' && (
                              <>
                                <div>
                                  <label className="text-[9px] uppercase tracking-wider text-white/40 block mb-1 font-mono">PostgreSQL Table</label>
                                  <input 
                                    type="text" 
                                    value={sNode.config.table}
                                    onChange={(e) => updateNodeConfig(sNode.id, 'table', e.target.value)}
                                    className="w-full bg-black/60 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-red-500"
                                  />
                                </div>
                              </>
                            )}
                          </div>
                        );
                      })()
                    ) : (
                      <p className="text-white/30 font-mono text-[10px]">Select any canvas node to edit its custom parameters.</p>
                    )}
                  </div>
                </div>

                {/* Log Terminal Block (Bottom of Config Panel) */}
                <div className="border-t border-white/5 pt-4 mt-4 h-[190px] flex flex-col overflow-hidden">
                  <div className="flex items-center gap-2 pb-2">
                    <Terminal className="w-3.5 h-3.5 text-red-500" />
                    <span className="text-[9px] font-bold font-mono tracking-widest text-white/60">SHELL_LOG</span>
                  </div>

                  <div className="flex-1 overflow-y-auto space-y-1.5 font-mono text-[9px] scrollbar-thin pr-1">
                    {logEntries.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center text-white/20">
                        <p>No active runs.</p>
                        <p className="text-[8px]">Click "Test Workflow" to compile logic.</p>
                      </div>
                    ) : (
                      logEntries.map((log, i) => {
                        const isSuccess = log.startsWith('[SUCCESS]');
                        const isData = log.startsWith('[DATA]') || log.startsWith('[PAYLOAD]') || log.startsWith('[NLP]') || log.startsWith('[CRAWLER]') || log.startsWith('[VERDICT]') || log.startsWith('[ALERT]') || log.startsWith('[DATABASE]');
                        
                        return (
                          <div key={i} className={`p-1.5 rounded border leading-tight ${
                            isSuccess 
                              ? 'bg-emerald-950/20 border-emerald-500/20 text-emerald-400'
                              : isData
                              ? 'bg-white/[0.02] border-white/5 text-white/70'
                              : 'bg-red-950/10 border-red-500/10 text-red-400'
                          }`}>
                            {log}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

              </div>

            </div>
          </InteractiveCard>

        </div>
      </section>

      {/* ════════ CORE FEATURES BENTO GRID ════════ */}
      <section className="relative py-24 px-4 z-10 bg-black/40">
        <div className="max-w-7xl mx-auto space-y-12">
          
          <div className="text-center space-y-3">
            <span className="text-[10px] font-bold text-red-500 uppercase tracking-[0.2em] font-display">System Modules</span>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black font-display tracking-tight text-white leading-none">
              Fact Evaluation Grid
            </h2>
            <p className="text-sm text-white/45 max-w-xl mx-auto">
              Automate verification using multiple analytical dimensions simultaneously.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            
            {/* Module 1 */}
            <InteractiveCard className="border border-white/[0.05] bg-white/[0.02] backdrop-blur-xl p-6 space-y-4 hover:border-red-500/25 transition-all">
              <div className="w-10 h-10 rounded-xl bg-red-950/30 flex items-center justify-center border border-red-500/15 shadow-[0_0_15px_rgba(239,68,68,0.05)]">
                <Shield className="w-5 h-5 text-red-500" />
              </div>
              <h3 className="text-base font-bold text-white tracking-wide">Dynamic Ingestion</h3>
              <p className="text-xs text-white/45 leading-relaxed">
                Connect API nodes, upload PDFs, URLs, images, or audio clips. Visual pipelines process any data source.
              </p>
            </InteractiveCard>

            {/* Module 2 */}
            <InteractiveCard className="border border-white/[0.05] bg-white/[0.02] backdrop-blur-xl p-6 space-y-4 hover:border-red-500/25 transition-all">
              <div className="w-10 h-10 rounded-xl bg-red-950/30 flex items-center justify-center border border-red-500/15 shadow-[0_0_15px_rgba(239,68,68,0.05)]">
                <Brain className="w-5 h-5 text-red-500" />
              </div>
              <h3 className="text-base font-bold text-white tracking-wide">Claim Parse</h3>
              <p className="text-xs text-white/45 leading-relaxed">
                Splits long text documents or audio files into individual checkable claims. Multi-signals processed asynchronously.
              </p>
            </InteractiveCard>

            {/* Module 3 */}
            <InteractiveCard className="border border-white/[0.05] bg-white/[0.02] backdrop-blur-xl p-6 space-y-4 hover:border-red-500/25 transition-all">
              <div className="w-10 h-10 rounded-xl bg-red-950/30 flex items-center justify-center border border-red-500/15 shadow-[0_0_15px_rgba(239,68,68,0.05)]">
                <Globe className="w-5 h-5 text-red-500" />
              </div>
              <h3 className="text-base font-bold text-white tracking-wide">Web Consensus</h3>
              <p className="text-xs text-white/45 leading-relaxed">
                Retrieves real-time evidence indices from search APIs and filters authoritative sources through a scoring matrix.
              </p>
            </InteractiveCard>

            {/* Module 4 */}
            <InteractiveCard className="border border-white/[0.05] bg-white/[0.02] backdrop-blur-xl p-6 space-y-4 hover:border-red-500/25 transition-all">
              <div className="w-10 h-10 rounded-xl bg-red-950/30 flex items-center justify-center border border-red-500/15 shadow-[0_0_15px_rgba(239,68,68,0.05)]">
                <GitMerge className="w-5 h-5 text-red-500" />
              </div>
              <h3 className="text-base font-bold text-white tracking-wide">Formula Aggregation</h3>
              <p className="text-xs text-white/45 leading-relaxed">
                Weighs fact check matches, web similarity, source credibility, and linguistic heuristics for highly accurate verdicts.
              </p>
            </InteractiveCard>

            {/* Module 5 */}
            <InteractiveCard className="border border-white/[0.05] bg-white/[0.02] backdrop-blur-xl p-6 space-y-4 hover:border-red-500/25 transition-all">
              <div className="w-10 h-10 rounded-xl bg-red-950/30 flex items-center justify-center border border-red-500/15 shadow-[0_0_15px_rgba(239,68,68,0.05)]">
                <Network className="w-5 h-5 text-red-500" />
              </div>
              <h3 className="text-base font-bold text-white tracking-wide">Synaptic Audit Trail</h3>
              <p className="text-xs text-white/45 leading-relaxed">
                Every verdict lists complete step-by-step reasons. Users can audit how the system arrived at the final score.
              </p>
            </InteractiveCard>

            {/* Module 6 */}
            <InteractiveCard className="border border-white/[0.05] bg-white/[0.02] backdrop-blur-xl p-6 space-y-4 hover:border-red-500/25 transition-all">
              <div className="w-10 h-10 rounded-xl bg-red-950/30 flex items-center justify-center border border-red-500/15 shadow-[0_0_15px_rgba(239,68,68,0.05)]">
                <Lock className="w-5 h-5 text-red-500" />
              </div>
              <h3 className="text-base font-bold text-white tracking-wide">Enterprise Keys</h3>
              <p className="text-xs text-white/45 leading-relaxed">
                Access features programmatically via secure REST APIs. Deploy keys to integrate TruthShield with your app.
              </p>
            </InteractiveCard>

          </div>

        </div>
      </section>

      {/* ════════ SYSTEM ACTIVITY LOG ════════ */}
      <section className="relative py-24 px-4 z-10 bg-black/80 border-t border-white/5">
        <div className="max-w-4xl mx-auto space-y-8">
          <div className="text-center space-y-3">
            <span className="text-[10px] font-bold text-red-500 uppercase tracking-[0.2em] font-display">Shell Audit Log</span>
            <h2 className="text-3xl font-bold font-display text-white">Live Ingestion Logs</h2>
          </div>

          <div className="terminal font-mono text-[10px] leading-relaxed p-6 rounded-2xl bg-black border border-white/10 relative overflow-hidden shadow-2xl">
            {/* Scanline overlay */}
            <div className="absolute inset-0 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[size:100%_4px,6px_100%] pointer-events-none" />
            
            <div className="space-y-1 z-10 relative">
              <p className="text-red-500/40">[2026-06-24 21:30:10] CONNECTED_TO_INGESTION_SERVER host=api.truthshield.ai</p>
              <p className="text-red-500/40">[2026-06-24 21:30:12] LISTENING_TO_WEBSOCKET_PORT port=8000</p>
              <p className="text-white/60">[2026-06-24 21:30:15] INGESTED claim="Bleach cures COVID" type=TEXT</p>
              <p className="text-white/60">[2026-06-24 21:30:16] PARSING claims=1 entities=2 language=en</p>
              <p className="text-white/40">[2026-06-24 21:30:17] EVIDENCE_SEARCH query="Bleach cures COVID" ddg_results=10 fact_check_matches=3</p>
              <p className="text-emerald-400">[2026-06-24 21:30:18] WEIGHTED_AGGREGATION formula_type=weighted_verdict score=30/100</p>
              <p className="text-red-500 font-bold">[2026-06-24 21:30:19] EMITTED_VERDICT verdict=FALSE confidence=0.98 report_id=fb9fc09b</p>
              <p className="text-white/20 animate-pulse">[2026-06-24 21:30:20] IDLE_STATE waiting for payload...</p>
            </div>
          </div>
        </div>
      </section>

      {/* ════════ CTA SECTION ════════ */}
      <section className="relative py-28 px-4 z-10 text-center border-t border-white/5">
        <div className="max-w-xl mx-auto space-y-6">
          <h2 className="text-3xl sm:text-4xl font-extrabold font-display text-white">DEFEND AGAINST DISINFORMATION</h2>
          <p className="text-xs sm:text-sm text-white/50 leading-relaxed max-w-md mx-auto">
            Join the decentralized intelligence network. Secure credentials and verify facts instantly.
          </p>
          <div className="pt-4 flex justify-center">
            <Link to="/login" className="btn-primary flex items-center gap-2 text-xs font-bold tracking-widest px-8 py-4 uppercase rounded-xl shadow-[0_0_50px_rgba(255,23,68,0.2)]">
              Establish Credentials
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* ════════ minimal footer ════════ */}
      <footer className="border-t border-white/5 py-12 px-4 relative z-10 bg-black/90">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6 text-center md:text-left">
          <div className="space-y-2">
            <div className="flex items-center justify-center md:justify-start gap-2.5">
              <Shield className="w-5 h-5 text-red-500" />
              <span className="text-base font-bold font-display text-white tracking-widest">TRUTHSHIELD</span>
            </div>
            <p className="text-[10px] text-white/35">AI Cyber Misinformation Threat Command</p>
          </div>
          <div className="flex items-center gap-4 text-xs text-white/40 font-semibold">
            <Link to="/login" className="hover:text-red-500 transition-colors">Workspace</Link>
            <span>·</span>
            <Link to="/analyze" className="hover:text-red-500 transition-colors">Pipeline</Link>
            <span>·</span>
            <a href="https://github.com/tarush5/Truthshield" target="_blank" rel="noopener noreferrer" className="hover:text-red-500 transition-colors">GitHub</a>
          </div>
          <div className="text-[10px] text-white/20">
            © 2026 TruthShield Inc. All protocols secured.
          </div>
        </div>
      </footer>

    </div>
  );
}
