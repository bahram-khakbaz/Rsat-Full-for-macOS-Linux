// Pure helpers for pairing the Windows worker over a pinned TLS certificate.

/** Trimmed worker base URL; a bare host gets https:// (plain http must be typed explicitly). */
export function normalizeWorkerUrl(value) {
  const text = String(value ?? '')
    .trim()
    .replace(/\/+$/, '');
  if (!text) return '';
  return /^[a-z][a-z0-9+.-]*:\/\//i.test(text) ? text : 'https://' + text;
}

export function isInsecureWorkerUrl(value) {
  return /^http:\/\//i.test(String(value ?? '').trim());
}

/** Lowercase hex without separators, so "AB:CD" and "abcd" compare equal. */
export function normalizeFingerprint(value) {
  return String(value ?? '')
    .toLowerCase()
    .replace(/[^0-9a-f]/g, '');
}

/** True only for two complete SHA-256 fingerprints with the same value. */
export function fingerprintsMatch(left, right) {
  const a = normalizeFingerprint(left);
  return a.length === 64 && a === normalizeFingerprint(right);
}

/** Label for the `worker_tls` object returned by GET /api/settings. */
export function workerTlsLabel(tls) {
  switch (tls?.mode) {
    case 'pinned':
      return 'TLS / PINNED CERTIFICATE';
    case 'ca':
      return 'TLS / CA-VERIFIED';
    case 'insecure':
      return 'INSECURE HTTP (NOT ENCRYPTED)';
    default:
      return 'NOT PAIRED';
  }
}
