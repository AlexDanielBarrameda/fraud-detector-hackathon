import React, { useId } from 'react';

/** Navbar mark: gradient shield outline holding a magnifier with a checkmark. */
export function LogoMark({ size = 48 }) {
  const id = useId().replace(/:/g, '');
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" className="logo-mark">
      <defs>
        <linearGradient id={`${id}-g`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#22d3ee" />
          <stop offset="0.55" stopColor="#14b8a6" />
          <stop offset="1" stopColor="#4ade80" />
        </linearGradient>
        <filter id={`${id}-glow`} x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="1.4" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <g filter={`url(#${id}-glow)`} fill="none" stroke={`url(#${id}-g)`} strokeLinecap="round" strokeLinejoin="round">
        <path d="M24 3.5 7.5 9.6v11.6c0 11 7 19.8 16.5 23.3 9.5-3.5 16.5-12.3 16.5-23.3V9.6L24 3.5Z" strokeWidth="2.6" />
        <path d="M24 8.3 11.8 12.9v8.3c0 8.2 5 14.9 12.2 17.9" strokeWidth="1.2" opacity="0.55" />
        <circle cx="22.5" cy="21.5" r="7.2" strokeWidth="2.6" />
        <path d="m27.8 26.8 6 6" strokeWidth="3.2" />
        <path d="m19.2 21.6 2.3 2.3 4.4-4.6" strokeWidth="2.3" />
      </g>
    </svg>
  );
}

/** Wordmark: FRAUD (ink) + ANALYZER (gradient), with the product subtitle. */
export function Wordmark() {
  return (
    <span className="wordmark">
      <span className="wordmark-title">
        FRAUD <span className="grad-text">ANALYZER</span>
      </span>
      <span className="wordmark-sub">
        AI-Powered Financial Scam
        <br />
        &amp; Fraud Risk Analyzer
      </span>
    </span>
  );
}

function MiniCard({ x, y, w, kind }) {
  const icon = {
    mail: <path d="M4 6h10v7H4zM4 6l5 4 5-4" />,
    link: (
      <>
        <path d="M8 11.5 6.8 12.7a2.2 2.2 0 0 1-3.1-3.1L5 8.3" />
        <path d="M10 6.5 11.2 5.3a2.2 2.2 0 0 1 3.1 3.1L13 9.7M7.4 10.6l3.2-3.2" />
      </>
    ),
    doc: <path d="M5.5 4h5l3 3v7.5h-8zM10.5 4v3h3M7.5 10h4M7.5 12h3" />,
  }[kind];
  return (
    // Outer <g> positions the card; the inner one animates (a CSS transform would override the SVG translate).
    <g transform={`translate(${x} ${y})`}>
    <g className={`illus-card illus-card-${kind}`}>
      <rect width={w} height="26" rx="7" className="illus-card-bg" />
      <rect x="5" y="4.5" width="18" height="17" rx="4.5" className="illus-card-icon-bg" />
      <g transform="translate(5 4.5)" className="illus-card-icon" fill="none" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
        {icon}
      </g>
      <rect x="29" y="8" width={w - 40} height="3.5" rx="1.75" className="illus-card-line" />
      <rect x="29" y="14.5" width={(w - 40) * 0.6} height="3.5" rx="1.75" className="illus-card-line is-soft" />
    </g>
    </g>
  );
}

