const API_BASE_URL = 'http://localhost:8000';


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
    throw new Error(`Can't reach the analyzer API at ${API_BASE_URL}. Is the backend server running?`);
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
