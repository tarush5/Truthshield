import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Globe, X, MapPin, ExternalLink } from 'lucide-react';

/**
 * Convert lat/lng to SVG coordinates (Mercator-ish projection)
 * ViewBox: 0 0 1000 500
 */
function latLngToSvg(lat, lng) {
  const x = ((lng + 180) / 360) * 1000;
  const y = ((90 - lat) / 180) * 500;
  return { x, y };
}

// Actual SVG paths for world continents — simplified but recognizable outlines
const CONTINENT_PATHS = [
  // North America
  "M130,80 L155,65 L180,55 L220,50 L250,60 L270,55 L285,68 L280,80 L265,85 L260,100 L250,120 L235,135 L230,145 L240,155 L250,160 L248,170 L238,180 L225,185 L210,190 L195,195 L180,205 L165,210 L155,225 L150,210 L140,195 L130,185 L120,175 L115,160 L110,145 L105,130 L110,115 L115,100 L120,90 Z",
  // South America
  "M220,250 L235,240 L255,245 L270,250 L280,260 L290,275 L295,295 L290,315 L285,330 L275,345 L268,360 L260,375 L250,390 L240,400 L232,415 L228,405 L225,390 L220,375 L215,355 L210,340 L205,320 L200,305 L195,290 L200,275 L205,260 Z",
  // Europe
  "M430,60 L445,55 L465,50 L485,52 L505,55 L520,60 L530,68 L525,80 L515,90 L508,100 L500,110 L490,115 L478,118 L470,125 L460,128 L450,125 L440,118 L435,110 L430,100 L425,90 L428,75 Z",
  // Africa
  "M430,145 L445,140 L465,142 L485,145 L505,148 L520,155 L530,165 L535,180 L538,200 L535,220 L530,240 L525,260 L515,280 L505,295 L495,310 L485,320 L475,330 L460,335 L448,328 L440,315 L435,300 L430,280 L425,260 L420,240 L418,220 L420,200 L422,180 L425,165 L428,155 Z",
  // Asia
  "M540,40 L570,35 L610,32 L650,30 L690,35 L730,40 L760,48 L790,55 L810,65 L825,75 L830,90 L825,105 L810,115 L790,120 L770,125 L750,130 L730,135 L710,138 L690,140 L665,142 L640,145 L615,148 L590,150 L570,148 L555,140 L542,130 L535,115 L530,100 L528,85 L530,70 L535,55 Z",
  // Australia
  "M750,280 L770,275 L795,278 L820,282 L840,290 L852,300 L855,315 L848,330 L835,340 L818,345 L800,348 L780,345 L765,338 L755,325 L750,310 L748,295 Z",
  // Greenland (small)
  "M270,25 L290,20 L310,22 L325,30 L328,42 L320,52 L305,55 L288,52 L275,45 L270,35 Z",
];

// Color for verdict
const VERDICT_COLOR = {
  FALSE: '#ef4444',
  MISLEADING: '#f59e0b',
};

/**
 * ThreatMap — SVG world map with animated threat indicators
 * @param {array} threats - Array of { id, claim, verdict, confidence, lat, lng, source_platform, virality_score }
 */
