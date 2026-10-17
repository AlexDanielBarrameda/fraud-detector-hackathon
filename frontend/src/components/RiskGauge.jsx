import React, { useEffect, useState } from 'react';
import {
  BoltIcon,
  CalendarIcon,
  ClipboardCheckIcon,
  CpuBoltIcon,
  DangerTriangleIcon,
  ServerIcon,
  ShieldCheckIcon,
  ShieldWarningIcon,
} from '@solar-icons/react/linear';

const LEVELS = {
  Low: { Icon: ShieldCheckIcon, summary: 'No strong scam indicators' },
  Medium: { Icon: ShieldWarningIcon, summary: 'Suspicious. Verify before you act' },
  High: { Icon: DangerTriangleIcon, summary: 'Likely a scam' },
  Critical: { Icon: DangerTriangleIcon, summary: 'Scam or phishing attempt' },
};

// Tier boundaries, matching the backend scorer (Low 0–29 · Medium 30–59 · High 60–84 · Critical 85–100).
const ZONES = [
  { level: 'low', from: 0, to: 30 },
  { level: 'medium', from: 30, to: 60 },
  { level: 'high', from: 60, to: 85 },
  { level: 'critical', from: 85, to: 100 },
];

const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Counts 0 -> target on the same curve as the severity bar; jumps straight there under reduced motion. */
function useCountUp(target, duration = 700) {
  const [value, setValue] = useState(() => (prefersReducedMotion() ? target : 0));

  useEffect(() => {
    if (prefersReducedMotion()) {
      setValue(target);
      return undefined;
    }
    let frame;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      setValue(Math.round(target * (1 - Math.pow(1 - t, 4)))); // ≈ cubic-bezier(0.16, 1, 0.3, 1)
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);

  return value;
}

function MetaCell({ Icon, label, value, muted }) {
  return (
    <div className={`meta-cell ${muted ? 'is-muted' : ''}`}>
      <dt>
        <Icon size={14} aria-hidden="true" />
        {label}
      </dt>
      <dd>{value}</dd>
    </div>
  );
}

export default function RiskGauge({ result }) {
  const { final_score: score, risk_level: level, rule_score, llm_score, llm_used, llm_model, cached } = result;
  const youngestDays = result.external_checks?.youngest_domain_days;
  const shown = useCountUp(score);
  const [filled, setFilled] = useState(false);
  const { Icon, summary } = LEVELS[level] ?? LEVELS.Medium;
  const isAlert = level === 'High' || level === 'Critical';

  // Mount at 0, then transition the bar to the score on the next frame.
  useEffect(() => {
    const frame = requestAnimationFrame(() => setFilled(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <section className="verdict" aria-labelledby="verdict-heading">
      <h2 id="verdict-heading" className="visually-hidden">
        Verdict
      </h2>

      <div className="verdict-lockup">
        <div className="score" aria-hidden="true">
          <span className="score-value">{shown}</span>
          <span className="score-max">/100</span>
        </div>

        <div className="verdict-copy">
          <div className="verdict-badges">
            <span className={`tier ${isAlert ? 'is-alert' : ''}`}>
              <span className="tier-dot" aria-hidden="true" />
              <Icon size={15} aria-hidden="true" />
              {level} risk
            </span>
            {cached && (
              <span className="cache-badge">
                <BoltIcon size={13} aria-hidden="true" />
                Instant cache hit
              </span>
            )}
          </div>
          <p className="verdict-summary">{summary}</p>
        </div>
      </div>

      <div
        className="severity"
        role="meter"
        aria-label="Risk score"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={score}
        aria-valuetext={`${score} out of 100, ${level} risk`}
      >
        <div className="severity-track">
          {ZONES.map((z) => (
            <span
              key={z.level}
              className={`severity-zone zone-${z.level}`}
              style={{ flexGrow: z.to - z.from }}
            />
          ))}
          <span className="severity-fill" style={{ transform: `scaleX(${filled ? score / 100 : 0})` }} />
        </div>
        <div className="severity-scale" aria-hidden="true">
          {ZONES.map((z) => (
            <span key={z.level} style={{ flexGrow: z.to - z.from }}>
              {z.level}
            </span>
          ))}
        </div>
      </div>

      <dl className="meta-strip">
        <MetaCell Icon={ClipboardCheckIcon} label="Rule score" value={`${rule_score}/100`} />
        <MetaCell Icon={CpuBoltIcon} label="AI score" value={llm_used ? `${llm_score}/100` : 'n/a'} muted={!llm_used} />
        <MetaCell
          Icon={ServerIcon}
          label="Model"
          value={<span className="model-chip">{llm_model || 'Rules-only fallback'}</span>}
          muted={!llm_used}
        />
        <MetaCell
          Icon={CalendarIcon}
          label="Domain age"
          value={youngestDays != null ? `${youngestDays.toLocaleString()} days` : 'n/a'}
        />
      </dl>
    </section>
  );
}
