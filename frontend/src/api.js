import { formatApiError } from './api-errors.mjs';

export const enc = encodeURIComponent;

/** Fired on `window` when the API reports that the session cookie is no longer valid. */
export const UNAUTHORIZED_EVENT = 'rsat-unauthorized';

// A 401 from these endpoints describes the submitted credentials, not the session.
const CREDENTIAL_ENDPOINTS = ['/api/auth/login', '/api/auth/password'];

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function reportUnauthorized() {
  window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
}

async function errorMessage(response) {
  try {
    return formatApiError(await response.json());
  } catch {
    return 'Request failed (HTTP ' + response.status + ')';
  }
}

/**
 * JSON request against the control plane. The session travels in an httpOnly,
 * same-origin cookie set by the backend; no token is readable from script.
 */
export async function api(path, init = {}) {
  const headers = { 'Content-Type': 'application/json', ...(init.headers || {}) };
  const response = await fetch(path, { credentials: 'same-origin', ...init, headers });
  if (response.status === 401 && !CREDENTIAL_ENDPOINTS.some((prefix) => path.startsWith(prefix))) {
    reportUnauthorized();
    throw new ApiError('Session expired. Sign in again.', 401);
  }
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status);
  return response.status === 204 ? null : response.json();
}
