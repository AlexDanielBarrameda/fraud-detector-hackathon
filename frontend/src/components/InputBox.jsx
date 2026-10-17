import React from 'react';
import {
  BugIcon,
  CheckCircleIcon,
  GlobalIcon,
  ShieldKeyholeIcon,
  TrashBinTrashIcon,
  UsersGroupRoundedIcon,
  WalletIcon,
} from '@solar-icons/react/linear';

import PRESET_DATA from '../data/presets.json';

export const MAX_CHARS = 5000;

const PRESET_ICONS = {
  gcash: WalletIcon,
  'safe-browsing': GlobalIcon,
  family: UsersGroupRoundedIcon,
  injection: BugIcon,
  legit: CheckCircleIcon,
};

// One-click test vectors. The texts live in presets.json so backend/warmup_demo.py
// pre-caches exactly the same messages.
export const PRESETS = PRESET_DATA.map((p) => ({ ...p, Icon: PRESET_ICONS[p.id] ?? CheckCircleIcon }));

export default function InputBox({ value, onChange, onSubmit, onClear, onPreset, loading }) {
  const canSubmit = !loading && value.trim().length > 0;
  const activePreset = PRESETS.find((p) => p.text === value)?.id;

  const handleKeyDown = (e) => {
    // Ctrl/Cmd + Enter submits, so a demo can run without reaching for the mouse.
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && canSubmit) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <section className="panel console" aria-labelledby="message-label">
      <form
        className="console-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) onSubmit();
        }}
      >
        <div className="section-head">
          <label id="message-label" htmlFor="message-input" className="eyebrow">
            Message
          </label>
          <span className={`counter ${value.length > MAX_CHARS * 0.9 ? 'is-near-limit' : ''}`} aria-live="off">
            {value.length.toLocaleString()}
            <span className="counter-max"> / {MAX_CHARS.toLocaleString()}</span>
          </span>
        </div>

        <textarea
          id="message-input"
          className="message-input"
          rows={8}
          maxLength={MAX_CHARS}
          placeholder="Paste the SMS, chat, or email you received…"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          spellCheck={false}
        />

        <div className="console-actions">
          <button
            type="button"
            className="btn btn-quiet"
            onClick={onClear}
            disabled={loading || value.length === 0}
          >
            <TrashBinTrashIcon size={16} aria-hidden="true" />
            Clear
          </button>
          <button type="submit" className="btn btn-primary" disabled={!canSubmit} aria-busy={loading}>
            {loading ? (
              <>
                <span className="spinner" aria-hidden="true" />
                Analyzing…
              </>
            ) : (
              <>
                <ShieldKeyholeIcon size={18} aria-hidden="true" />
                Analyze message
                <kbd className="kbd-hint" aria-hidden="true">
                  Ctrl ↵
                </kbd>
              </>
            )}
          </button>
        </div>
      </form>

      <div className="vectors">
        <div className="section-head">
          <h2 className="eyebrow">Test vectors</h2>
          <span className="section-meta">{PRESETS.length} samples</span>
        </div>
        <ul className="vector-list">
          {PRESETS.map(({ id, label, hint, tag, tone, Icon }, i) => (
            <li key={id}>
              <button
                type="button"
                className={`vector tone-${tone}`}
                onClick={() => onPreset(PRESET_DATA[i].text)}
                disabled={loading}
                aria-pressed={activePreset === id}
              >
                <span className="vector-index" aria-hidden="true">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <Icon size={18} className="vector-icon" aria-hidden="true" />
                <span className="vector-text">
                  <span className="vector-label">{label}</span>
                  <span className="vector-hint">{hint}</span>
                </span>
                <span className="vector-tag">
                  <span className="tag-dot" aria-hidden="true" />
                  {tag}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
