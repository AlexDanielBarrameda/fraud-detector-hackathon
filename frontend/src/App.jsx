import React, { useCallback, useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import {
  CpuBoltIcon,
  DangerCircleIcon,
  GlobalIcon,
  InfoCircleIcon,
  ListCheckIcon,
  MoonIcon,
  ServerIcon,
  ShieldKeyholeIcon,
  SunIcon,
} from '@solar-icons/react/linear';

import { analyzeText, checkHealth } from './api/client';
import ActionList from './components/ActionList';
import InputBox from './components/InputBox';
import RedFlagList from './components/RedFlagList';
import RiskGauge from './components/RiskGauge';

// Only show a pending state if the request is actually slow; cached results swap in with no flash.
const PENDING_DELAY_MS = 150;

const LAYERS = [
  { Icon: ListCheckIcon, name: 'Heuristic rules', detail: '15 weighted patterns, English and Taglish' },
  { Icon: GlobalIcon, name: 'Google Safe Browsing', detail: 'Live malware and phishing lookup' },
  { Icon: ServerIcon, name: 'RDAP domain age', detail: 'Flags domains registered under 30 days ago' },
  { Icon: CpuBoltIcon, name: 'Gemini analysis', detail: 'Structured verdict with 3-model failover' },
];

function StandbyPanel({ pending }) {
  return (
    <section className={`panel standby ${pending ? 'is-pending' : ''}`} aria-labelledby="standby-heading">
      <div className="standby-head">
        <h2 id="standby-heading">{pending ? 'Analyzing message' : 'No analysis yet'}</h2>
        <p>
          {pending
            ? 'Running every detection layer. Cached messages return instantly.'
            : 'Paste a suspicious SMS, chat, or email, or run a test vector.'}
        </p>
      </div>
      <ol className="layer-list">
        {LAYERS.map(({ Icon, name, detail }, i) => (
          <li key={name} className="layer" style={{ '--i': i }}>
            <span className="layer-index">{String(i + 1).padStart(2, '0')}</span>
            <Icon size={18} className="layer-icon" aria-hidden="true" />
            <span className="layer-text">
              <span className="layer-name">{name}</span>
              <span className="layer-detail">{detail}</span>
            </span>
            {pending && <span className="layer-scan" aria-hidden="true" />}
          </li>
        ))}
      </ol>
    </section>
  );
}

const THEME_COLORS = { dark: '#08090a', light: '#f5f5f6' };

// Liquid-drop reveal: the mask is a radial gradient with a feathered rim (opaque to 90% of the radius,
// fading to 100%), so the edge reads like spreading ink rather than a hard circle.
const WAVE_DURATION_MS = 700;
const WAVE_EASING = 'cubic-bezier(0.65, 0, 0.35, 1)';
const WAVE_SOLID_FRACTION = 0.9;

function applyThemeToDocument(theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLORS[theme]);
}

/**
 * Switches theme with a drop that spreads from (x, y). Uses the View Transitions API: the browser
 * snapshots the old page, we apply the new theme, then grow a soft-edged mask over the new snapshot.
 * Falls back to an instant switch where the API is unavailable, and to a short crossfade under reduced motion.
 */
function switchThemeWithWave(next, x, y, commit) {
  const update = () => {
    applyThemeToDocument(next);
    flushSync(commit);
  };

  if (!document.startViewTransition) {
    update();
    return;
  }

  const root = document.documentElement;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  root.classList.add(reduceMotion ? 'theme-fade' : 'theme-wave');
  const transition = document.startViewTransition(update);
  transition.finished.finally(() => root.classList.remove('theme-wave', 'theme-fade'));
  if (reduceMotion) return;

  transition.ready.then(() => {
    // Final mask must cover the farthest viewport corner with its solid (unfeathered) part.
    const reach = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    const size = (2 * reach) / WAVE_SOLID_FRACTION;
    root.animate(
      {
        maskSize: ['0px 0px', `${size}px ${size}px`],
        maskPosition: [`${x}px ${y}px`, `${x - size / 2}px ${y - size / 2}px`],
      },
      { duration: WAVE_DURATION_MS, easing: WAVE_EASING, fill: 'both', pseudoElement: '::view-transition-new(root)' },
    );
  });
}

/** Dark/light theme: starts from what index.html set before paint; follows the OS until the user picks. */
function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'dark');

  useEffect(() => {
    applyThemeToDocument(theme);
  }, [theme]);

  useEffect(() => {
    let saved = null;
    try {
      saved = localStorage.getItem('theme');
    } catch {
      /* storage blocked: just follow the OS */
    }
    if (saved) return undefined;
    const media = window.matchMedia('(prefers-color-scheme: light)');
    const follow = (e) => setTheme(e.matches ? 'light' : 'dark');
    media.addEventListener('change', follow);
    return () => media.removeEventListener('change', follow);
  }, []);

  const toggle = (event) => {
    const next = theme === 'dark' ? 'light' : 'dark';
    try {
      localStorage.setItem('theme', next);
    } catch {
      /* not persisted; still switches for this session */
    }
    // The drop starts at the centre of the toggle button (works for mouse and keyboard activation).
    const rect = event.currentTarget.getBoundingClientRect();
    switchThemeWithWave(next, rect.left + rect.width / 2, rect.top + rect.height / 2, () => setTheme(next));
  };

  return [theme, toggle];
}

