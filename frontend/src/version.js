// Injected by Vite from package.json (see vite.config.js); 'dev' outside a Vite build.
export const APP_VERSION = typeof __APP_VERSION__ === 'string' ? __APP_VERSION__ : 'dev';

/** "1.4.0", or "1.4.0 / API 1.4.1" when the backend reports a different version. */
export function versionLabel(apiVersion) {
  return apiVersion && apiVersion !== APP_VERSION
    ? APP_VERSION + ' / API ' + apiVersion
    : APP_VERSION;
}
