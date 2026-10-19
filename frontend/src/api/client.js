// Empty locally: requests go to relative /api/... and Vite's dev proxy forwards them to 127.0.0.1:8000.
// On Vercel, set VITE_API_BASE_URL=https://<your-backend>.onrender.com (build-time variable).
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');


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
    });
  } catch {
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