function ThemeToggle({ theme, onToggle }) {
  const next = theme === 'dark' ? 'light' : 'dark';
  return (
    <button type="button" className="theme-toggle" onClick={onToggle} aria-label={`Switch to ${next} theme`} title={`Switch to ${next} theme`}>
      {theme === 'dark' ? <SunIcon size={17} aria-hidden="true" /> : <MoonIcon size={17} aria-hidden="true" />}
    </button>
  );
}

function EngineStatus({ status }) {
  const label = { checking: 'Connecting', online: 'Engine online', offline: 'Engine offline' }[status];
  return (
    <span className={`engine-status is-${status}`} role="status">
      <span className="engine-dot" aria-hidden="true" />
      {label}
    </span>
  );
}

export default function App() {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null); // { data, id }
  const [engine, setEngine] = useState('checking');
  const [theme, toggleTheme] = useTheme();
  const latestRequest = useRef(0);
  const pendingTimer = useRef(null);
  const resultsRef = useRef(null);

  const refreshEngine = useCallback(async () => {
    setEngine((await checkHealth()) ? 'online' : 'offline');
  }, []);

  useEffect(() => {
    refreshEngine();
  }, [refreshEngine]);

  const analyze = async (messageText) => {
    if (!messageText.trim()) return;
    // Ignore responses from superseded requests (e.g. two test-vector clicks in a row).
    const requestId = ++latestRequest.current;
    setLoading(true);
    setError(null);
    clearTimeout(pendingTimer.current);
    pendingTimer.current = setTimeout(() => {
      if (requestId === latestRequest.current) setPending(true);
    }, PENDING_DELAY_MS);

    try {
      const data = await analyzeText(messageText);
      if (requestId === latestRequest.current) {
        setResult({ data, id: requestId });
        setEngine('online');
      }
    } catch (err) {
      if (requestId === latestRequest.current) {
        setError(err.message || 'Analysis failed.');
        refreshEngine();
      }
    } finally {
      if (requestId === latestRequest.current) {
        clearTimeout(pendingTimer.current);
        setLoading(false);
        setPending(false);
      }
    }
  };

  const handlePreset = (presetText) => {
    setText(presetText);
    analyze(presetText);
  };

  const handleClear = () => {
    setText('');
    setResult(null);
    setError(null);
  };

  // On stacked (narrow) layouts, bring the verdict into view once it arrives.
  useEffect(() => {
    if (result && window.matchMedia('(max-width: 1099px)').matches) {
      resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [result]);

  const data = result?.data;
  const showResult = data && !pending;

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <ShieldKeyholeIcon size={22} className="brand-mark" aria-hidden="true" />
            <span className="brand-name">Fraud Analyzer</span>
            <span className="brand-sep" aria-hidden="true" />
            <span className="brand-tag">Hybrid scam &amp; fraud detection</span>
          </div>
          <div className="topbar-actions">
            <EngineStatus status={engine} />
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
          </div>
        </div>
      </header>

      <main className="workspace">
        <div className="col-input">
          <InputBox
            value={text}
            onChange={setText}
            onSubmit={() => analyze(text)}
            onClear={handleClear}
            onPreset={handlePreset}
            loading={loading}
          />
        </div>

        <div className="col-results" ref={resultsRef} aria-live="polite" aria-busy={loading}>
          {error && (
            <div className="error-banner" role="alert">
              <DangerCircleIcon size={18} aria-hidden="true" />
              <span>{error}</span>
            </div>
          )}

          {showResult ? (
            <article
              key={result.id}
              className={`panel report risk-${data.risk_level.toLowerCase()}`}
              aria-label={`Analysis result: ${data.risk_level} risk, score ${data.final_score}`}
            >
              <p className="report-notice">
                <InfoCircleIcon size={15} aria-hidden="true" />
                <span>
                  Disclaimer: This tool provides an automated risk indicator combining heuristic rules, threat
                  intelligence, and AI analysis—not a guarantee of safety. Never share your OTP, MPIN, or
                  passwords.
                </span>
              </p>
              <RiskGauge result={data} />
              <div className="report-body">
                <RedFlagList result={data} />
                <ActionList actions={data.recommended_actions} />
              </div>
            </article>
          ) : (
            !error && <StandbyPanel pending={pending} />
          )}
        </div>
      </main>
    </div>
  );
}
