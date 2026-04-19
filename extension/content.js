/**
 * TruthShield — Content Script
 * Scans page article text and displays a trust badge overlay.
 */

(function () {
  'use strict';

  const API_URL = 'http://localhost:8000/api/v1';
  const BADGE_ID = 'truthshield-badge';

  // Avoid running on non-article pages
  const SKIP_DOMAINS = ['google.com', 'youtube.com', 'github.com', 'localhost'];

  function shouldSkip() {
    const host = window.location.hostname;
    return SKIP_DOMAINS.some(d => host.includes(d));
  }

  function extractArticleText() {
    // Try structured selectors
    const selectors = ['article', 'main', '[role="main"]', '.post-content', '.entry-content', '.article-body'];
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && el.innerText.length > 200) {
        return el.innerText.trim().substring(0, 3000);
      }
    }
    // Fallback: gather all paragraphs
    const paragraphs = document.querySelectorAll('p');
    const texts = Array.from(paragraphs)
      .map(p => p.innerText.trim())
      .filter(t => t.length > 50);
    return texts.join('\n').substring(0, 3000);
  }

  function createBadge(score, verdict) {
    // Remove existing badge
    const existing = document.getElementById(BADGE_ID);
    if (existing) existing.remove();

    let color, bg, emoji;
    if (score >= 75) { color = '#10b981'; bg = 'rgba(16,185,129,0.15)'; emoji = '✅'; }
    else if (score >= 55) { color = '#f59e0b'; bg = 'rgba(245,158,11,0.15)'; emoji = '⚠️'; }
    else if (score >= 35) { color = '#f97316'; bg = 'rgba(249,115,22,0.15)'; emoji = '🟡'; }
    else { color = '#ef4444'; bg = 'rgba(239,68,68,0.15)'; emoji = '🔴'; }

    const badge = document.createElement('div');
    badge.id = BADGE_ID;
    badge.innerHTML = `
      <div style="
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 999999;
        background: #0f172a;
        border: 1px solid ${color}40;
        border-radius: 16px;
        padding: 12px 16px;
        display: flex;
        align-items: center;
        gap: 10px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 20px ${color}20;
        font-family: 'Inter', -apple-system, sans-serif;
        cursor: pointer;
        transition: all 0.3s ease;
        max-width: 280px;
      " onmouseover="this.style.transform='scale(1.03)'" onmouseout="this.style.transform='scale(1)'">
        <div style="
          width: 40px; height: 40px; border-radius: 12px;
          background: ${bg}; display: flex; align-items: center;
          justify-content: center; font-size: 18px; flex-shrink: 0;
        ">${emoji}</div>
        <div>
          <div style="color: ${color}; font-weight: 700; font-size: 14px;">
            🛡️ TruthShield: ${score}/100
          </div>
          <div style="color: rgba(255,255,255,0.5); font-size: 11px; margin-top: 2px;">
            ${verdict}
          </div>
        </div>
        <div style="
          position: absolute; top: 4px; right: 8px;
          color: rgba(255,255,255,0.2); font-size: 14px; cursor: pointer;
          padding: 4px;
        " onclick="event.stopPropagation(); this.parentElement.parentElement.remove();">✕</div>
      </div>
    `;

    document.body.appendChild(badge);

    // Click to open full report
    badge.querySelector('div').addEventListener('click', () => {
      // Store result and open popup
      chrome.storage.local.set({ lastResult: { score, verdict, url: window.location.href } });
    });
  }

  async function analyzeCurrentPage() {
    if (shouldSkip()) return;

    const text = extractArticleText();
    if (!text || text.length < 100) return;

    try {
      const formData = new FormData();
      formData.append('text', text);
      formData.append('url', window.location.href);
      formData.append('lang', document.documentElement.lang || 'en');

      const response = await fetch(`${API_URL}/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        const score = data.credibility?.trust_score ?? 50;
        const verdict = data.credibility?.verdict ?? 'Unknown';

        createBadge(score, verdict);

        // Store for popup
        chrome.storage.local.set({
          lastResult: {
            score,
            verdict,
            url: window.location.href,
            reportId: data.id,
          },
        });
      }
    } catch (err) {
      console.log('TruthShield: Backend not reachable', err.message);
    }
  }

  // Run after page load
  if (document.readyState === 'complete') {
    setTimeout(analyzeCurrentPage, 2000);
  } else {
    window.addEventListener('load', () => setTimeout(analyzeCurrentPage, 2000));
  }
})();
