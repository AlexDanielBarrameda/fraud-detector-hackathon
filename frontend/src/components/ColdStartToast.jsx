import React, { useEffect, useState } from 'react';
import { CheckCircleIcon, CloseCircleIcon, ServerSquareUpdateIcon } from '@solar-icons/react/linear';

const EXIT_MS = 240;

function useElapsedSeconds(startedAt, running) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return undefined;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [running, startedAt]);
  return Math.max(0, Math.floor((now - startedAt) / 1000));
}

/**
 * Floating notice shown while a free-tier server boots during a scan. Stays mounted briefly after
 * `open` turns false so it can animate out instead of vanishing.
 */
export default function ColdStartToast({ open, startedAt, serverAwake, onDismiss }) {
  const [mounted, setMounted] = useState(open);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    if (open) {
      setMounted(true);
      setLeaving(false);
      return undefined;
    }
    if (!mounted) return undefined;
    setLeaving(true);
    const id = setTimeout(() => {
      setMounted(false);
      setLeaving(false);
    }, EXIT_MS);
    return () => clearTimeout(id);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const elapsed = useElapsedSeconds(startedAt, mounted && !leaving);
  if (!mounted) return null;

  const steps = [
    { label: 'Waking up the server', done: serverAwake, active: !serverAwake },
    { label: 'Analyzing your message', done: false, active: serverAwake },
  ];

  return (
    <aside className={`cold-toast ${leaving ? 'is-leaving' : ''}`} role="status" aria-live="polite" aria-labelledby="cold-toast-title">
      <span className="cold-toast-icon" aria-hidden="true">
        <ServerSquareUpdateIcon size={24} />
      </span>
      <div className="cold-toast-body">
        <div className="cold-toast-head">
          <h2 id="cold-toast-title">Waking up server…</h2>
          <span className="cold-toast-timer" aria-label={`${elapsed} seconds elapsed`}>
            {elapsed}s
          </span>
        </div>
        <p>
          Our cloud server went to sleep due to inactivity. Starting it back up—your analysis will finish in about
          20–40 seconds.
        </p>
        <ol className="cold-toast-steps">
          {steps.map(({ label, done, active }) => (
            <li key={label} className={done ? 'is-done' : active ? 'is-active' : ''}>
              {done ? <CheckCircleIcon size={16} aria-hidden="true" /> : <span className="cold-toast-dot" aria-hidden="true" />}
              {label}
              {done && <span className="visually-hidden"> (done)</span>}
            </li>
          ))}
        </ol>
        <div className="cold-toast-bar" aria-hidden="true">
          <span />
        </div>
      </div>
      <button type="button" className="cold-toast-close" onClick={onDismiss} aria-label="Dismiss">
        <CloseCircleIcon size={20} aria-hidden="true" />
      </button>
    </aside>
  );
}
