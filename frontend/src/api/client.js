// Empty locally: requests go to relative /api/... and Vite's dev proxy forwards them to 127.0.0.1:8000.
// On Vercel, set VITE_API_BASE_URL=https://<your-backend>.onrender.com (build-time variable).
// Both /health and /api/analyze use this same origin, so the CSP connect-src in vercel.json covers them.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');

// Only a remote (Render) backend sleeps; the local dev backend is either running or not.
export const IS_REMOTE_API = Boolean(API_BASE_URL);

// A free Render instance can need ~30-50 s to boot, plus the AI step (capped at 30 s server-side).
// 90 s covers both, so a cold start never aborts mid-wake-up.
export const ANALYZE_TIMEOUT_MS = 90_000;

/**
 * GET /health once. Resolves true on HTTP 200, false on any error or timeout. Never throws.
 * Used as a silent wake-up ping: it makes a sleeping server start booting right away.
 */
export async function pingHealth(timeoutMs = 60_000) {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(timeoutMs),
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Sends a message text to the backend analysis endpoint.
 *
 * @param {string} text - Message or suspicious communication to analyze.
 * @returns {Promise<object>} Parsed AnalyzeResponse payload from backend.
 */
export async function analyzeText(text) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text }),
      signal: AbortSignal.timeout(ANALYZE_TIMEOUT_MS),
    });
  } catch (err) {
    if (err?.name === 'TimeoutError') {
      throw new Error(
        'The server took too long to respond. It may still be starting up: please try again in a moment.',
      );
    }
    // fetch only rejects on network failure (server down, CORS, offline).
    throw new Error(
      API_BASE_URL
        ? `Can't reach the analyzer API at ${API_BASE_URL}. If it was idle, it may be waking up: try again in a minute.`
        : "Can't reach the local analyzer API (127.0.0.1:8000). Is the backend server running?",
    );
  }

  if (!response.ok) {
    let errorMessage = `API error: ${response.status} ${response.statusText}`;
    try {
      const errorData = await response.json();
      if (errorData.detail) {
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
        } else if (Array.isArray(errorData.detail)) {
          errorMessage = errorData.detail.map((d) => d.msg || JSON.stringify(d)).join(', ');
        }
      }
    } catch {
      // Ignore JSON parse error on non-JSON response
    }
    throw new Error(errorMessage);
  }

  return response.json();
}
