import React, { useEffect, useState } from 'react';
import {
  ArrowLeftIcon,
  BoltIcon,
  BugIcon,
  CalendarIcon,
  CheckCircleIcon,
  ClockCircleIcon,
  CpuBoltIcon,
  DangerCircleIcon,
  DangerTriangleIcon,
  DocumentIcon,
  GiftIcon,
  GlobalIcon,
  InfoCircleIcon,
  KeyIcon,
  LinkIcon,
  MagnifierIcon,
  RadarIcon,
  RestartIcon,
  ScannerIcon,
  ShieldCheckIcon,
  ShieldIcon,
  UserIdIcon,
  WalletIcon,
} from '@solar-icons/react/linear';

import { formatStamp, KIND_LABELS } from '../lib/history';
import { ShieldIllustration } from './Brand';
import { RiskPill } from './Sidebar';

const LEVELS = {
  Critical: { Icon: DangerTriangleIcon, title: 'Critical Risk', summary: 'Scam or phishing attempt' },
  High: { Icon: DangerCircleIcon, title: 'High Risk', summary: 'Likely a scam' },
  Medium: { Icon: InfoCircleIcon, title: 'Medium Risk', summary: 'Suspicious. Verify before you act' },
  Low: { Icon: ShieldCheckIcon, title: 'Low Risk', summary: 'No strong scam indicators' },
};

// Each backend red flag is one sentence; give it a category title and icon by keyword (first match wins).
const INDICATORS = [
  { test: /inject|instructions|manipulat|rewrite|tamper|score 0|jailbreak/i, Icon: BugIcon, title: 'Manipulation attempt' },
  { test: /registered only|newly registered|domain age/i, Icon: CalendarIcon, title: 'Newly registered domain' },
  { test: /\botp\b|mpin|\bpin\b|password|credential|cvv|login details|one-time/i, Icon: KeyIcon, title: 'Requests sensitive credentials' },
  { test: /impersonat|pretend|claims to be|posing as|new number|family member|relative/i, Icon: UserIdIcon, title: 'Impersonation' },
  { test: /link|url|domain|website|https?:/i, Icon: LinkIcon, title: 'Suspicious link' },
  // Money before urgency: "requests immediate money transfer" is a money ask first.
  { test: /send(ing)? (money|funds)|transfer|\bfees?\b|payment|money|₱|php ?\d|\bload\b|crypto|usdt|gift card/i, Icon: WalletIcon, title: 'Money request' },
  { test: /urgen|suspen|immediate|hour|deadline|pressure|lock|expire|threat|panic/i, Icon: ClockCircleIcon, title: 'Urgency or threat' },
  { test: /prize|\bwon\b|raffle|reward|free |too good/i, Icon: GiftIcon, title: 'Too-good-to-be-true offer' },
];

function classify(flag, verified) {
  if (verified.has(flag)) return { Icon: RadarIcon, title: 'Verified threat intelligence', verified: true };
  return INDICATORS.find((i) => i.test.test(flag)) ?? { Icon: DangerCircleIcon, title: 'Scam indicator' };
}

/** Bold the opening sentence (the verdict), keep the rest regular. */
function Explanation({ text }) {
  const match = text.match(/^(.+?[.!?])(\s+[\s\S]*)?$/);
  if (!match) return <p className="assessment">{text}</p>;
  return (
    <p className="assessment">
      <strong>{match[1]}</strong>
      {match[2]}
    </p>
  );
}

