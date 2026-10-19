import React, { useRef } from 'react';
import {
  AltArrowRightIcon,
  ChatRoundDotsIcon,
  ClockCircleIcon,
  CloseCircleIcon,
  DangerCircleIcon,
  DangerTriangleIcon,
  DocumentTextIcon,
  InfoCircleIcon,
  LetterIcon,
  LinkIcon,
  ShieldCheckIcon,
  StarsIcon,
  TrashBinTrashIcon,
} from '@solar-icons/react/linear';

import PRESET_DATA from '../data/presets.json';
import { formatStamp } from '../lib/history';

// Icon + tint per sample (tints match the mockup: red, slate, yellow, slate, green).
const SAMPLE_STYLE = {
  gcash: { Icon: LetterIcon, tone: 'red' },
  'safe-browsing': { Icon: LinkIcon, tone: 'slate' },
  family: { Icon: LetterIcon, tone: 'yellow' },
  injection: { Icon: DocumentTextIcon, tone: 'slate' },
  legit: { Icon: ChatRoundDotsIcon, tone: 'green' },
};

const KIND_ICONS = {
  sms: ChatRoundDotsIcon,
  link: LinkIcon,
  email: LetterIcon,
  payment: DocumentTextIcon,
  message: LetterIcon,
};

const RISK_ICONS = {
  Critical: DangerTriangleIcon,
  High: DangerCircleIcon,
  Medium: InfoCircleIcon,
  Low: ShieldCheckIcon,
};

export function RiskPill({ level, size = 'sm' }) {
  const Icon = RISK_ICONS[level] ?? InfoCircleIcon;
  return (
    <span className={`pill pill-${level.toLowerCase()} pill-${size}`}>
      <Icon size={size === 'sm' ? 11 : 13} aria-hidden="true" />
      {level}
    </span>
  );
}

function ScanRow({ entry, onOpen, active }) {
  const Icon = KIND_ICONS[entry.kind] ?? LetterIcon;
  return (
    <li>
      <button type="button" className={`row-card scan-row ${active ? 'is-active' : ''}`} onClick={() => onOpen(entry)}>
        <span className="row-icon tone-neutral">
          <Icon size={22} aria-hidden="true" />
        </span>
        <span className="row-text">
          <span className="row-title-line">
            <span className="row-title">{entry.title}</span>
            <RiskPill level={entry.risk_level} />
          </span>
          <span className="row-sub">{formatStamp(entry.ts)}</span>
        </span>
        <AltArrowRightIcon size={18} className="row-chevron" aria-hidden="true" />
      </button>
    </li>
  );
}

export default function Sidebar({ history, activeId, onSample, onOpenScan, onClearHistory, busy }) {
  const allRef = useRef(null);
  const openAndClose = (entry) => {
    allRef.current?.close();
    onOpenScan(entry);
  };

  return (
    <aside className="sidebar" aria-label="Samples and recent scans">
      <section className="card side-card" aria-labelledby="samples-title">
        <div className="side-head">
          <StarsIcon size={22} className="side-head-icon" aria-hidden="true" />
          <div>
            <h2 id="samples-title">Try a sample</h2>
            <p>Use these examples to see how it works</p>
          </div>
        </div>
        <ul className="row-list">
          {PRESET_DATA.map((p) => {
            const { Icon, tone } = SAMPLE_STYLE[p.id] ?? SAMPLE_STYLE.legit;
            return (
              <li key={p.id}>
                <button type="button" className="row-card" onClick={() => onSample(p)} disabled={busy}>
                  <span className={`row-icon tone-${tone}`}>
                    <Icon size={22} aria-hidden="true" />
                  </span>
                  <span className="row-text">
                    <span className="row-title">{p.label}</span>
                    <span className="row-sub">{p.hint}</span>
                  </span>
                  <AltArrowRightIcon size={18} className="row-chevron" aria-hidden="true" />
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="card side-card" aria-labelledby="recent-title">
        <div className="side-head is-row">
          <ClockCircleIcon size={22} className="side-head-icon" aria-hidden="true" />
          <h2 id="recent-title">Recent Scans</h2>
          {history.length > 0 && (
            <button type="button" className="link-btn" onClick={() => allRef.current?.showModal()}>
              View all →
            </button>
          )}
        </div>
        {history.length === 0 ? (
          <p className="empty-note">Your scans will appear here.</p>
        ) : (
          <ul className="row-list">
            {history.slice(0, 4).map((entry) => (
              <ScanRow key={entry.id} entry={entry} onOpen={onOpenScan} active={entry.id === activeId} />
            ))}
          </ul>
        )}
      </section>

      <dialog
        ref={allRef}
        className="history-dialog"
        aria-labelledby="history-title"
        onClick={(e) => e.target === e.currentTarget && e.currentTarget.close()}
      >
        <div className="help-body">
          <div className="help-head">
            <h2 id="history-title">All recent scans</h2>
            <button type="button" className="icon-btn" onClick={() => allRef.current?.close()} aria-label="Close">
              <CloseCircleIcon size={22} aria-hidden="true" />
            </button>
          </div>
          <ul className="row-list history-list">
            {history.map((entry) => (
              <ScanRow key={entry.id} entry={entry} onOpen={openAndClose} active={entry.id === activeId} />
            ))}
          </ul>
          <button
            type="button"
            className="btn btn-ghost clear-btn"
            onClick={() => {
              onClearHistory();
              allRef.current?.close();
            }}
          >
            <TrashBinTrashIcon size={16} aria-hidden="true" />
            Clear history
          </button>
        </div>
      </dialog>
    </aside>
  );
}
