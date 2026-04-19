/**
 * TruthShield — Extension Popup Script
 */

const API_URL = 'http://localhost:8000/api/v1';

function getScoreColor(score) {
  if (score >= 75) return '#10b981';
  if (score >= 55) return '#f59e0b';
  if (score >= 35) return '#f97316';
  return '#ef4444';
}

function updateUI(data) {
  const { score, verdict, url } = data;
  const color = getScoreColor(score);

  document.getElementById('result-section').style.display = 'block';
  document.getElementById('no-result').style.display = 'none';

  // Update score
  document.getElementById('score-number').textContent = score;
  document.getElementById('score-number').style.color = color;

  // Update ring
  const circumference = 2 * Math.PI * 42;
  const offset = circumference - (score / 100) * circumference;
  const circle = document.getElementById('score-circle');
  circle.style.stroke = color;
  circle.setAttribute('stroke-dashoffset', offset);

  // Update verdict
  const badge = document.getElementById('verdict-badge');
  badge.textContent = verdict;
  badge.style.color = color;
  badge.style.backgroundColor = color + '20';
  badge.style.border = `1px solid ${color}40`;

  // Update URL
  if (url) {
    document.getElementById('url-info').textContent = url;
  }
}

// Load last result from storage
chrome.storage.local.get(['lastResult'], (result) => {
  if (result.lastResult) {
    updateUI(result.lastResult);
  }
});

// Analyze button
document.getElementById('analyze-btn').addEventListener('click', async () => {
  const btn = document.getElementById('analyze-btn');
  btn.disabled = true;
  btn.textContent = '⏳ Analyzing...';

  try {
    // Get current tab URL and text
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    // Execute script to get page text
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const selectors = ['article', 'main', '[role="main"]'];
        for (const sel of selectors) {
          const el = document.querySelector(sel);
          if (el && el.innerText.length > 200) return el.innerText.substring(0, 3000);
        }
        const paragraphs = document.querySelectorAll('p');
        return Array.from(paragraphs).map(p => p.innerText).filter(t => t.length > 50).join('\n').substring(0, 3000);
      }
    });

    const pageText = results[0]?.result || '';

    if (!pageText) {
      btn.textContent = '❌ No article text found';
      setTimeout(() => { btn.textContent = '🔍 Analyze This Page'; btn.disabled = false; }, 2000);
      return;
    }

    const formData = new FormData();
    formData.append('text', pageText);
    formData.append('url', tab.url);
    formData.append('lang', 'en');

    const response = await fetch(`${API_URL}/analyze`, { method: 'POST', body: formData });

    if (response.ok) {
      const data = await response.json();
      const result = {
        score: data.credibility?.trust_score ?? 50,
        verdict: data.credibility?.verdict ?? 'Unknown',
        url: tab.url,
        reportId: data.id,
      };
      chrome.storage.local.set({ lastResult: result });
      updateUI(result);
      btn.textContent = '✅ Analysis Complete';
    } else {
      btn.textContent = '❌ Analysis Failed';
    }
  } catch (err) {
    console.error('Analysis error:', err);
    btn.textContent = '❌ Backend unreachable';
  }

  setTimeout(() => { btn.textContent = '🔍 Analyze This Page'; btn.disabled = false; }, 3000);
});