function useCountUp(target, duration = 700) {
  const reduce = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const [value, setValue] = useState(() => (reduce() ? target : 0));
  useEffect(() => {
    if (reduce()) {
      setValue(target);
      return undefined;
    }
    let frame;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      setValue(Math.round(target * (1 - Math.pow(1 - t, 4))));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);
  return value;
}

function RiskBanner({ result }) {
  const { final_score: score, risk_level: level } = result;
  const { Icon, title, summary } = LEVELS[level] ?? LEVELS.Medium;
  const shown = useCountUp(score);
  const [filled, setFilled] = useState(false);
  useEffect(() => {
    const frame = requestAnimationFrame(() => setFilled(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <section className={`risk-banner risk-${level.toLowerCase()}`} aria-label={`${title}, score ${score} out of 100`}>
      <div className="risk-id">
        <Icon size={56} className="risk-icon" aria-hidden="true" />
        <div>
          <h2 className="risk-title">{title}</h2>
          <p className="risk-summary">{summary}</p>
        </div>
      </div>
      <div className="risk-score">
        <p className="risk-number" aria-hidden="true">
          {shown}
          <span> / 100</span>
        </p>
        <div className="risk-bar" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={score} aria-label="Risk score">
          <span style={{ transform: `scaleX(${filled ? score / 100 : 0})` }} />
        </div>
      </div>
      <span className="risk-corner">
        <RiskPill level={level} />
      </span>
    </section>
  );
}

function MetricCard({ Icon, label, value, muted }) {
  return (
    <div className={`card metric ${muted ? 'is-muted' : ''}`}>
      <span className="metric-label">
        <Icon size={20} aria-hidden="true" />
        {label}
      </span>
      <span className="metric-value">{value}</span>
    </div>
  );
}

function FraudAnalysisCard({ result }) {
  const ext = result.external_checks ?? {};
  const verified = new Set([...(ext.safe_browsing_threats ?? []), ...(ext.domain_flags ?? [])]);
  const flags = result.red_flags ?? [];
  const { Icon } = LEVELS[result.risk_level] ?? LEVELS.Medium;
  const aiNote = (ext.skipped_checks ?? []).find((n) => n.startsWith('AI analysis'));

  return (
    <section className={`card forensic-card risk-${result.risk_level.toLowerCase()}`} aria-labelledby="fa-title">
      <h3 id="fa-title" className="card-title">
        <Icon size={20} className="card-title-icon" aria-hidden="true" />
        1. Fraud Analysis
      </h3>
      <div className="sub-head">
        <span>Assessment</span>
        <span className="sub-meta">{result.llm_used ? result.llm_model : 'Rules engine'}</span>
      </div>
      <Explanation text={result.explanation} />
      {aiNote && <p className="inline-note">{aiNote}</p>}

      <div className="sub-head is-spaced">
        <span>Detected Fraud Indicators</span>
        {flags.length > 0 && (
          <span className={`count-pill risk-${result.risk_level.toLowerCase()}`}>
            {flags.length} finding{flags.length > 1 ? 's' : ''}
          </span>
        )}
      </div>
      {flags.length === 0 ? (
        <p className="clear-pill">
          <CheckCircleIcon size={20} aria-hidden="true" />
          No fraud indicators detected
        </p>
      ) : (
        <ul className="indicator-list">
          {flags.map((flag) => {
            const { Icon: FlagIcon, title, verified: isVerified } = classify(flag, verified);
            return (
              <li key={flag} className={isVerified ? 'is-verified' : ''}>
                <FlagIcon size={20} className="indicator-icon" aria-hidden="true" />
                <div>
                  <p className="indicator-title">
                    {title}
                    {isVerified && <span className="verified-tag">Verified</span>}
                  </p>
                  <p className="indicator-text">{flag}</p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/** Per-domain intelligence derived only from what the backend actually verified. */
function DomainIntel({ result }) {
  const ext = result.external_checks ?? {};
  const domains = (result.extracted_entities?.domains ?? []).slice(0, 3);
  if (!domains.length) return null;
  const skipped = ext.skipped_checks ?? [];
  const sbNote = skipped.find((n) => n.startsWith('Google Safe Browsing'));
  const threats = ext.safe_browsing_threats ?? [];
  const domainFlags = ext.domain_flags ?? [];
  const ruleIds = new Set((result.rule_flags ?? []).map((f) => f.rule_id));
  const heuristic = ['lookalike_domain', 'suspicious_tld', 'brand_impersonation_link', 'ip_address_url', 'url_shortener']
    .filter((id) => ruleIds.has(id))
    .map((id) => result.rule_flags.find((f) => f.rule_id === id).description);

  return (
    <div className="ver-section">
      <h4>Domain &amp; Link Intelligence</h4>
      <ul className="domain-list">
        {domains.map((domain) => {
          const sbHit = threats.find((t) => t.includes(domain));
          const ageHit = domainFlags.find((f) => f.includes(`'${domain}'`));
          let pill;
          let detail;
          if (sbHit) {
            const type = sbHit.match(/flagged as (\w+)/)?.[1]?.replace(/_/g, ' ').toLowerCase() ?? 'a threat';
            pill = <span className="pill pill-critical">Flagged domain</span>;
            detail = `Google Safe Browsing lists this link as ${type}.`;
          } else if (ageHit) {
            pill = <span className="pill pill-critical">New domain</span>;
            detail = ageHit;
          } else if (heuristic.length) {
            pill = <span className="pill pill-medium">Suspicious</span>;
            detail = `${heuristic.join('. ')}.`;
          } else if (!sbNote) {
            pill = <span className="pill pill-low">No threats found</span>;
            detail = 'No match in Google Safe Browsing.';
          }
          return (
            <li key={domain}>
              <p className="domain-line">
                <GlobalIcon size={18} className="domain-icon" aria-hidden="true" />
                <code>{domain}</code>
                {pill}
              </p>
              {detail && <p className="domain-detail">{detail}</p>}
            </li>
          );
        })}
      </ul>
      <p className="domain-detail">
        Domain age:{' '}
        {ext.youngest_domain_days != null
          ? `youngest linked domain registered ${ext.youngest_domain_days.toLocaleString()} days ago.`
          : skipped.some((n) => n.startsWith('Domain age'))
            ? 'unavailable (no public registration record for this domain).'
            : 'not checked (well-known platform).'}
        {sbNote && ` Safe Browsing skipped: ${sbNote.replace(/^Google Safe Browsing \(|\)$/g, '')}.`}
      </p>
    </div>
  );
}

function VerificationCard({ result }) {
  const ext = result.external_checks ?? {};
  const entities = result.extracted_entities ?? {};
  const entityCount = ['urls', 'emails', 'phone_numbers'].reduce((n, k) => n + (entities[k]?.length ?? 0), 0);
  const skipped = ext.skipped_checks ?? [];
  const hasUrls = (ext.urls_found ?? []).length > 0;
  // Layers that actually produced a result for this message (rules always run).
  const ran = [
    true,
    hasUrls && !skipped.some((n) => n.startsWith('Google Safe Browsing')),
    ext.youngest_domain_days != null || (ext.domain_flags ?? []).length > 0,
    result.llm_used,
  ].filter(Boolean).length;
  const actions = result.recommended_actions ?? [];

  return (
    <section className="card verify-card" aria-labelledby="vs-title">
      <h3 id="vs-title" className="card-title">
        <MagnifierIcon size={20} className="card-title-icon" aria-hidden="true" />
        2. Verification &amp; Safety
      </h3>

      <div className="ver-section">
        <h4>Forensic Analysis</h4>
        <dl className="forensic-rows">
          <div>
            <dt>Heuristic Rules Triggered</dt>
            <dd>{(result.rule_flags ?? []).length}</dd>
          </div>
          <div>
            <dt>Entities Detected</dt>
            <dd>{entityCount}</dd>
          </div>
          <div>
            <dt>Security Checks Completed</dt>
            <dd>{ran}/4</dd>
          </div>
        </dl>
      </div>

      <DomainIntel result={result} />

      {actions.length > 0 && (
        <div className="ver-section">
          <h4>Recommended Actions</h4>
          <ol className="action-list">
            {actions.map((action, i) => (
              <li key={action}>
                <span className="action-num" aria-hidden="true">
                  {i + 1}
                </span>
                <span>{action}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}

export default function ResultView({ entry, fromHistory, onNewScan }) {
  const result = entry.result;
  const llmUsed = result.llm_used;

  return (
    <div className="view view-result">
      <section className="hero is-result">
        <div className="hero-copy">
          <h1 className="display is-result">
            ANALYSIS <span className="grad-text">RESULT</span>
          </h1>
          <div className="result-status">
            <span className="pill pill-low pill-md">
              <CheckCircleIcon size={13} aria-hidden="true" />
              Scanned Successfully
            </span>
          </div>
          <p className="hero-sub">Here's what we found in your message. Review the details below and take the recommended actions.</p>
        </div>
        <ShieldIllustration className="hero-illus is-small" />
      </section>

      <section className="card scanned-card" aria-labelledby="scanned-title">
        <div className="scanned-head">
          <DocumentIcon size={20} aria-hidden="true" />
          <h2 id="scanned-title">Scanned content</h2>
          <span className="pill pill-low pill-md">{KIND_LABELS[entry.kind] ?? 'Message'}</span>
          <button type="button" className="btn btn-scan-new" onClick={onNewScan}>
            <RestartIcon size={18} aria-hidden="true" />
            Scan New Message
          </button>
        </div>
        <pre className="scanned-text">{entry.text}</pre>
        <p className="scanned-foot">
          <ScannerIcon size={15} aria-hidden="true" />
          Scanned on {formatStamp(entry.ts)}
          {result.cached && (
            <span className="pill pill-accent pill-sm">
              <BoltIcon size={11} aria-hidden="true" />
              Instant Cache Hit
            </span>
          )}
          {fromHistory && <span className="pill pill-neutral pill-sm">Saved result</span>}
        </p>
      </section>

      <RiskBanner key={entry.id} result={result} />

      <div className="metric-grid">
        <MetricCard Icon={ShieldIcon} label="Rule Score" value={`${result.rule_score}/100`} />
        <MetricCard Icon={CpuBoltIcon} label="AI score" value={llmUsed ? `${result.llm_score}/100` : 'n/a'} muted={!llmUsed} />
        <MetricCard Icon={GlobalIcon} label="Model" value={llmUsed ? result.llm_model : 'Rules only'} muted={!llmUsed} />
        <MetricCard
          Icon={BoltIcon}
          label="Domain age"
          value={result.external_checks?.youngest_domain_days != null ? `${result.external_checks.youngest_domain_days.toLocaleString()}d` : 'n/a'}
        />
      </div>

      <div className="forensic-grid">
        <FraudAnalysisCard result={result} />
        <VerificationCard result={result} />
      </div>

      {/* Second exit at the end of the report, so nobody has to scroll back up. */}
      <div className="result-cta">
        <button type="button" className="btn btn-scan-new is-large" onClick={onNewScan}>
          <ArrowLeftIcon size={20} aria-hidden="true" />
          Scan Another Message
        </button>
      </div>

      <p className="disclaimer">
        <InfoCircleIcon size={14} aria-hidden="true" />
        Disclaimer: This tool provides an automated risk indicator combining heuristic rules, threat intelligence, and AI
        analysis—not a guarantee of safety. Never share your OTP, MPIN, or passwords.
      </p>
    </div>
  );
}