/** Hero / result illustration: glossy 3D shield with a checkmark, orbit rings, glowing nodes and notification cards. */
export function ShieldIllustration({ className = '' }) {
  const id = useId().replace(/:/g, '');
  const ring = (rx, ry) => `M ${180 - rx} 150 A ${rx} ${ry} 0 0 0 ${180 + rx} 150`;
  return (
    <svg viewBox="0 0 360 250" className={`shield-illus ${className}`} role="img" aria-label="Shield with a checkmark">
      <defs>
        <linearGradient id={`${id}-body`} x1="0.15" y1="0" x2="0.85" y2="1">
          <stop offset="0" stopColor="#6ee7b7" />
          <stop offset="0.45" stopColor="#14b8a6" />
          <stop offset="1" stopColor="#0f5f58" />
        </linearGradient>
        <linearGradient id={`${id}-inner`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2dd4bf" />
          <stop offset="1" stopColor="#0d6e64" />
        </linearGradient>
        <linearGradient id={`${id}-ring`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#22d3ee" stopOpacity="0.15" />
          <stop offset="0.5" stopColor="#14b8a6" stopOpacity="0.85" />
          <stop offset="1" stopColor="#4ade80" stopOpacity="0.2" />
        </linearGradient>
        <radialGradient id={`${id}-glow`} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#2dd4bf" stopOpacity="0.45" />
          <stop offset="1" stopColor="#2dd4bf" stopOpacity="0" />
        </radialGradient>
        <filter id={`${id}-soft`} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="2.5" />
        </filter>
        <filter id={`${id}-shadow`} x="-30%" y="-30%" width="160%" height="170%">
          <feDropShadow dx="0" dy="10" stdDeviation="10" floodColor="#0f766e" floodOpacity="0.35" />
        </filter>
        <filter id={`${id}-check`} x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="3" stdDeviation="3" floodColor="#064e3b" floodOpacity="0.45" />
        </filter>
      </defs>

      <ellipse cx="180" cy="135" rx="120" ry="95" fill={`url(#${id}-glow)`} />

      {/* Back halves of the orbit rings sit behind the shield. */}
      <g transform="rotate(-9 180 150)" fill="none" stroke={`url(#${id}-ring)`} strokeWidth="1.4">
        <ellipse cx="180" cy="150" rx="168" ry="46" />
        <ellipse cx="180" cy="150" rx="142" ry="34" opacity="0.6" />
      </g>

      <g filter={`url(#${id}-shadow)`}>
        <path d="M180 26 251 52v66c0 50-30 88-71 106-41-18-71-56-71-106V52l71-26Z" fill={`url(#${id}-body)`} />
        <path d="M180 44 237 65v52c0 40-24 71-57 86-33-15-57-46-57-86V65l57-21Z" fill={`url(#${id}-inner)`} />
        {/* Glossy left facet and rim light. */}
        <path d="M180 26 109 52v66c0 50 30 88 71 106V26Z" fill="#ffffff" opacity="0.14" />
        <path d="M180 27.5 250 53" stroke="#ffffff" strokeOpacity="0.6" strokeWidth="1.5" strokeLinecap="round" fill="none" />
        <path
          d="m151 124 20 20 39-42"
          fill="none"
          stroke="#ffffff"
          strokeWidth="15"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter={`url(#${id}-check)`}
        />
      </g>

      {/* Front halves of the rings pass in front of the shield. */}
      <g transform="rotate(-9 180 150)" fill="none" stroke={`url(#${id}-ring)`} strokeWidth="1.4">
        <path d={ring(168, 46)} />
        <path d={ring(142, 34)} opacity="0.6" />
      </g>

      {/* Glowing nodes on the orbits. */}
      {[
        [26, 172, 3.2],
        [328, 112, 2.6],
        [76, 196, 2.2],
        [296, 186, 3],
        [58, 86, 2],
      ].map(([cx, cy, r]) => (
        <g key={`${cx}-${cy}`} className="illus-node">
          <circle cx={cx} cy={cy} r={r * 2.4} fill="#34d399" opacity="0.35" filter={`url(#${id}-soft)`} />
          <circle cx={cx} cy={cy} r={r} fill="#34d399" />
        </g>
      ))}

      <MiniCard x={30} y={14} w={74} kind="mail" />
      <MiniCard x={268} y={30} w={80} kind="link" />
      <MiniCard x={262} y={200} w={74} kind="doc" />
    </svg>
  );
}

/** Decorative hexagon mesh for the header banner, faded at the edges. */
export function HexMesh() {
  const id = useId().replace(/:/g, '');
  return (
    <svg className="hex-mesh" aria-hidden="true" preserveAspectRatio="none">
      <defs>
        <pattern id={`${id}-hex`} width="28" height="48.5" patternUnits="userSpaceOnUse" patternTransform="scale(0.9)">
          <path d="M14 0 28 8.1v16.2L14 32.4 0 24.3V8.1ZM14 32.4V48.5M0 48.5" fill="none" stroke="currentColor" strokeWidth="1" />
        </pattern>
        <radialGradient id={`${id}-fade`} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#fff" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
        <mask id={`${id}-mask`}>
          <rect width="100%" height="100%" fill={`url(#${id}-fade)`} />
        </mask>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${id}-hex)`} mask={`url(#${id}-mask)`} className="hex-fill" />
    </svg>
  );
}
