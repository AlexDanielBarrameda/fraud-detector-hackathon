import { useCallback, useEffect, useRef, useState } from 'react';

import { IS_REMOTE_API, pingHealth } from '../api/client';

// /health slower than this on page load means the free-tier server was asleep and is booting.
export const SLOW_HEALTH_MS = 3_000;
const RETRY_MS = 5_000; // while booting, Render may briefly answer with an error: retry
const GIVE_UP_MS = 150_000; // stop polling; the analyze request reports any real outage

/**
 * Server readiness: 'checking' | 'waking' | 'awake'.
 *
 * On mount it fires a silent GET /health so a sleeping server starts booting while the user is still
 * reading or pasting. `statusRef` gives the current value synchronously (for decisions inside handlers).
 * The local dev backend never sleeps, so without a remote API URL the status is 'awake' immediately.
 */
export function useServerStatus() {
  const initial = IS_REMOTE_API ? 'checking' : 'awake';
  const [status, setStatus] = useState(initial);
  const statusRef = useRef(initial);

  const update = useCallback((next) => {
    statusRef.current = next;
    setStatus(next);
  }, []);

  useEffect(() => {
    if (!IS_REMOTE_API) return undefined;
    let cancelled = false;
    const started = Date.now();
    const slowTimer = setTimeout(() => {
      if (!cancelled && statusRef.current === 'checking') update('waking');
    }, SLOW_HEALTH_MS);

    (async () => {
      while (!cancelled) {
        const ok = await pingHealth();
        if (cancelled) return;
        if (ok) {
          update('awake');
          return;
        }
        if (statusRef.current !== 'awake') update('waking');
        if (Date.now() - started > GIVE_UP_MS) return;
        await new Promise((resolve) => setTimeout(resolve, RETRY_MS));
      }
    })();

    return () => {
      cancelled = true;
      clearTimeout(slowTimer);
    };
  }, [update]);

  const markAwake = useCallback(() => update('awake'), [update]);
  return { status, statusRef, markAwake };
}