export default function ThreatMap({ threats = [] }) {
  const [selected, setSelected] = useState(null);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
      className="glass-card overflow-hidden"
    >
      {/* Header */}
      <div className="p-6 pb-0">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="section-title text-lg flex items-center gap-2">
              <Globe className="w-5 h-5 text-brand-400" />
              Global Threat Map
            </h3>
            <p className="text-xs text-white/30 mt-1">
              Real-time misinformation vectors across the world
            </p>
          </div>
          <div className="flex items-center gap-4 text-[11px] text-white/40">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-red-500" /> False
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-500" /> Misleading
            </span>
          </div>
        </div>
      </div>

      {/* Map container */}
      <div className="relative p-6 pt-4">
        <div className="relative bg-white/[0.02] rounded-xl border border-white/[0.04] overflow-hidden">
          <svg
            viewBox="0 0 1000 500"
            className="w-full h-auto"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* Grid lines for subtle map texture */}
            <defs>
              <pattern id="mapGrid" width="50" height="50" patternUnits="userSpaceOnUse">
                <path d="M 50 0 L 0 0 0 50" fill="none" stroke="rgba(255,255,255,0.015)" strokeWidth="0.5" />
              </pattern>
            </defs>
            <rect width="1000" height="500" fill="url(#mapGrid)" />

            {/* Continent outlines */}
            {CONTINENT_PATHS.map((path, i) => (
              <path
                key={i}
                d={path}
                fill="rgba(59,147,255,0.06)"
                stroke="rgba(59,147,255,0.12)"
                strokeWidth="0.8"
              />
            ))}

            {/* Threat dots */}
            {threats.map((threat) => {
              const { x, y } = latLngToSvg(threat.lat, threat.lng);
              const dotColor = VERDICT_COLOR[threat.verdict] || '#ef4444';
              const isSelected = selected?.id === threat.id;

              return (
                <g key={threat.id} className="cursor-pointer" onClick={() => setSelected(threat)}>
                  {/* Pulse ring animation */}
                  <circle cx={x} cy={y} r="12" fill="none" stroke={dotColor} strokeWidth="1" opacity="0.3">
                    <animate attributeName="r" values="6;18" dur="2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.4;0" dur="2s" repeatCount="indefinite" />
                  </circle>
                  <circle cx={x} cy={y} r="8" fill="none" stroke={dotColor} strokeWidth="0.5" opacity="0.2">
                    <animate attributeName="r" values="4;14" dur="2s" begin="0.5s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.3;0" dur="2s" begin="0.5s" repeatCount="indefinite" />
                  </circle>

                  {/* Core dot */}
                  <circle
                    cx={x} cy={y} r={isSelected ? 5 : 4}
                    fill={dotColor}
                    stroke="#020617"
                    strokeWidth="1.5"
                    className="transition-all"
                  />
                  {isSelected && (
                    <circle cx={x} cy={y} r="8" fill="none" stroke="#3b93ff" strokeWidth="1.5" opacity="0.6" />
                  )}
                </g>
              );
            })}
          </svg>

          {/* Floating threat detail card */}
          <AnimatePresence>
            {selected && (
              <motion.div
                initial={{ opacity: 0, y: 8, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.95 }}
                transition={{ duration: 0.2 }}
                className="absolute top-4 right-4 w-72 bg-surface-800/95 backdrop-blur-xl
                           border border-white/10 rounded-xl p-4 shadow-2xl shadow-black/50 z-10"
              >
                {/* Close button */}
                <button
                  onClick={(e) => { e.stopPropagation(); setSelected(null); }}
                  className="absolute top-3 right-3 p-1 rounded-lg hover:bg-white/10 
                             text-white/30 hover:text-white transition-colors"
                >
                  <X className="w-3.5 h-3.5" />
                </button>

                {/* Verdict badge */}
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase
                  ${selected.verdict === 'FALSE' ? 'bg-red-500/15 text-red-400' : 'bg-amber-500/15 text-amber-400'}`}>
                  {selected.verdict}
                </span>

                {/* Claim */}
                <p className="text-sm text-white/80 mt-2.5 leading-relaxed line-clamp-3">
                  {selected.claim}
                </p>

                {/* Meta grid */}
                <div className="grid grid-cols-2 gap-2 mt-3">
                  <div className="p-2 rounded-lg bg-white/[0.04] border border-white/[0.06]">
                    <span className="text-[9px] text-white/30 uppercase font-semibold">Confidence</span>
                    <p className="text-xs font-bold text-white/80 mt-0.5">{selected.confidence}%</p>
                  </div>
                  <div className="p-2 rounded-lg bg-white/[0.04] border border-white/[0.06]">
                    <span className="text-[9px] text-white/30 uppercase font-semibold">Virality</span>
                    <p className="text-xs font-bold text-white/80 mt-0.5">{selected.virality_score || '—'}</p>
                  </div>
                  <div className="p-2 rounded-lg bg-white/[0.04] border border-white/[0.06]">
                    <span className="text-[9px] text-white/30 uppercase font-semibold">Platform</span>
                    <p className="text-xs font-bold text-brand-400 capitalize mt-0.5">
                      {selected.source_platform || '—'}
                    </p>
                  </div>
                  <div className="p-2 rounded-lg bg-white/[0.04] border border-white/[0.06]">
                    <span className="text-[9px] text-white/30 uppercase font-semibold">Location</span>
                    <p className="text-[10px] font-mono text-white/50 mt-0.5">
                      {selected.lat?.toFixed(2)}, {selected.lng?.toFixed(2)}
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Threat count badge */}
        {threats.length > 0 && (
          <div className="mt-3 text-center">
            <span className="text-[11px] text-white/25 font-medium">
              Tracking {threats.length} active threat{threats.length !== 1 ? 's' : ''}
            </span>
          </div>
        )}
      </div>
    </motion.div>
  );
}
