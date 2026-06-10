import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Shield, Zap, ArrowRight, Loader2, CheckCircle2 } from 'lucide-react';
import UploadZone from '../components/UploadZone';
import TrustGauge from '../components/TrustGauge';
import { API_BASE, getWsUrl } from '../config';

const stages = [
  { key: 'preprocessing', pct: 20 },
  { key: 'detecting', pct: 50 },
  { key: 'verifying', pct: 80 },
  { key: 'explaining', pct: 95 },
  { key: 'done', pct: 100 },
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
            
            // Re-format WS dummy data to match normal REST result for UX
            setResult({
              id: data.partial_result.report_id,
              credibility: {
                trust_score: data.partial_result.trust_score,
                verdict: data.partial_result.verdict
              }
            });

            setTimeout(() => {
              navigate(`/report/${data.partial_result.report_id}`);
            }, 1500);
            
            ws.close();
            return;
          }

          // Update Progress
          setCurrentStage(data.stage);
          setProgress(data.progress * 100);
        };

        ws.onerror = (err) => {
          console.error("WS error:", err);
          setError("WebSocket Connection failed. Falling back to HTTP...");
          ws.close();
        };

        return; // wait for WS to finish
      }

      // ── Fallback: HTTP POST for Files ──
      const formData = new FormData();
      if (file) formData.append('file', file);
      if (url) formData.append('url', url);
      if (text) formData.append('text', text);
      formData.append('lang', i18n.language || 'en');

      // Simulate stage progression for UX since HTTP doesn't stream progress
      const stageInterval = setInterval(() => {
        setProgress((prev) => {
          if (prev < 90) return prev + Math.random() * 8;
          return prev;
        });
      }, 800);

      const stageTimer = setTimeout(() => setCurrentStage('detecting'), 2000);
      const stageTimer2 = setTimeout(() => setCurrentStage('verifying'), 5000);
      const stageTimer3 = setTimeout(() => setCurrentStage('explaining'), 8000);

      const token = localStorage.getItem('token');
      const headers = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: headers,
        body: formData,
      });

      clearInterval(stageInterval);
      clearTimeout(stageTimer);
      clearTimeout(stageTimer2);
      clearTimeout(stageTimer3);

      if (!response.ok) {
        throw new Error(`Analysis failed: ${response.statusText}`);
      }

      const data = await response.json();
      setProgress(100);
      setCurrentStage('done');
      setResult(data);

      setTimeout(() => {
        navigate(`/report/${data.id}`);
      }, 1500);

    } catch (err) {
      console.error('Analysis error:', err);
      setError(err.message || 'Analysis failed. Please check if the backend is running.');
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
      <div className="text-center mb-12 animate-in">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-brand-500/10 border border-brand-500/20 mb-6">
          <Zap className="w-4 h-4 text-brand-400" />
          <span className="text-sm font-medium text-brand-300">{t('tagline')}</span>
        </div>

        <h1 className="text-4xl sm:text-5xl font-extrabold font-display tracking-tight mb-4">
          <span className="gradient-text">{t('analyze.title')}</span>
        </h1>
        <p className="text-lg text-white/40 max-w-2xl mx-auto">
          {t('analyze.subtitle')}
        </p>
      </div>

      {/* Upload Zone */}
      <div className="mb-8 animate-in" style={{ animationDelay: '0.1s' }}>
        <UploadZone
          onFileSelect={setFile}
          onUrlSubmit={setUrl}
          onTextSubmit={setText}
          disabled={analyzing}
        />
      </div>

      {/* Analyze Button */}
      <div className="flex justify-center mb-8 animate-in" style={{ animationDelay: '0.2s' }}>
        <button
          onClick={handleAnalyze}
          disabled={!hasInput || analyzing}
          className="btn-primary flex items-center gap-3 text-lg px-10 py-4"
        >
          {analyzing ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              {t('analyze.btn_analyzing')}
            </>
          ) : (
            <>
              <Shield className="w-5 h-5" />
              {t('analyze.btn_analyze')}
              <ArrowRight className="w-5 h-5" />
            </>
          )}
        </button>
      </div>

      {/* Error Display */}
      {error && (
        <div className="glass-card border-red-500/30 p-5 mb-8 text-center">
          <p className="text-red-400 text-sm">{error}</p>
          <p className="text-white/30 text-xs mt-2">Make sure the backend server is running on port 8000</p>
        </div>
      )}

      {/* Progress Stages */}
      {analyzing && (
        <div className="glass-card p-8 animate-in">
          {/* Progress Bar */}
          <div className="progress-bar mb-8">
            <div
              className="progress-fill bg-gradient-to-r from-brand-500 to-cyan-500"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Stage Indicators */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
            {stages.map((stage, idx) => {
              const isActive = idx === stageIdx;
              const isDone = idx < stageIdx;

              return (
                <div
                  key={stage.key}
                  className={`flex flex-col items-center gap-2 p-3 rounded-xl transition-all duration-300 ${
                    isActive ? 'bg-brand-500/10 scale-105' : isDone ? 'opacity-60' : 'opacity-30'
                  }`}
                >
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    isDone ? 'bg-emerald-500/20' : isActive ? 'bg-brand-500/20' : 'bg-white/5'
                  }`}>
                    {isDone ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : isActive ? (
                      <Loader2 className="w-4 h-4 text-brand-400 animate-spin" />
                    ) : (
                      <div className="w-2 h-2 rounded-full bg-white/20" />
                    )}
                  </div>
                  <span className={`text-xs font-medium text-center ${
                    isActive ? 'text-brand-300' : isDone ? 'text-white/50' : 'text-white/20'
                  }`}>
                    {t(`analyze.progress.${stage.key}`)}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Quick Result Preview */}
          {result && (
            <div className="mt-8 flex justify-center">
              <TrustGauge score={result.credibility?.trust_score || 50} size={160} />
            </div>
          )}
        </div>
      )}

      {/* Features Grid */}
      {!analyzing && !result && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-12 animate-in" style={{ animationDelay: '0.3s' }}>
          {[
            { title: 'Multimodal Analysis', desc: 'Text, images, audio, video & URLs', icon: '🔍' },
            { title: 'Multilingual', desc: 'English, Hindi & Tamil support', icon: '🌐' },
            { title: 'AI-Powered', desc: 'Claude AI + ML detection models', icon: '🤖' },
          ].map((feat, idx) => (
            <div key={idx} className="glass-card-hover p-5 text-center">
              <div className="text-3xl mb-3">{feat.icon}</div>
              <h3 className="text-sm font-semibold text-white/80 mb-1">{feat.title}</h3>
              <p className="text-xs text-white/40">{feat.desc}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
