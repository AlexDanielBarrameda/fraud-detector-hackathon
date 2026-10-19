import React, { useRef } from 'react';
import {
  CloseCircleIcon,
  CpuBoltIcon,
  GlobalIcon,
  ListCheckIcon,
  MoonIcon,
  QuestionCircleIcon,
  ServerIcon,
  ShieldCheckIcon,
  SunIcon,
} from '@solar-icons/react/linear';

import { HexMesh, LogoMark, Wordmark } from './Brand';

const LAYERS = [
  { Icon: ListCheckIcon, name: 'Fraud detection rules', detail: '15 weighted patterns in English and Taglish: OTP/MPIN requests, lookalike domains, fee and crypto asks, family-emergency stories, prompt injection.' },
  { Icon: GlobalIcon, name: 'Google Safe Browsing', detail: 'Every link is checked live against Google’s malware and phishing lists.' },
  { Icon: ServerIcon, name: 'Domain age (RDAP)', detail: 'Looks up when each linked domain was registered. Domains under 30 days old are a strong scam signal.' },
  { Icon: CpuBoltIcon, name: 'Gemini AI analysis', detail: 'Reads the message plus all the evidence above and returns a structured verdict, with a 3-model failover.' },
];

function HelpDialog({ dialogRef }) {
  return (
    <dialog ref={dialogRef} className="help-dialog" aria-labelledby="help-title" onClick={(e) => e.target === e.currentTarget && e.currentTarget.close()}>
      <div className="help-body">
        <div className="help-head">
          <h2 id="help-title">How Fraud Analyzer scores a message</h2>
          <button type="button" className="icon-btn" onClick={() => dialogRef.current?.close()} aria-label="Close help">
            <CloseCircleIcon size={22} aria-hidden="true" />
          </button>
        </div>
        <p className="help-lead">Four independent layers check every message, so no single one can be fooled into calling a scam safe.</p>
        <ol className="help-layers">
          {LAYERS.map(({ Icon, name, detail }, i) => (
            <li key={name}>
              <span className="help-layer-icon">
                <Icon size={20} aria-hidden="true" />
              </span>
              <span>
                <strong>
                  {i + 1}. {name}
                </strong>
                <span className="help-layer-detail">{detail}</span>
              </span>
            </li>
          ))}
        </ol>
        <div className="help-formula">
          <h3>Final score</h3>
          <p>
            The rule and AI scores are blended, and verified evidence sets a minimum: a Google Safe Browsing match means at
            least 90, an OTP/MPIN request with a link at least 85, a domain under 30 days old at least 70.
          </p>
          <p className="help-scale">
            <span className="pill pill-low">Low 0–29</span>
            <span className="pill pill-medium">Medium 30–59</span>
            <span className="pill pill-high">High 60–84</span>
            <span className="pill pill-critical">Critical 85–100</span>
          </p>
        </div>
      </div>
    </dialog>
  );
}

function ThemeSwitch({ theme, onToggle }) {
  const dark = theme === 'dark';
  return (
    <button type="button" role="switch" aria-checked={dark} aria-label="Dark mode" className="theme-switch" onClick={onToggle}>
      <SunIcon size={16} className="theme-switch-sun" aria-hidden="true" />
      <span className="theme-switch-track" aria-hidden="true">
        <span className="theme-switch-knob" />
      </span>
      <MoonIcon size={16} className="theme-switch-moon" aria-hidden="true" />
    </button>
  );
}

export default function Header({ theme, onToggleTheme, onHome }) {
  const helpRef = useRef(null);
  return (
    <header className="site-header">
      <HexMesh />
      <div className="header-inner">
        <a
          className="brand"
          href="/"
          aria-label="Fraud Analyzer home"
          onClick={(e) => {
            // Plain click: go home in-app (no reload). Ctrl/Cmd/middle-click still open a new tab.
            if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
            e.preventDefault();
            onHome();
          }}
        >
          <LogoMark size={50} />
          <Wordmark />
        </a>
        <div className="header-actions">
          <button type="button" className="help-btn" onClick={() => helpRef.current?.showModal()}>
            <QuestionCircleIcon size={16} aria-hidden="true" />
            <span className="help-label">Help</span>
          </button>
          <ThemeSwitch theme={theme} onToggle={onToggleTheme} />
          <span className="tagline">
            <ShieldCheckIcon size={30} className="tagline-icon" aria-hidden="true" />
            <span>
              Smarter analysis
              <br />
              Safer transactions
            </span>
          </span>
        </div>
      </div>
      <HelpDialog dialogRef={helpRef} />
    </header>
  );
}
