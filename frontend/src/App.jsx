import React, { useRef, useState } from 'react';
import { CpuBoltIcon, DangerCircleIcon, GlobalIcon, ListCheckIcon, ServerIcon } from '@solar-icons/react/linear';

import { analyzeText } from './api/client';
import { ShieldIllustration } from './components/Brand';
import Header from './components/Header';
import InputView from './components/InputView';
import ResultView from './components/ResultView';
import Sidebar from './components/Sidebar';
import { addEntry, detectKind, loadHistory, makeEntry, saveHistory } from './lib/history';
import { normalizePastedText } from './lib/text';
import { useTheme } from './lib/theme';

// Only show the scanning state if a request is actually slow; cached results swap in with no flash.
const PENDING_DELAY_MS = 150;

const LAYERS = [
  { Icon: ListCheckIcon, name: 'Fraud detection rules' },
  { Icon: GlobalIcon, name: 'Google Safe Browsing' },
  { Icon: ServerIcon, name: 'Domain age (RDAP)' },
  { Icon: CpuBoltIcon, name: 'Gemini AI analysis' },
];

function PendingView() {
  return (
    <div className="view view-pending" role="status">
      <ShieldIllustration className="pending-illus" />
      <h1 className="display is-result">
        ANALYZING<span className="grad-text">…</span>
      </h1>
      <p className="hero-sub">Running every detection layer. Cached messages return instantly.</p>
      <ul className="pending-layers">
        {LAYERS.map(({ Icon, name }, i) => (
          <li key={name} style={{ '--i': i }}>
            <Icon size={20} aria-hidden="true" />
            {name}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function App() {
  const [theme, toggleTheme] = useTheme();
  const [view, setView] = useState('home'); // 'home' | 'result'
  const [text, setText] = useState('');
  const [current, setCurrent] = useState(null); // { entry, fromHistory }
  const [history, setHistory] = useState(loadHistory);
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  const latestRequest = useRef(0);
  const pendingTimer = useRef(null);
  const mainRef = useRef(null);
  const textareaRef = useRef(null);

  const updateHistory = (updater) =>
    setHistory((prev) => {
      const next = updater(prev);
      saveHistory(next);
      return next;
    });

  const showTop = () => mainRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const analyze = async (messageText, kind) => {
    if (!messageText.trim()) return;
    // Ignore responses from superseded requests (e.g. two sample clicks in a row).
    const requestId = ++latestRequest.current;
    setLoading(true);
    setError(null);
    clearTimeout(pendingTimer.current);
    pendingTimer.current = setTimeout(() => {
      if (requestId === latestRequest.current) setPending(true);
    }, PENDING_DELAY_MS);

    try {
      const result = await analyzeText(messageText);
      if (requestId !== latestRequest.current) return;
      const entry = makeEntry(messageText, kind, result);
      updateHistory((prev) => addEntry(prev, entry));
      setCurrent({ entry, fromHistory: false });
      setView('result');
      showTop();
    } catch (err) {
      if (requestId === latestRequest.current) setError(err.message || 'Analysis failed.');
    } finally {
      if (requestId === latestRequest.current) {
        clearTimeout(pendingTimer.current);
        setLoading(false);
        setPending(false);
      }
    }
  };

  const handleAnalyze = () => {
    // Catch Markdown links that were typed or slipped past the paste handler.
    const clean = normalizePastedText(text);
    if (clean !== text) setText(clean);
    analyze(clean, detectKind(clean));
  };

  const handleSample = (sample) => {
    setText(sample.text);
    analyze(sample.text, detectKind(sample.text));
  };

  const handleOpenScan = (entry) => {
    if (entry.result) {
      latestRequest.current += 1; // cancel any in-flight request's UI updates
      setError(null);
      setCurrent({ entry, fromHistory: true });
      setView('result');
      showTop();
    } else {
      // Seed entries have no stored result yet: run the real analysis.
      setText(entry.text);
      analyze(entry.text, entry.kind);
    }
  };

  const handleNewScan = () => {
    setView('home');
    setText('');
    setError(null);
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  // Logo click: back to the input view, keeping anything already typed.
  const handleHome = () => {
    setView('home');
    setError(null);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="app">
      <Header theme={theme} onToggleTheme={toggleTheme} onHome={handleHome} />

      <main className="layout">
        <div className="main-col" ref={mainRef} aria-live="polite" aria-busy={loading}>
          {error && (
            <div className="error-banner" role="alert">
              <DangerCircleIcon size={20} aria-hidden="true" />
              <span>{error}</span>
            </div>
          )}

          {pending ? (
            <PendingView />
          ) : view === 'result' && current ? (
            <ResultView key={current.entry.id} entry={current.entry} fromHistory={current.fromHistory} onNewScan={handleNewScan} />
          ) : (
            <InputView
              text={text}
              onTextChange={setText}
              onAnalyze={handleAnalyze}
              loading={loading}
              textareaRef={textareaRef}
            />
          )}
        </div>

        <Sidebar
          history={history}
          activeId={view === 'result' ? current?.entry.id : null}
          onSample={handleSample}
          onOpenScan={handleOpenScan}
          onClearHistory={() => updateHistory(() => [])}
          busy={loading}
        />
      </main>
    </div>
  );
}
