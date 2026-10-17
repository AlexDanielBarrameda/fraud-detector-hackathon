import React, { useRef, useState } from 'react';
import {
  CheckCircleIcon,
  CpuBoltIcon,
  DangerCircleIcon,
  GlobalIcon,
  InfoCircleIcon,
  LetterIcon,
  LinkIcon,
  ListCheckIcon,
  PhoneIcon,
  RadarIcon,
  ServerIcon,
} from '@solar-icons/react/linear';

const ACRONYMS = /\b(tld|url|otp|ip)\b/g;
const ruleLabel = (id) =>
  id.replace(/_/g, ' ').replace(ACRONYMS, (m) => m.toUpperCase()).replace(/^\w/, (c) => c.toUpperCase());

/** Tag every red flag with where it came from, verified intel first. */
function classifyFindings(result) {
  const ext = result.external_checks ?? {};
  const sb = new Set(ext.safe_browsing_threats ?? []);
  const rdap = new Set(ext.domain_flags ?? []);
  return (result.red_flags ?? []).map((text) => {
    if (sb.has(text)) return { text, kind: 'intel', source: 'Google Safe Browsing' };
    if (rdap.has(text)) return { text, kind: 'intel', source: 'RDAP registry' };
    return result.llm_used
      ? { text, kind: 'ai', source: 'AI finding' }
      : { text, kind: 'rule', source: 'Heuristic rule' };
  });
}

/** Status of each detection layer, derived only from what the backend reported. */
function buildChecks(result) {
  const ext = result.external_checks ?? {};
  const skipped = ext.skipped_checks ?? [];
  const hasUrls = (ext.urls_found ?? []).length > 0;
  const sbNote = skipped.find((n) => n.startsWith('Google Safe Browsing'));
  const rdapNotes = skipped.filter((n) => n.startsWith('Domain age'));
  const aiNote = skipped.find((n) => n.startsWith('AI analysis'));
  const threats = ext.safe_browsing_threats ?? [];
  const domainFlags = ext.domain_flags ?? [];
  const ruleCount = (result.rule_flags ?? []).length;

  const safeBrowsing = !hasUrls
    ? { status: 'idle', detail: 'Not run. The message has no links' }
    : sbNote
      ? { status: 'skipped', detail: sbNote.replace(/^Google Safe Browsing \(|\)$/g, '') }
      : threats.length
        ? { status: 'alert', detail: `${threats.length} threat match${threats.length > 1 ? 'es' : ''}` }
        : { status: 'ok', detail: 'No threat matches' };

  let rdap;
  if (!hasUrls) rdap = { status: 'idle', detail: 'Not run. The message has no links' };
  else if (domainFlags.length) rdap = { status: 'alert', detail: `Newly registered: ${ext.youngest_domain_days} days old` };
  else if (ext.youngest_domain_days != null) rdap = { status: 'ok', detail: `Youngest domain ${ext.youngest_domain_days.toLocaleString()} days old` };
  else if (rdapNotes.length) rdap = { status: 'skipped', detail: rdapNotes.join(' · ') };
  else rdap = { status: 'idle', detail: 'Only well-known platforms linked' };

  return [
    {
      name: 'Heuristic rules',
      Icon: ListCheckIcon,
      status: ruleCount ? 'alert' : 'ok',
      detail: ruleCount ? `${ruleCount} rule${ruleCount > 1 ? 's' : ''} triggered` : 'No rules triggered',
    },
    { name: 'Google Safe Browsing', Icon: GlobalIcon, ...safeBrowsing },
    { name: 'RDAP domain age', Icon: ServerIcon, ...rdap },
    {
      name: 'Gemini analysis',
      Icon: CpuBoltIcon,
      ...(result.llm_used
        ? { status: 'ok', detail: `Answered by ${result.llm_model}` }
        : { status: 'skipped', detail: aiNote ?? 'Unavailable. Rules-only verdict' }),
    },
  ];
}

const STATUS_LABEL = { ok: 'Clear', alert: 'Flagged', skipped: 'Skipped', idle: 'Not run' };

