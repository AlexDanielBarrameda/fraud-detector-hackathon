// Recent scans, persisted in localStorage.
// Real scans store the full API response so clicking one reloads the exact verdict (no new request).
// First-run seed entries store only the message text; clicking one runs a real analysis and replaces it.

const KEY = 'fraud-analyzer:history';
const MAX_ENTRIES = 20;
const HOUR = 3_600_000;

export const KIND_LABELS = {
  sms: 'SMS',
  link: 'Link',
  email: 'Email',
  payment: 'Payment request',
  message: 'Message',
};

// Invoice / billing language (a plain receipt like "You have paid PHP 245" stays an SMS).
const PAYMENT_RE = /\b(invoice|billing statement|statement of account|amount due|due date|payment request|request(ing)? (for )?payment|pay (now|before|within|on or before)|remit(tance)?)\b/i;

/** Infer what was scanned from the text itself, for the icon and the "Scanned content" badge. */
export function detectKind(text) {
  const trimmed = text.trim();
  if (/^(from|subject|to):/im.test(trimmed)) return 'email';
  if (/^(https?:\/\/|www\.)\S+$/i.test(trimmed) || /^[a-z0-9-]+(\.[a-z0-9-]+)+(\/\S*)?$/i.test(trimmed)) return 'link';
  if (PAYMENT_RE.test(trimmed)) return 'payment';
  return trimmed.length <= 320 ? 'sms' : 'message';
}

function titleFor(text, kind) {
  const firstLine = text.trim().split('\n')[0];
  if (kind === 'link') return firstLine;
  return firstLine.length > 60 ? `${firstLine.slice(0, 57).trimEnd()}…` : firstLine;
}

export function makeEntry(text, kind, result) {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    text,
    kind,
    title: titleFor(text, kind),
    risk_level: result.risk_level,
    final_score: result.final_score,
    ts: Date.now(),
    result,
  };
}

// Verdicts below are what the rules engine returns for these texts (checked against the backend);
// the full AI-backed result replaces each entry the first time it is opened.
function seedEntries() {
  const now = Date.now();
  const seed = (text, kind, risk_level, final_score, hoursAgo) => ({
    ...makeEntry(text, kind, { risk_level, final_score }),
    id: `seed-${hoursAgo}`,
    ts: now - hoursAgo * HOUR,
    result: null,
    seed: true,
  });
  return [
    seed('Maya: Your wallet has been temporarily restricted. Re-activate your account within 12 hours at https://maya-ph-secure.xyz/kyc or it will be permanently deactivated.', 'sms', 'Critical', 95, 2),
    seed('https://lbc-ph-delivery.top/track', 'link', 'High', 65, 27),
    seed('BDO: Your One-Time PIN is 482913 for your online transaction of PHP 3,250.00. Valid for 5 minutes. Never share your OTP with anyone.', 'sms', 'Low', 0, 52),
    seed('Netflix: Your payment was declined. Update your billing information within 48 hours to avoid suspension of your membership: https://netflix-billing-update.com/account', 'email', 'High', 75, 98),
  ];
}

export function loadHistory() {
  try {
    const stored = JSON.parse(localStorage.getItem(KEY));
    if (Array.isArray(stored)) return stored;
  } catch {
    /* corrupt or blocked storage: fall through to seeds */
  }
  const seeds = seedEntries();
  saveHistory(seeds);
  return seeds;
}

export function saveHistory(list) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    /* storage full or blocked: history stays in memory for this session */
  }
}

/** Prepend a scan; an earlier entry with the same text is replaced rather than duplicated. */
export function addEntry(list, entry) {
  const key = entry.text.trim();
  return [entry, ...list.filter((e) => e.text.trim() !== key)].slice(0, MAX_ENTRIES);
}

const DATE_FMT = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
const TIME_FMT = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' });

/** "Oct 16, 2026 • 2:24 PM" */
export function formatStamp(ts) {
  const d = new Date(ts);
  return `${DATE_FMT.format(d)} • ${TIME_FMT.format(d)}`;
}
