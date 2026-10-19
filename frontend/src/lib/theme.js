import { useEffect, useState } from 'react';
import { flushSync } from 'react-dom';

// Browser chrome colour per theme (matches each header banner).
const THEME_COLORS = { light: '#e2fbe8', dark: '#115e59' };

// Liquid-drop reveal: the mask is a radial gradient with a feathered rim (opaque to 90% of the radius,
// fading to 100%), so the edge reads like spreading liquid rather than a hard circle.
const WAVE_DURATION_MS = 700;
const WAVE_EASING = 'cubic-bezier(0.65, 0, 0.35, 1)';
const WAVE_SOLID_FRACTION = 0.9;

function applyThemeToDocument(theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLORS[theme]);
}

/**
 * Switches theme with a drop that spreads from (x, y), using the View Transitions API: the browser
 * snapshots the old page, we apply the new theme, then grow a soft-edged mask over the new snapshot.
 * Instant where the API is unavailable; a short crossfade under reduced motion.
 */
function switchThemeWithWave(next, x, y, commit) {
  const update = () => {
    applyThemeToDocument(next);
    flushSync(commit);
  };

  if (!document.startViewTransition) {
    update();
    return;
  }

  const root = document.documentElement;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  root.classList.add(reduceMotion ? 'theme-fade' : 'theme-wave');
  const transition = document.startViewTransition(update);
  transition.finished.finally(() => root.classList.remove('theme-wave', 'theme-fade'));
  if (reduceMotion) return;

  transition.ready.then(() => {
    // The final mask must cover the farthest viewport corner with its solid (unfeathered) part.
    const reach = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    const size = (2 * reach) / WAVE_SOLID_FRACTION;
    root.animate(
      {
        maskSize: ['0px 0px', `${size}px ${size}px`],
        maskPosition: [`${x}px ${y}px`, `${x - size / 2}px ${y - size / 2}px`],
      },
      { duration: WAVE_DURATION_MS, easing: WAVE_EASING, fill: 'both', pseudoElement: '::view-transition-new(root)' },
    );
  });
}

/** Light by default; the user's choice persists in localStorage. index.html applies it before first paint. */
export function useTheme() {
  const [theme, setTheme] = useState(() => (document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'));

  useEffect(() => {
    applyThemeToDocument(theme);
  }, [theme]);

  const toggle = (event) => {
    const next = theme === 'dark' ? 'light' : 'dark';
    try {
      localStorage.setItem('theme', next);
    } catch {
      /* not persisted; still switches for this session */
    }
    const rect = event.currentTarget.getBoundingClientRect();
    switchThemeWithWave(next, rect.left + rect.width / 2, rect.top + rect.height / 2, () => setTheme(next));
  };

  return [theme, toggle];
}
