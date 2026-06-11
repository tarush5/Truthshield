import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Shield, Zap, ArrowRight, Loader2, CheckCircle2, 
  XCircle, Brain, Eye, FileSearch, HelpCircle, 
  RefreshCw, Check, AlertCircle, FileText
} from 'lucide-react';
import UploadZone from '../components/UploadZone';
import TrustGauge from '../components/TrustGauge';
import { API_BASE, getWsUrl } from '../config';
import InteractiveCard from '../components/InteractiveCard';


const PIPELINE_STAGES = [
  { key: 'preprocessing', label: 'Extracting Claims', icon: FileSearch },
  { key: 'detecting', label: 'Searching Evidence', icon: Eye },
  { key: 'verifying', label: 'Ranking Sources', icon: Shield },
  { key: 'explaining', label: 'Verifying Facts', icon: Brain },
  { key: 'done', label: 'Generating Verdict', icon: CheckCircle2 }
];

export default function Analyze() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();

  const [file, setFile] = useState(null);
  const [url, setUrl] = useState('');
  const [text, setText] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [currentStage, setCurrentStage] = useState(null);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  
  // Track ticks for each stage
  const [completedStages, setCompletedStages] = useState([]);
  const wsRef = useRef(null);

  const handleCancel = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setAnalyzing(false);
    setCurrentStage(null);
    setProgress(0);
    setResult(null);
    setError(null);
    setCompletedStages([]);
  };

  const handleAnalyze = async () => {
    if (!file && !url && !text) return;

    setAnalyzing(true);
    setError(null);
    setResult(null);
    setCompletedStages([]);
    setCurrentStage('preprocessing');
    setProgress(5);

    try {
      // ── WebSocket for Text or URL ──
      if (!file) {
        const wsUrl = getWsUrl();
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          ws.send(JSON.stringify({
            text: text || null,
            url: url || null,
            lang: i18n.language || 'en',
            token: localStorage.getItem('token'),
            org_id: localStorage.getItem('active_org_id') || null
          }));
        };

        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          
          if (data.stage === 'error') {
            setError(data.message);
            setAnalyzing(false);
            ws.close();
            return;
          }

          if (data.stage === 'done') {
            // Check off everything
            setCompletedStages(PIPELINE_STAGES.map(s => s.key));
            setProgress(100);
            setCurrentStage('done');
            setResult({
              id: data.partial_result.report_id,
              credibility: {
                trust_score: data.partial_result.trust_score,
                verdict: data.partial_result.verdict
              }
            });
            setTimeout(() => navigate(`/report/${data.partial_result.report_id}`), 1800);
            ws.close();
            return;
          }

          // Advance stages dynamically
          setCurrentStage(data.stage);
          setProgress(data.progress * 100);

          // Update ticks
          const stageIdx = PIPELINE_STAGES.findIndex(s => s.key === data.stage);
          if (stageIdx !== -1) {
            const completed = PIPELINE_STAGES.slice(0, stageIdx).map(s => s.key);
            setCompletedStages(completed);
          }
        };

        ws.onerror = async () => {
          ws.close();
          // Fallback: retry via HTTP POST when WebSocket fails
          console.warn('[TruthShield] WebSocket failed, falling back to HTTP POST');
          try {
            const formData = new FormData();
            if (text) formData.append('text', text);
            if (url) formData.append('url', url);
            formData.append('lang', i18n.language || 'en');
            const orgId = localStorage.getItem('active_org_id');
            if (orgId) formData.append('org_id', orgId);

            const token = localStorage.getItem('token');
            const headers = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;

            // Simulate pipeline stages during HTTP wait
            const stagesKeys = PIPELINE_STAGES.map(s => s.key);
            let stepIdx = 0;
            const interval = setInterval(() => {
              if (stepIdx < stagesKeys.length - 1) {
                const current = stagesKeys[stepIdx];
                setCurrentStage(current);
                setCompletedStages(prev => [...new Set([...prev, current])]);
                setProgress((stepIdx + 1) * 20);
                stepIdx++;
              }
            }, 2000);

            const response = await fetch(`${API_BASE}/analyze`, {
              method: 'POST',
              headers,
              body: formData,
            });
            clearInterval(interval);

            if (response.status === 401 || response.status === 403) {
              throw new Error('Authentication required. Please log in to analyze claims.');
            }
            if (!response.ok) throw new Error(`Analysis failed: ${response.statusText}`);

            const data = await response.json();
            setCompletedStages(stagesKeys);
            setProgress(100);
            setCurrentStage('done');
            setResult(data);
            setTimeout(() => navigate(`/report/${data.id}`), 1800);
          } catch (httpErr) {
            console.error('HTTP fallback also failed:', httpErr);
            if (httpErr.message && httpErr.message.includes('Authentication required')) {
              setError(httpErr.message);
            } else {
              setError('Connection failed. Please check if the backend is running.');
            }
            setAnalyzing(false);
            setCurrentStage(null);
            setProgress(0);
            setCompletedStages([]);
          }
        };

        return;
      }

      // ── HTTP POST for File Uploads ──
      const formData = new FormData();
      if (file) formData.append('file', file);
      if (url) formData.append('url', url);
      if (text) formData.append('text', text);
      formData.append('lang', i18n.language || 'en');
      const orgId = localStorage.getItem('active_org_id');
      if (orgId) formData.append('org_id', orgId);

      // Simulate steps progression visually
      const stagesKeys = PIPELINE_STAGES.map(s => s.key);
      let stepIdx = 0;
      
      const interval = setInterval(() => {
        if (stepIdx < stagesKeys.length - 1) {
          const current = stagesKeys[stepIdx];
          setCurrentStage(current);
          setCompletedStages(prev => [...new Set([...prev, current])]);
          setProgress((stepIdx + 1) * 20);
          stepIdx++;
        }
      }, 1500);

      const token = localStorage.getItem('token');
      const headers = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers,
        body: formData,
      });

      clearInterval(interval);

      if (response.status === 401 || response.status === 403) {
        throw new Error('Authentication required. Please log in to analyze claims.');
      }
      if (!response.ok) throw new Error(`Analysis failed: ${response.statusText}`);

      const data = await response.json();
      setCompletedStages(stagesKeys);
      setProgress(100);
      setCurrentStage('done');
      setResult(data);
      setTimeout(() => navigate(`/report/${data.id}`), 1800);

    } catch (err) {
      console.error('Analysis error:', err);
      setError(err.message || 'Analysis failed. Please try again.');
      setAnalyzing(false);
      setCurrentStage(null);
      setProgress(0);
      setCompletedStages([]);
    }
  };

  const hasInput = file || url || text;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 space-y-10">
      
      {/* Page header section */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center space-y-4"
      >
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-sky-500/10 border border-sky-500/20">
          <Brain className="w-3.5 h-3.5 text-sky-400" />
          <span className="text-[10px] font-bold uppercase tracking-wider text-sky-300">Advanced AI Core Ingestion</span>
        </div>
        <h1 className="text-4xl sm:text-5xl font-extrabold font-display text-white tracking-tight">
          Verify Claim Node
        </h1>
        <p className="text-sm text-white/45 max-w-xl mx-auto">
          Submit files, text segments or source URLs directly to the pipeline. Results are cross-audited.
        </p>
      </motion.div>

      {/* Input panel wrapper */}
      {!analyzing && (
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="space-y-6"
        >
          <UploadZone
            onFileSelect={setFile}
            onUrlSubmit={setUrl}
            onTextSubmit={setText}
            disabled={analyzing}
          />

          <div className="flex justify-center gap-3">
            <button
              onClick={handleAnalyze}
              disabled={!hasInput || analyzing}
              className="btn-primary flex items-center gap-2 text-sm"
            >
              Analyze Input
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </motion.div>
      )}

      {/* Dynamic Processing Pipeline (Replaces basic loaders) */}
      <AnimatePresence>
        {analyzing && (
          <InteractiveCard className="border border-white/10 bg-[#030712]/40 backdrop-blur-xl">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="p-8 relative overflow-hidden space-y-8"
            >
            {/* Ambient Aurora Glow inside loader */}
            <div className="absolute -top-12 -right-12 w-48 h-48 bg-sky-500/10 rounded-full blur-3xl pointer-events-none" />

            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">Ingestion Running</h3>
                <p className="text-xs text-white/40 mt-0.5">Stage progression and signal mapping</p>
              </div>
              <button onClick={handleCancel} className="btn-secondary text-[10px] py-1 px-4 hover:border-red-500/30 hover:text-red-400 transition-colors">
                Cancel Run
              </button>
            </div>

            {/* Simulated Live Ticks Pipeline */}
            <div className="space-y-4">
              {PIPELINE_STAGES.map((stage, idx) => {
                const isCompleted = completedStages.includes(stage.key);
                const isActive = currentStage === stage.key;
                const StageIcon = stage.icon;

                return (
                  <div 
                    key={stage.key}
                    className={`flex items-center gap-4 p-3.5 rounded-xl border transition-all duration-300 ${
                      isActive 
                        ? 'bg-sky-500/5 border-sky-400/30 shadow-[0_0_15px_rgba(14,165,233,0.05)] electric-glow laser-sweep' 
                        : isCompleted
                        ? 'bg-white/[0.01] border-white/5 opacity-80'
                        : 'border-transparent opacity-25'
                    }`}

                  >
                    {/* Status Circle */}
                    <div className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 transition-colors ${
                      isCompleted 
                        ? 'bg-emerald-500/15 text-emerald-400' 
                        : isActive 
                        ? 'bg-sky-500/15 text-sky-400 animate-pulse' 
                        : 'bg-white/5 text-white/30'
                    }`}>
                      {isCompleted ? (
                        <Check className="w-3.5 h-3.5" />
                      ) : isActive ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <StageIcon className="w-3.5 h-3.5" />
                      )}
                    </div>

                    <span className={`text-xs font-semibold ${
                      isActive ? 'text-sky-300 font-bold' : isCompleted ? 'text-white/70' : 'text-white/30'
                    }`}>
                      {stage.label}
                    </span>

                    {isActive && (
                      <span className="text-[10px] font-mono text-sky-400 ml-auto animate-pulse">ACTIVE</span>
                    )}
                    {isCompleted && (
                      <span className="text-[10px] font-mono text-emerald-400 ml-auto font-bold">✓ DONE</span>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Overall Progress Slider */}
            <div className="space-y-2">
              <div className="flex justify-between text-[10px] font-mono text-white/40">
                <span>PIPELINE CAPACITY</span>
                <span>{progress}%</span>
              </div>
              <div className="progress-bar">
                <motion.div 
                  className="progress-fill bg-gradient-to-r from-sky-400 to-indigo-500" 
                  initial={{ width: 0 }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
            </div>
            </motion.div>
          </InteractiveCard>
        )}
      </AnimatePresence>

      {/* Error displays */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="p-5 glass-card border-red-500/25 bg-red-500/[0.02] text-center space-y-3"
          >
            <div className="flex items-center justify-center gap-2 text-red-400 text-xs font-bold uppercase tracking-wider">
              <AlertCircle className="w-4 h-4" />
              Inference Failure
            </div>
            <p className="text-xs text-white/75">{error}</p>
            <div>
              <button
                onClick={() => { setError(null); handleAnalyze(); }}
                className="btn-secondary text-[10px] py-1.5 px-5"
              >
                Retry Execution
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Technology parameters grid (rendered when idle) */}
      {!analyzing && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="grid grid-cols-1 sm:grid-cols-3 gap-4"
        >
          {[
            { title: 'Dynamic Analysis', desc: 'Audio voice matching, deepfake detection & text integrity', icon: Eye },
            { title: 'Localization Support', desc: 'Verified English, Hindi & Tamil semantic translation', icon: FileSearch },
            { title: 'pgvector Cluster', desc: 'RAG fact mapping against global research consensus', icon: Brain },
          ].map((item, i) => (
            <InteractiveCard key={i} className="border border-white/5 bg-[#071124]/30 backdrop-blur-xl">
              <div className="p-5 space-y-3">
                <div className="w-8 h-8 rounded-lg bg-sky-500/10 flex items-center justify-center">
                  <item.icon className="w-4 h-4 text-sky-400" />
                </div>
                <h4 className="text-xs font-bold text-white">{item.title}</h4>
                <p className="text-[10px] text-white/45 leading-relaxed">{item.desc}</p>
              </div>
            </InteractiveCard>
          ))}
        </motion.div>
      )}

    </div>
  );
}