function RulesTab({ flags }) {
  if (!flags.length) return <p className="empty-note">No heuristic rules triggered.</p>;
  const total = flags.reduce((sum, f) => sum + f.weight, 0);
  return (
    <table className="rule-table">
      <thead>
        <tr>
          <th scope="col" className="col-weight">Points</th>
          <th scope="col">Rule</th>
          <th scope="col" className="col-signal">Signal</th>
        </tr>
      </thead>
      <tbody>
        {flags.map((f) => (
          <tr key={f.rule_id}>
            <td className="col-weight">
              <span className="weight">+{f.weight}</span>
            </td>
            <td className="rule-name">{ruleLabel(f.rule_id)}</td>
            <td className="col-signal">{f.description}</td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <td className="col-weight">
            <span className="weight is-total">{total}</span>
          </td>
          <td colSpan={2}>
            Rule score <strong>{Math.min(100, total)}/100</strong>
            {total > 100 && <span className="cap-note"> · capped at 100</span>}
          </td>
        </tr>
      </tfoot>
    </table>
  );
}

function EntitiesTab({ entities }) {
  const groups = [
    { key: 'urls', label: 'URLs', Icon: LinkIcon },
    { key: 'emails', label: 'Emails', Icon: LetterIcon },
    { key: 'phone_numbers', label: 'Phone numbers', Icon: PhoneIcon },
  ].filter((g) => entities[g.key]?.length);

  if (!groups.length) return <p className="empty-note">No links, emails, or phone numbers in the message.</p>;
  return (
    <div className="entity-groups">
      {groups.map(({ key, label, Icon }) => (
        <div key={key} className="entity-group">
          <h4>
            <Icon size={14} aria-hidden="true" />
            {label}
            <span className="entity-count">{entities[key].length}</span>
          </h4>
          <ul>
            {entities[key].map((item) => (
              <li key={item}>
                <code>{item}</code>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function ChecksTab({ checks }) {
  return (
    <ul className="check-list">
      {checks.map(({ name, Icon, status, detail }) => (
        <li key={name} className={`check status-${status}`}>
          <Icon size={16} className="check-icon" aria-hidden="true" />
          <span className="check-name">{name}</span>
          <span className="check-detail">{detail}</span>
          <span className="check-status">{STATUS_LABEL[status]}</span>
        </li>
      ))}
    </ul>
  );
}

function ForensicsTabs({ result }) {
  const entities = result.extracted_entities ?? {};
  const entityCount = ['urls', 'emails', 'phone_numbers'].reduce((n, k) => n + (entities[k]?.length ?? 0), 0);
  const checks = buildChecks(result);
  const tabs = [
    { id: 'rules', label: 'Rules', count: (result.rule_flags ?? []).length },
    { id: 'entities', label: 'Entities', count: entityCount },
    { id: 'checks', label: 'Checks', count: checks.length },
  ];
  const [active, setActive] = useState(0);
  const tabRefs = useRef([]);

  // Arrow keys move between tabs (WAI-ARIA tabs pattern, automatic activation).
  const onKeyDown = (e) => {
    const delta = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (e.key === 'Home' || e.key === 'End' || delta) {
      e.preventDefault();
      const next = e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : (active + delta + tabs.length) % tabs.length;
      setActive(next);
      tabRefs.current[next]?.focus();
    }
  };

  return (
    <section className="block forensics" aria-labelledby="forensics-heading">
      <div className="section-head">
        <h3 id="forensics-heading" className="eyebrow">Forensics</h3>
      </div>
      <div className="tablist" role="tablist" aria-labelledby="forensics-heading" onKeyDown={onKeyDown}>
        {tabs.map((t, i) => (
          <button
            key={t.id}
            ref={(el) => (tabRefs.current[i] = el)}
            type="button"
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={active === i}
            aria-controls={`panel-${t.id}`}
            tabIndex={active === i ? 0 : -1}
            className="tab"
            onClick={() => setActive(i)}
          >
            {t.label}
            <span className="tab-count">{t.count}</span>
          </button>
        ))}
        <span
          className="tab-indicator"
          aria-hidden="true"
          style={{ width: `${100 / tabs.length}%`, transform: `translateX(${active * 100}%)` }}
        />
      </div>
      <div
        key={tabs[active].id}
        className="tabpanel"
        role="tabpanel"
        id={`panel-${tabs[active].id}`}
        aria-labelledby={`tab-${tabs[active].id}`}
        tabIndex={0}
      >
        {active === 0 && <RulesTab flags={result.rule_flags ?? []} />}
        {active === 1 && <EntitiesTab entities={entities} />}
        {active === 2 && <ChecksTab checks={checks} />}
      </div>
    </section>
  );
}

export default function RedFlagList({ result }) {
  const findings = classifyFindings(result);
  const intelCount = findings.filter((f) => f.kind === 'intel').length;

  return (
    <>
      <section className="block" aria-labelledby="assessment-heading">
        <div className="section-head">
          <h3 id="assessment-heading" className="eyebrow">Assessment</h3>
          <span className="section-meta">{result.llm_used ? result.llm_model : 'Rules engine'}</span>
        </div>
        <p className="assessment">{result.explanation}</p>
      </section>

      <section className="block" aria-labelledby="findings-heading">
        <div className="section-head">
          <h3 id="findings-heading" className="eyebrow">Findings</h3>
          <span className="section-meta">
            {findings.length} total{intelCount > 0 && ` · ${intelCount} verified`}
          </span>
        </div>

        {findings.length === 0 ? (
          <div className="finding is-clear">
            <CheckCircleIcon size={18} className="finding-icon" aria-hidden="true" />
            <p>No fraud indicators detected.</p>
          </div>
        ) : (
          <ul className="finding-list">
            {findings.map((f) => (
              <li key={f.text} className={`finding kind-${f.kind}`}>
                {f.kind === 'intel' ? (
                  <RadarIcon size={18} className="finding-icon" aria-hidden="true" />
                ) : (
                  <DangerCircleIcon size={18} className="finding-icon" aria-hidden="true" />
                )}
                <div className="finding-body">
                  <span className="finding-source">
                    {f.kind === 'intel' ? `Verified threat intel · ${f.source}` : f.source}
                  </span>
                  <p>{f.text}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <ForensicsTabs result={result} />

      {(result.external_checks?.skipped_checks ?? []).length > 0 && (
        <p className="skipped-inline">
          <InfoCircleIcon size={14} aria-hidden="true" />
          {result.external_checks.skipped_checks.length} check
          {result.external_checks.skipped_checks.length > 1 ? 's' : ''} skipped. See the Checks tab.
        </p>
      )}
    </>
  );
}
