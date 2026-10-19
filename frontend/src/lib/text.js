// Chat apps often copy links as Markdown: [https://example.com](https://example.com).
// Collapse those to a single URL so it isn't duplicated (or mangled into "https://x](https://x").
const MD_LINK = /\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g;

const comparable = (s) =>
  s
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, '')
    .replace(/^www\./, '')
    .replace(/\/+$/, '');

/**
 * [url](url) -> url. A link with different visible text ("[Click here](https://evil.top)") keeps both
 * as "Click here (https://evil.top)": the real destination is what the scanner must see, and a label
 * that hides it is itself a phishing tell.
 */
export function normalizePastedText(text) {
  return text.replace(MD_LINK, (_, label, url) => (comparable(label) === comparable(url) ? url : `${label} (${url})`));
}
