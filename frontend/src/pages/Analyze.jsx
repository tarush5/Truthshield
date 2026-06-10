import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, Zap, ArrowRight, Loader2, CheckCircle2, XCircle, Brain, Eye, FileSearch } from 'lucide-react';
import UploadZone from '../components/UploadZone';
import TrustGauge from '../components/TrustGauge';
import { API_BASE, getWsUrl } from '../config';

const stages = [
  { key: 'preprocessing', label: 'Preprocess', icon: FileSearch, pct: 20 },
  { key: 'detecting', label: 'Detect', icon: Eye, pct: 50 },
  { key: 'verifying', label: 'Verify', icon: Shield, pct: 80 },
  { key: 'explaining', label: 'Explain', icon: Brain, pct: 95 },
  { key: 'done', label: 'Complete', icon: CheckCircle2, pct: 100 },
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
  };

  const handleAnalyze = async () => {
    if (!file && !url && !text) return;

    setAnalyzing(true);
    setError(null);
    setResult(null);
    setCurrentStage('preprocessing');
    setProgress(5);

    try {
      // ── Use WebSocket for Text/URL analysis ──
      if (!file) {
        const wsUrl = getWsUrl();
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          ws.send(JSON.stringify({
            text: text || null,
            url: url || null,
            lang: i18n.language || 'en',
            token: localStorage.getItem('token')
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
            setProgress(100);
            setCurrentStage('done');
            setResult({
              id: data.partial_result.report_id,
              credibility: {
                trust_score: data.partial_result.trust_score,
                verdict: data.partial_result.verdict
              }
            });
            setTimeout(() => navigate(`/report/${data.partial_result.report_id}`), 1500);
            ws.close();
            return;
          }

          setCurrentStage(data.stage);
          setProgress(data.progress * 100);
        };

        ws.onerror = () => {
          setError('Connection failed. Please check if the backend is running.');
          setAnalyzing(false);
          ws.close();
        };

        return;
      }

      // ── Fallback: HTTP POST for Files ──
      const formData = new FormData();
      if (file) formData.append('file', file);
      if (url) formData.append('url', url);
      if (text) formData.append('text', text);
      formData.append('lang', i18n.language || 'en');

      // Simulated progress for HTTP uploads
      const progressStages = ['preprocessing', 'detecting', 'verifying', 'explaining'];
      let stageIndex = 0;
      const stageInterval = setInterval(() => {
        if (stageIndex < progressStages.length) {
          setCurrentStage(progressStages[stageIndex]);
          setProgress((stageIndex + 1) * 22);
          stageIndex++;
        }
      }, 2500);

      const token = localStorage.getItem('token');
      const headers = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers,
        body: formData,
      });

      clearInterval(stageInterval);

      if (!response.ok) throw new Error(`Analysis failed: ${response.statusText}`);

      const data = await response.json();
      setProgress(100);
      setCurrentStage('done');
      setResult(data);
      setTimeout(() => navigate(`/report/${data.id}`), 1500);

    } catch (err) {
      console.error('Analysis error:', err);
      setError(err.message || 'Analysis failed. Please try again.');
      setAnalyzing(false);
      setCurrentStage(null);
      setProgress(0);
    }
  };

  const hasInput = file || url || text;
  const stageIdx = stages.findIndex(s => s.key === currentStage);

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Hero Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-12"
      >
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-brand-500/10 border border-brand-500/20 mb-6">
          <Zap className="w-4 h-4 text-brand-400" />
          <span className="text-sm font-medium text-brand-300">{t('tagline') || 'AI-Powered Analysis'}</span>
        </div>

        <h1 className="text-4xl sm:text-5xl font-extrabold font-display tracking-tight mb-4">
          <span className="gradient-text">{t('analyze.title') || 'Analyze Content'}</span>
        </h1>
        <p className="text-lg text-white/40 max-w-2xl mx-auto">
          {t('analyze.subtitle') || 'Submit any content for AI-powered misinformation detection'}
        </p>
      </motion.div>

      {/* Upload Zone */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mb-8"
      >
        <UploadZone
          onFileSelect={setFile}
          onUrlSubmit={setUrl}
          onTextSubmit={setText}
          disabled={analyzing}
        />
      </motion.div>

      {/* Analyze Button */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="flex justify-center gap-3 mb-8"
      >
        <button
          onClick={handleAnalyze}
          disabled={!hasInput || analyzing}
          className="btn-primary-lg flex items-center gap-3"
        >
          {analyzing ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              {t('analyze.btn_analyzing') || 'Analyzing...'}
            </>
          ) : (
            <>
              <Shield className="w-5 h-5" />
              {t('analyze.btn_analyze') || 'Analyze Content'}
              <ArrowRight className="w-5 h-5" />
            </>
          )}
        </button>
        {analyzing && (
          <button onClick={handleCancel} className="btn-secondary flex items-center gap-2 text-red-400">
            <XCircle className="w-4 h-4" />
            Cancel
          </button>
        )}
      </motion.div>

      {/* Error Display */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="glass-card border-red-500/30 p-5 mb-8 text-center"
          >
            <p className="text-red-400 text-sm">{error}</p>
            <button
              onClick={() => { setError(null); handleAnalyze(); }}
              className="mt-2 text-xs text-brand-400 hover:underline"
            >
              Retry Analysis
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Progress Stages */}
      <AnimatePresence>
        {analyzing && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="glass-card p-8"
          >
            {/* Progress Bar */}
            <div className="progress-bar mb-8">
              <motion.div
                className="progress-fill bg-gradient-to-r from-brand-500 to-cyan-500"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              />
            </div>

            {/* Stage Indicators */}
            <div className="grid grid-cols-5 gap-3">
              {stages.map((stage, idx) => {
                const isActive = idx === stageIdx;
                const isDone = idx < stageIdx;
                const StageIcon = stage.icon;

                return (
                  <motion.div
                    key={stage.key}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ 
                      opacity: isActive ? 1 : isDone ? 0.7 : 0.3,
                      scale: isActive ? 1.05 : 1,
                    }}
                    transition={{ duration: 0.3 }}
                    className={`flex flex-col items-center gap-2 p-3 rounded-xl transition-all ${
                      isActive ? 'bg-brand-500/10' : ''
                    }`}
                  >
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300 ${
                      isDone ? 'bg-emerald-500/20' : isActive ? 'bg-brand-500/20 glow-pulse' : 'bg-white/5'
                    }`}>
                      {isDone ? (
                        <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                      ) : isActive ? (
                        <Loader2 className="w-5 h-5 text-brand-400 animate-spin" />
                      ) : (
                        <StageIcon className="w-5 h-5 text-white/20" />
                      )}
                    </div>
                    <span className={`text-xs font-medium text-center ${
                      isActive ? 'text-brand-300' : isDone ? 'text-emerald-400/70' : 'text-white/20'
                    }`}>
                      {stage.label}
                    </span>
                  </motion.div>
                );
              })}
            </div>

            {/* Quick Result Preview */}
            {result && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="mt-8 flex flex-col items-center gap-3"
              >
                <TrustGauge score={result.credibility?.trust_score || 50} size={160} />
                <p className="text-xs text-white/30">Redirecting to full report...</p>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Features Grid */}
      {!analyzing && !result && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-12"
        >
          {[
            { title: 'Multimodal Analysis', desc: 'Text, images, audio, video & URLs', icon: Eye },
            { title: 'Multilingual', desc: 'English, Hindi & Tamil support', icon: FileSearch },
            { title: 'AI-Powered', desc: '5-stage detection pipeline', icon: Brain },
          ].map((feat, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 + idx * 0.1 }}
              className="glass-card-hover p-5 text-center"
            >
              <div className="w-10 h-10 rounded-xl bg-brand-500/10 flex items-center justify-center mx-auto mb-3">
                <feat.icon className="w-5 h-5 text-brand-400" />
              </div>
              <h3 className="text-sm font-semibold text-white/80 mb-1">{feat.title}</h3>
              <p className="text-xs text-white/40">{feat.desc}</p>
            </motion.div>
          ))}
        </motion.div>
      )}
    </div>
  );
}
