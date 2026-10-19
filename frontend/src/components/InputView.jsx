import React from 'react';
import {
  BoltIcon,
  CpuBoltIcon,
  GlobalIcon,
  ShieldIcon,
  StarsIcon,
  TrashBinTrashIcon,
} from '@solar-icons/react/linear';

import { normalizePastedText } from '../lib/text';
import { ShieldIllustration } from './Brand';

export const MAX_CHARS = 5000;

const FEATURES = [
  { Icon: CpuBoltIcon, title: 'AI-Powered Analysis', body: 'Understands context and finds hidden risks.' },
  { Icon: ShieldIcon, title: 'Fraud Detection Rules', body: 'Checks against known scam patterns.' },
  { Icon: GlobalIcon, title: 'External API Checks', body: 'Verifies domains, URLs and payment details.' },
  { Icon: BoltIcon, title: 'Actionable Results', body: 'Get a risk score, reasons, and next steps.' },
];

export default function InputView({ text, onTextChange, onAnalyze, loading, textareaRef }) {
  const canSubmit = !loading && text.trim().length > 0;

  const handleClear = () => {
    onTextChange('');
    textareaRef.current?.focus();
  };

  return (
    <div className="view view-home">
      <section className="hero">
        <div className="hero-copy">
          <p className="overline grad-text">FRAUD ANALYZER</p>
          <h1 className="display">
            <span className="display-line">CHECK BEFORE</span>
            <span className="display-line is-indent">
              YOU <span className="grad-text">TRUST</span>
            </span>
          </h1>
          <p className="hero-sub">
            Analyze suspicious messages, links, and payment requests using AI and real-time threat intelligence.
          </p>
        </div>
        <ShieldIllustration className="hero-illus" />
      </section>

      <form
        className="card input-card"
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) onAnalyze();
        }}
      >
        {/* One box for everything: the type (SMS, link, email, payment request) is detected from the text. */}
        <textarea
          ref={textareaRef}
          className="message-input"
          aria-label="Message, link, email, or payment request to analyze"
          placeholder="Paste a message, link, email, or payment request…"
          value={text}
          maxLength={MAX_CHARS}
          onChange={(e) => onTextChange(e.target.value)}
          onPaste={(e) => {
            const pasted = e.clipboardData.getData('text');
            const clean = normalizePastedText(pasted);
            if (clean === pasted) return; // nothing to fix: let the browser paste normally
            e.preventDefault();
            // Insert at the cursor via execCommand so the browser's undo history keeps working.
            if (!document.execCommand('insertText', false, clean)) {
              const el = e.currentTarget;
              el.setRangeText(clean, el.selectionStart, el.selectionEnd, 'end');
              onTextChange(el.value);
            }
          }}
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && canSubmit) {
              e.preventDefault();
              onAnalyze();
            }
          }}
          disabled={loading}
          spellCheck={false}
        />

        <div className="input-actions">
          <button type="button" className="btn btn-ghost" onClick={handleClear} disabled={loading || text.length === 0}>
            <TrashBinTrashIcon size={18} aria-hidden="true" />
            Clear
          </button>
          <span className="counter" aria-hidden="true">
            {text.length.toLocaleString()} / {MAX_CHARS.toLocaleString()}
          </span>
          <button type="submit" className="btn btn-analyze" disabled={!canSubmit} aria-busy={loading}>
            {loading ? <span className="spinner" aria-hidden="true" /> : <StarsIcon size={18} aria-hidden="true" />}
            {loading ? 'Analyzing…' : 'Analyze'}
          </button>
        </div>
      </form>

      <ul className="feature-grid">
        {FEATURES.map(({ Icon, title, body }) => (
          <li key={title} className="card feature-card">
            <span className="feature-icon">
              <Icon size={22} aria-hidden="true" />
            </span>
            <h3>{title}</h3>
            <p>{body}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
