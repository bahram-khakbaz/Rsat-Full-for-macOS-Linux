import { useEffect, useState } from 'react';
import {
  Activity,
  Download,
  KeyRound,
  Plus,
  Search,
  ShieldCheck,
  Trash2,
  Wifi,
} from 'lucide-react';
import { api } from '../api.js';
import { Button } from '../components/Button.jsx';
import { KV } from '../components/KV.jsx';
import { OperatorsPanel } from '../components/OperatorsPanel.jsx';
import { useSession } from '../session.jsx';
import {
  fingerprintsMatch,
  isInsecureWorkerUrl,
  normalizeWorkerUrl,
  workerTlsLabel,
} from '../worker-pairing.mjs';

export function SettingsPage({ notify }) {
  const blankDc = () => ({ name: '', host: '', ip: '', enabled: true, notes: '' });
  const blankSite = () => ({ name: '', code: '', description: '', dcs: [blankDc(), blankDc()] });
  const [cfg, setCfg] = useState({
    demo_mode: true,
    worker_url: '',
    worker_paired: false,
    worker_identity: null,
    authentication_model: 'domain-integrated-worker',
    sites: [],
  });
  const { can } = useSession();
  const [pairingCode, setPairingCode] = useState('');
  // Worker TLS certificate as presented to the backend, awaiting the operator's comparison
  // with the fingerprint printed on the worker console.
  const [workerCert, setWorkerCert] = useState(null),
    [consoleFingerprint, setConsoleFingerprint] = useState(''),
    [fingerprintChecked, setFingerprintChecked] = useState(false);
  const [nativeForm, setNativeForm] = useState({
      domain: '',
      username: '',
      preferred_dc: '',
      password: '',
      ca_pem: '',
    }),
    [nativeTest, setNativeTest] = useState(null),
    [certificate, setCertificate] = useState(null),
    [certificateHost, setCertificateHost] = useState('');
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(''),
    [tests, setTests] = useState({}),
    [workerTest, setWorkerTest] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const r = await api('/api/settings');
      setCfg(r);
      setNativeForm((x) => ({ ...x, ...r.native, password: '' }));
      setCertificateHost(
        (x) =>
          x ||
          r.native?.preferred_dc ||
          r.sites.flatMap((s) => s.dcs).find((d) => d.enabled !== false)?.host ||
          '',
      );
    } catch (e) {
      notify(e.message, 'bad');
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);

  function updateSite(si, key, value) {
    setCfg((x) => ({
      ...x,
      sites: x.sites.map((s, i) => (i === si ? { ...s, [key]: value } : s)),
    }));
  }
  function updateDc(si, di, key, value) {
    setCfg((x) => ({
      ...x,
      sites: x.sites.map((s, i) =>
        i === si ? { ...s, dcs: s.dcs.map((d, j) => (j === di ? { ...d, [key]: value } : d)) } : s,
      ),
    }));
  }
  function addSite() {
    setCfg((x) => ({ ...x, sites: [...x.sites, blankSite()] }));
  }
  function removeSite(si) {
    setCfg((x) => ({ ...x, sites: x.sites.filter((_, i) => i !== si) }));
  }
  function addDc(si) {
    setCfg((x) => ({
      ...x,
      sites: x.sites.map((s, i) => (i === si ? { ...s, dcs: [...s.dcs, blankDc()] } : s)),
    }));
  }
  function removeDc(si, di) {
    setCfg((x) => ({
      ...x,
      sites: x.sites.map((s, i) =>
        i === si ? { ...s, dcs: s.dcs.filter((_, j) => j !== di) } : s,
      ),
    }));
  }

  async function save() {
    setBusy('save');
    try {
      await api('/api/settings', {
        method: 'PUT',
        body: JSON.stringify({
          demo_mode: cfg.demo_mode,
          connection_mode: cfg.connection_mode,
          worker_url: cfg.worker_url,
          sites: cfg.sites.map((s) => ({
            name: s.name,
            code: s.code || '',
            description: s.description || '',
            dcs: s.dcs.map((d) => ({
              name: d.name,
              host: d.host,
              ip: d.ip || '',
              enabled: d.enabled !== false,
              notes: d.notes || '',
            })),
          })),
        }),
      });
      notify('SETTINGS SAVED — ACTIVE WITHOUT RESTART', 'ok');
      window.dispatchEvent(new Event('directory-settings-changed'));
      await load();
    } catch (e) {
      notify(e.message, 'bad');
    } finally {
      setBusy('');
    }
  }

  function setWorkerUrl(value) {
    setCfg((x) => ({ ...x, worker_url: value }));
    // A certificate inspected for another address must never be pinned to this one.
    setWorkerCert(null);
    setConsoleFingerprint('');
    setFingerprintChecked(false);
  }
  const consoleMismatch =
    Boolean(workerCert) &&
    Boolean(consoleFingerprint.trim()) &&
    !fingerprintsMatch(consoleFingerprint, workerCert.fingerprint);
  const fingerprintConfirmed =
    Boolean(workerCert) &&
    !consoleMismatch &&
    (fingerprintChecked || fingerprintsMatch(consoleFingerprint, workerCert.fingerprint));

  async function inspectWorkerCertificate() {
    const workerUrl = normalizeWorkerUrl(cfg.worker_url);
    if (!workerUrl) {
      notify('WINDOWS WORKER URL IS REQUIRED', 'bad');
      return;
    }
    setBusy('worker-cert');
    setWorkerCert(null);
    setFingerprintChecked(false);
    try {
      const certificate = await api('/api/settings/worker-certificate', {
        method: 'POST',
        body: JSON.stringify({ worker_url: workerUrl }),
      });
      setCfg((x) => ({ ...x, worker_url: workerUrl }));
      setWorkerCert(certificate);
    } catch (e) {
      notify(e.message, 'bad');
    } finally {
      setBusy('');
    }
  }

  async function pairWorker() {
    const workerUrl = normalizeWorkerUrl(cfg.worker_url);
    if (!workerUrl) {
      notify('WINDOWS WORKER URL IS REQUIRED', 'bad');
      return;
    }
    if (!pairingCode) {
      notify('ENTER THE ONE-TIME PAIRING CODE SHOWN ON THE WINDOWS WORKER', 'bad');
      return;
    }
    if (consoleMismatch) {
      notify('CERTIFICATE FINGERPRINT DOES NOT MATCH THE WORKER CONSOLE — DO NOT PAIR', 'bad');
      return;
    }
    if (workerCert && !fingerprintConfirmed) {
      notify('COMPARE THE CERTIFICATE FINGERPRINT WITH THE WORKER CONSOLE FIRST', 'bad');
      return;
    }
    setBusy('pair');
    try {
      const body = { worker_url: workerUrl, pairing_code: pairingCode };
      // Pin exactly the certificate the operator confirmed. Without it the backend
      // only accepts a certificate issued by a CA it already trusts.
      if (fingerprintConfirmed) body.certificate_fingerprint = workerCert.fingerprint;
      const r = await api('/api/settings/pair-worker', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setPairingCode('');
      setWorkerCert(null);
      setConsoleFingerprint('');
      setFingerprintChecked(false);
      setWorkerTest({ ok: true, worker: { identity: r.worker_identity } });
      notify('WINDOWS WORKER PAIRED SECURELY', 'ok');
      await load();
    } catch (e) {
      notify(e.message, 'bad');
    } finally {
      setBusy('');
    }
  }

  async function unpairWorker() {
    setBusy('unpair');
    try {
      await api('/api/settings/unpair-worker', { method: 'POST' });
      setWorkerTest(null);
      notify('WINDOWS WORKER UNPAIRED', 'ok');
      await load();
    } catch (e) {
      notify(e.message, 'bad');
    } finally {
      setBusy('');
    }
  }

  async function testWorker() {
    setBusy('worker');
    try {
      const r = await api('/api/settings/test-worker', {
        method: 'POST',
        body: JSON.stringify({
          worker_url: cfg.worker_url,
          demo_mode: cfg.demo_mode,
        }),
      });
      setWorkerTest(r);
      notify('WINDOWS WORKER CONNECTION OK', 'ok');
    } catch (e) {
      setWorkerTest({ ok: false, error: e.message });
      notify(e.message, 'bad');
    } finally {
      setBusy('');
    }
  }

  async function discover() {
    setBusy('discover');
    try {
      const rows = await api('/api/settings/discover-dcs', {
        method: 'POST',
        body: JSON.stringify({
          worker_url: cfg.worker_url,
          demo_mode: cfg.demo_mode,
        }),
      });
      const grouped = {};
      for (const dc of rows) {
        const site = dc.site || 'Unknown';
        if (!grouped[site]) grouped[site] = [];
        grouped[site].push({
          name: dc.name || '',
          host: dc.host || '',
          ip: dc.ip || '',
          enabled: dc.enabled !== false,
          notes: dc.globalCatalog ? 'Global Catalog' : '',
        });
      }
      const sites = Object.entries(grouped).map(([name, dcs]) => ({
        name,
        code: name
          .toUpperCase()
          .replace(/[^A-Z0-9]+/g, '-')
          .slice(0, 20),
        description: 'Discovered from Active Directory',
        dcs,
      }));
      setCfg((x) => ({ ...x, sites }));
      notify('DOMAIN CONTROLLERS DISCOVERED — REVIEW AND SAVE', 'ok');
    } catch (e) {
      notify(e.message, 'bad');
    } finally {
      setBusy('');
    }
  }

  async function testDc(si, di) {
    const dc = cfg.sites[si].dcs[di];
    if (!dc.host) {
      notify('DC HOST/FQDN IS REQUIRED', 'bad');
      return;
    }
    const key = si + '-' + di;
    setTests((x) => ({ ...x, [key]: { loading: true } }));
    try {
      const r = await api('/api/settings/test-dc', {
        method: 'POST',
        body: JSON.stringify({
          host: dc.host,
          worker_url: cfg.worker_url,
          demo_mode: cfg.demo_mode,
        }),
      });
      setTests((x) => ({ ...x, [key]: r }));
      notify((r.ok ? 'DC REACHABLE: ' : 'DC CHECK FAILED: ') + dc.host, r.ok ? 'ok' : 'bad');
    } catch (e) {
      setTests((x) => ({ ...x, [key]: { ok: false, error: e.message } }));
      notify(e.message, 'bad');
    }
  }

  const totalDcs = cfg.sites.reduce((n, s) => n + s.dcs.length, 0);
  const activeDcs = cfg.sites.reduce(
    (n, s) => n + s.dcs.filter((d) => d.enabled !== false).length,
    0,
  );
  const identity = cfg.worker_identity || workerTest?.worker?.identity || null;
  const isNative = cfg.connection_mode === 'native';
  const canUseWorker = isNative
    ? Boolean(cfg.native?.password_configured)
    : cfg.demo_mode || cfg.worker_paired;

  async function saveNative() {
    setBusy('native');
    setNativeTest(null);
    try {
      const body = {
        domain: nativeForm.domain,
        username: nativeForm.username,
        preferred_dc: nativeForm.preferred_dc,
        ca_pem: nativeForm.ca_pem,
        mobile_attribute: nativeForm.mobile_attribute || 'mobile',
      };
      if (nativeForm.password) body.password = nativeForm.password;
      if (nativeForm.vault_key) body.vault_key = nativeForm.vault_key;
      await api('/api/settings/native', { method: 'PUT', body: JSON.stringify(body) });
      setNativeForm((x) => ({ ...x, password: '' }));
      await load();
      const result = await api('/api/settings/native/test', { method: 'POST' });
      setNativeTest(result);
      notify('DIRECT MAC CONNECTION READY', 'ok');
      window.dispatchEvent(new Event('directory-settings-changed'));
    } catch (e) {
      setNativeTest({ ok: false, error: e.message });
      notify(e.message, 'bad');
    } finally {
      setBusy('');
    }
  }
  async function inspectCertificate() {
    setBusy('certificate');
    setCertificate(null);
    try {
      setCertificate(
        await api('/api/settings/native/certificate', {
          method: 'POST',
          body: JSON.stringify({ host: certificateHost }),
        }),
      );
    } catch (e) {
      notify(e.message, 'bad');
    } finally {
      setBusy('');
    }
  }
  async function trustCertificate() {
    setBusy('trust');
    try {
      await api('/api/settings/native/trust-certificate', {
        method: 'POST',
        body: JSON.stringify({ host: certificate.host, fingerprint: certificate.fingerprint }),
      });
      await load();
      notify('DC CERTIFICATE APPROVED — NOW SAVE YOUR ACCOUNT', 'ok');
      setCertificate(null);
    } catch (e) {
      notify(e.message, 'bad');
    } finally {
      setBusy('');
    }
  }
  async function testNative() {
    setBusy('native-test');
    try {
      setNativeTest(await api('/api/settings/native/test', { method: 'POST' }));
    } catch (e) {
      setNativeTest({ ok: false, error: e.message });
    } finally {
      setBusy('');
    }
  }
  async function forgetNative() {
    await api('/api/settings/native/credentials', { method: 'DELETE' });
    setNativeTest(null);
    await load();
    window.dispatchEvent(new Event('directory-settings-changed'));
  }

  if (loading) return <div className="loading">LOADING SYSTEM CONFIGURATION...</div>;

  return (
    <div className="settings-page">
      <section className="window-frame settings-connection direct-connection">
        <div className="window-title">
          <span>DIRECT MAC CONNECTION / NO WINDOWS WORKER</span>
          <span>LDAPS · PORT 636</span>
        </div>
        <div className="identity-model-note">
          <ShieldCheck size={18} />
          <div>
            <b>CONNECT ONCE — DIRECTORY LOADS AUTOMATICALLY</b>
            <span>
              The Mac backend connects directly to enabled DCs. Password is encrypted at rest; TLS
              requires a trusted CA or an explicitly approved DC certificate; hostname and
              certificate validity are checked. Corporate network/VPN and corporate DNS must be
              reachable.
            </span>
          </div>
        </div>
        <div className="connection-config">
          <label>
            <span>AD DOMAIN</span>
            <input
              value={nativeForm.domain || ''}
              onChange={(e) => setNativeForm({ ...nativeForm, domain: e.target.value })}
            />
          </label>
          <label>
            <span>DOMAIN USER / UPN</span>
            <input
              autoComplete="username"
              value={nativeForm.username || ''}
              onChange={(e) => setNativeForm({ ...nativeForm, username: e.target.value })}
            />
          </label>
          <label>
            <span>AD PASSWORD</span>
            <input
              type="password"
              autoComplete="new-password"
              value={nativeForm.password}
              placeholder={
                cfg.native?.password_configured
                  ? 'Saved securely — leave blank to keep'
                  : 'Enter your domain password here'
              }
              onChange={(e) => setNativeForm({ ...nativeForm, password: e.target.value })}
            />
          </label>
          <label>
            <span>VAULT AGENT KEY (OPTIONAL)</span>
            <input
              value={nativeForm.vault_key || ''}
              placeholder="Key delivered by Vault Agent; leave password blank"
              onChange={(e) => setNativeForm({ ...nativeForm, vault_key: e.target.value })}
            />
            <small>
              Use a password OR a Vault Agent key. Clear this key to switch back to a local
              password.
            </small>
          </label>
          <label>
            <span>MOBILE LDAP ATTRIBUTE</span>
            <input
              value={nativeForm.mobile_attribute || 'mobile'}
              onChange={(e) => setNativeForm({ ...nativeForm, mobile_attribute: e.target.value })}
            />
            <small>
              Read-only display mapping for custom schemas. Edit Mobile changes only the standard
              mobile attribute.
            </small>
          </label>
          <label>
            <span>PREFERRED DC / OPTIONAL</span>
            <input
              value={nativeForm.preferred_dc || ''}
              placeholder="Automatic: use enabled DCs below"
              onChange={(e) => setNativeForm({ ...nativeForm, preferred_dc: e.target.value })}
            />
          </label>
          <label style={{ gridColumn: '1 / -1' }}>
            <span>AD CA CERTIFICATE / PEM</span>
            <textarea
              rows={4}
              value={nativeForm.ca_pem || ''}
              placeholder="Paste the corporate root/intermediate CA certificate if the DC certificate uses an internal CA"
              onChange={(e) => setNativeForm({ ...nativeForm, ca_pem: e.target.value })}
            />
            <small>
              Public CA roots are already trusted. For an internal CA, paste its PEM certificate
              chain. If you do not have it, approve a DC certificate below instead.
            </small>
          </label>
          <div className="connection-buttons">
            <Button kind="primary" icon={KeyRound} disabled={Boolean(busy)} onClick={saveNative}>
              {busy === 'native' ? 'CONNECTING...' : 'SAVE & CONNECT DIRECTLY'}
            </Button>
            <Button
              icon={Wifi}
              disabled={Boolean(busy) || !cfg.native?.password_configured}
              onClick={testNative}
            >
              TEST DIRECT CONNECTION
            </Button>
            <Button
              icon={Search}
              disabled={Boolean(busy) || !isNative || !cfg.native?.password_configured}
              onClick={discover}
            >
              DISCOVER ALL DCS
            </Button>
            {cfg.native?.password_configured && (
              <Button
                kind="danger"
                disabled={Boolean(busy)}
                onClick={() => forgetNative().catch((e) => notify(e.message, 'bad'))}
              >
                FORGET AD PASSWORD
              </Button>
            )}
          </div>
        </div>
        <div className="connection-config">
          <label>
            <span>NO CA FILE? INSPECT A DC CERTIFICATE</span>
            <select
              value={certificateHost}
              onChange={(e) => {
                setCertificateHost(e.target.value);
                setCertificate(null);
              }}
            >
              {cfg.sites
                .flatMap((s) => s.dcs)
                .filter((d) => d.enabled !== false)
                .map((d) => (
                  <option key={d.host} value={d.host}>
                    {d.host}
                  </option>
                ))}
            </select>
            <small>
              Inspect sends no password. Verify this fingerprint against a trusted company source
              before approving it. Approval trusts this DC only; a CA enables automatic failover to
              other DCs.
            </small>
          </label>
          <div className="connection-buttons">
            <Button disabled={Boolean(busy) || !certificateHost} onClick={inspectCertificate}>
              INSPECT DC CERTIFICATE
            </Button>
          </div>
          {certificate && (
            <div style={{ gridColumn: '1 / -1' }}>
              <KV
                items={[
                  ['DC', certificate.host],
                  ['SHA-256', certificate.fingerprint],
                  ['ISSUER', certificate.issuer],
                  ['VALID UNTIL', certificate.valid_until],
                  [
                    'HOSTNAME / DATE',
                    certificate.hostname_valid && certificate.time_valid
                      ? 'MATCH / VALID'
                      : 'INVALID',
                  ],
                ]}
              />
              <Button
                kind="primary"
                disabled={Boolean(busy) || !certificate.hostname_valid || !certificate.time_valid}
                onClick={trustCertificate}
              >
                I VERIFIED THIS CERTIFICATE — TRUST THIS DC
              </Button>
            </div>
          )}
          {Boolean(cfg.native?.trusted_dc_certificates?.length) && (
            <small>Approved DCs: {cfg.native.trusted_dc_certificates.join(', ')}</small>
          )}
        </div>
        <KV
          items={[
            ['ACTIVE CONNECTION', isNative ? 'DIRECT MAC / LDAPS' : 'WINDOWS WORKER'],
            ['ACCOUNT', cfg.native?.username || 'Not configured'],
            ['PASSWORD', cfg.native?.password_configured ? 'Encrypted / saved' : 'Required'],
            ['AUTO CONNECTION', 'Enabled after saving the account'],
          ]}
        />
        {nativeTest && (
          <div className={'connection-result ' + (nativeTest.ok ? 'ok' : 'bad')}>
            <b>{nativeTest.ok ? 'DIRECT AD ONLINE' : 'DIRECT AD ERROR'}</b>
            <span>
              {nativeTest.ok
                ? `${nativeTest.username} → ${nativeTest.host} · ${nativeTest.authentication}`
                : nativeTest.error}
            </span>
          </div>
        )}
        <div className="identity-model-note">
          <div>
            <b>DIRECT MODE CAPABILITIES</b>
            <span>
              Users, groups, computers, OU inventory, sites, trusts, password policies and GPO
              inventory. Supports unlock, password reset, enable/disable, attribute edits, moves,
              deletions and group membership. User creation, OU protection, computer account reset,
              DNS/DHCP administration, GPO editing, replication health and recycle bin are
              unavailable.
            </span>
          </div>
        </div>
      </section>
      {!isNative && (
        <section className="window-frame settings-connection">
          <div className="window-title">
            <span>CONNECTION / IDENTITY MODEL</span>
            <span>DOMAIN-INTEGRATED</span>
          </div>

          <div className="settings-summary settings-summary-five">
            <div>
              <span>MODE</span>
              <b>{cfg.demo_mode ? 'DEMO' : 'PRODUCTION'}</b>
            </div>
            <div>
              <span>WORKER</span>
              <b className={cfg.worker_paired ? 'green-text' : ''}>
                {cfg.demo_mode ? 'SIMULATED' : cfg.worker_paired ? 'PAIRED' : 'NOT PAIRED'}
              </b>
            </div>
            <div>
              <span>SITES</span>
              <b>{cfg.sites.length}</b>
            </div>
            <div>
              <span>DOMAIN CONTROLLERS</span>
              <b>{totalDcs}</b>
            </div>
            <div>
              <span>ENABLED DCS</span>
              <b>{activeDcs}</b>
            </div>
          </div>

          <div className="identity-model-note">
            <ShieldCheck size={18} />
            <div>
              <b>NO ACTIVE DIRECTORY PASSWORD IS STORED ON THE MAC</b>
              <span>
                The Windows Worker runs under a domain identity (recommended: gMSA or delegated
                service account). AD, DNS, DHCP and GPO cmdlets use Windows Integrated
                Authentication / Kerberos.
              </span>
            </div>
          </div>

          <div className="connection-config pairing-config">
            <label className="settings-check">
              <input
                type="checkbox"
                checked={cfg.demo_mode}
                onChange={(e) => setCfg({ ...cfg, demo_mode: e.target.checked })}
              />
              <span>DEMO MODE</span>
              <small>Disable this after the Windows Worker is installed and paired.</small>
            </label>

            <label>
              <span>WINDOWS WORKER URL</span>
              <input
                value={cfg.worker_url || ''}
                onChange={(e) => setWorkerUrl(e.target.value)}
                onBlur={(e) => {
                  const normalized = normalizeWorkerUrl(e.target.value);
                  if (normalized !== e.target.value) setWorkerUrl(normalized);
                }}
                placeholder="https://windows-management-host:8765"
              />
              <small>
                Use a dedicated domain-joined Windows management host, not a Domain Controller.
                HTTPS is the default.
              </small>
              {isInsecureWorkerUrl(cfg.worker_url) && (
                <small className="red-text">
                  Plain http:// sends the worker credential and new passwords unencrypted. The
                  backend refuses it unless it was started with ALLOW_INSECURE_WORKER=true.
                </small>
              )}
            </label>

            <label>
              <span>ONE-TIME PAIRING CODE</span>
              <input
                type="password"
                autoComplete="off"
                value={pairingCode}
                onChange={(e) => setPairingCode(e.target.value)}
                placeholder={
                  cfg.worker_paired
                    ? 'restart worker only if re-pairing is required'
                    : 'shown when run-worker.ps1 starts'
                }
              />
              <small>The code expires after 15 minutes, works once, and is never stored.</small>
            </label>

            {!cfg.worker_paired && !cfg.demo_mode && (
              <label>
                <span>FINGERPRINT ON THE WORKER CONSOLE (OPTIONAL PASTE)</span>
                <input
                  autoComplete="off"
                  spellCheck={false}
                  value={consoleFingerprint}
                  onChange={(e) => setConsoleFingerprint(e.target.value)}
                  placeholder="SHA-256 printed when the worker starts"
                />
                <small>
                  Inspect the worker certificate, then compare its SHA-256 fingerprint with the one
                  printed on the worker console. Pairing pins that exact certificate.
                </small>
              </label>
            )}

            <div className="connection-buttons">
              {!cfg.worker_paired && !cfg.demo_mode && (
                <Button
                  icon={ShieldCheck}
                  onClick={inspectWorkerCertificate}
                  disabled={Boolean(busy) || isInsecureWorkerUrl(cfg.worker_url)}
                >
                  {busy === 'worker-cert' ? 'INSPECTING...' : 'INSPECT CERTIFICATE'}
                </Button>
              )}
              {!cfg.worker_paired && !cfg.demo_mode && (
                <Button
                  icon={KeyRound}
                  kind="primary"
                  onClick={pairWorker}
                  disabled={busy === 'pair' || consoleMismatch}
                >
                  {busy === 'pair' ? 'PAIRING...' : 'PAIR WORKER'}
                </Button>
              )}
              {cfg.worker_paired && !cfg.demo_mode && (
                <Button icon={Wifi} onClick={testWorker} disabled={busy === 'worker'}>
                  {busy === 'worker' ? 'TESTING...' : 'TEST WORKER'}
                </Button>
              )}
              {cfg.worker_paired && !cfg.demo_mode && (
                <Button
                  icon={Trash2}
                  kind="danger"
                  onClick={unpairWorker}
                  disabled={busy === 'unpair'}
                >
                  {busy === 'unpair' ? 'UNPAIRING...' : 'UNPAIR'}
                </Button>
              )}
              <Button
                icon={Search}
                onClick={discover}
                disabled={busy === 'discover' || !canUseWorker}
              >
                {busy === 'discover' ? 'DISCOVERING...' : 'DISCOVER DCS FROM AD'}
              </Button>
              <Button icon={Download} onClick={save} disabled={busy === 'save'}>
                {busy === 'save' ? 'SAVING...' : 'SAVE SETTINGS'}
              </Button>
            </div>
          </div>

          {workerCert && !cfg.worker_paired && !cfg.demo_mode && (
            <div className="connection-config">
              <div style={{ gridColumn: '1 / -1' }}>
                <KV
                  items={[
                    ['WORKER CERTIFICATE SHA-256', workerCert.fingerprint],
                    ['SUBJECT', workerCert.subject],
                    ['VALID FROM', workerCert.valid_from],
                    ['VALID UNTIL', workerCert.valid_until],
                    [
                      'CONSOLE COMPARISON',
                      !consoleFingerprint.trim()
                        ? 'Not pasted — compare by eye and tick the box below'
                        : consoleMismatch
                          ? 'DOES NOT MATCH — DO NOT PAIR'
                          : 'MATCH',
                    ],
                  ]}
                />
                <label className="settings-check">
                  <input
                    type="checkbox"
                    checked={fingerprintConfirmed}
                    disabled={consoleMismatch}
                    onChange={(e) => setFingerprintChecked(e.target.checked)}
                  />
                  <span>THIS FINGERPRINT MATCHES THE WORKER CONSOLE</span>
                  <small>
                    A different fingerprint means another machine answered on this address. Pairing
                    without this confirmation only works for a certificate issued by a CA the
                    backend already trusts.
                  </small>
                </label>
              </div>
            </div>
          )}

          {cfg.worker_paired && !cfg.demo_mode && cfg.worker_tls && (
            <KV
              items={[
                ['WORKER TRANSPORT', workerTlsLabel(cfg.worker_tls)],
                ['PINNED SHA-256', cfg.worker_tls.fingerprint || '—'],
              ]}
            />
          )}

          {identity && (
            <div className="worker-identity">
              <div>
                <span>WORKER COMPUTER</span>
                <b>{identity.computer || '—'}</b>
              </div>
              <div>
                <span>RUN-AS IDENTITY</span>
                <b>{identity.runAs || '—'}</b>
              </div>
              <div>
                <span>AD DOMAIN</span>
                <b>{identity.domain || '—'}</b>
              </div>
              <div>
                <span>AUTHENTICATION</span>
                <b className="green-text">WINDOWS INTEGRATED / KERBEROS</b>
              </div>
            </div>
          )}

          {workerTest && (
            <div className={'connection-result ' + (workerTest.ok ? 'ok' : 'bad')}>
              <b>{workerTest.ok ? 'WORKER ONLINE' : 'WORKER ERROR'}</b>
              <span>
                {workerTest.ok
                  ? 'Authenticated management channel is operational (' +
                    workerTlsLabel(cfg.worker_tls) +
                    ').'
                  : workerTest.error}
              </span>
            </div>
          )}
        </section>
      )}

      <section className="window-frame sites-config">
        <div className="window-title">
          <span>SITE / DOMAIN CONTROLLER MATRIX</span>
          <span>
            {cfg.sites.length} SITES / {totalDcs} DCS
          </span>
        </div>
        <div className="sites-toolbar">
          <div>
            <b>MULTI-SITE DIRECTORY TOPOLOGY</b>
            <span>
              Enabled DCs are used automatically in direct Mac mode. Discovery reads all sites/DCs
              through one authenticated AD connection; review and save the resulting topology.
            </span>
          </div>
          <Button icon={Plus} onClick={addSite}>
            ADD SITE
          </Button>
        </div>

        <div className="site-list">
          {!cfg.sites.length && (
            <div className="empty">
              NO SITES CONFIGURED — ADD A DC OR CONNECT AND DISCOVER ACTIVE DIRECTORY
            </div>
          )}
          {cfg.sites.map((site, si) => (
            <section className="site-card" key={si}>
              <div className="site-head">
                <div className="site-fields">
                  <label>
                    <span>SITE NAME</span>
                    <input
                      value={site.name || ''}
                      onChange={(e) => updateSite(si, 'name', e.target.value)}
                      placeholder="Site name"
                    />
                  </label>
                  <label>
                    <span>CODE</span>
                    <input
                      value={site.code || ''}
                      onChange={(e) => updateSite(si, 'code', e.target.value)}
                      placeholder="HQ"
                    />
                  </label>
                  <label className="site-description">
                    <span>DESCRIPTION</span>
                    <input
                      value={site.description || ''}
                      onChange={(e) => updateSite(si, 'description', e.target.value)}
                      placeholder="Optional description"
                    />
                  </label>
                </div>
                <div className="site-tools">
                  <span>{site.dcs.length} DC</span>
                  <Button icon={Plus} onClick={() => addDc(si)}>
                    ADD DC
                  </Button>
                  <Button icon={Trash2} kind="danger" onClick={() => removeSite(si)}>
                    REMOVE SITE
                  </Button>
                </div>
              </div>

              <div className="dc-table">
                <div className="dc-header">
                  <span>ENABLED</span>
                  <span>DC NAME</span>
                  <span>HOST / FQDN</span>
                  <span>IP ADDRESS</span>
                  <span>NOTES</span>
                  <span>HEALTH</span>
                  <span>ACTIONS</span>
                </div>
                {site.dcs.map((dc, di) => {
                  const result = tests[si + '-' + di];
                  return (
                    <div className="dc-row" key={di}>
                      <label className="dc-enabled">
                        <input
                          type="checkbox"
                          checked={dc.enabled !== false}
                          onChange={(e) => updateDc(si, di, 'enabled', e.target.checked)}
                        />
                      </label>
                      <input
                        value={dc.name || ''}
                        onChange={(e) => updateDc(si, di, 'name', e.target.value)}
                        placeholder="DC01"
                      />
                      <input
                        value={dc.host || ''}
                        onChange={(e) => updateDc(si, di, 'host', e.target.value)}
                        placeholder="dc01.domain.local"
                      />
                      <input
                        value={dc.ip || ''}
                        onChange={(e) => updateDc(si, di, 'ip', e.target.value)}
                        placeholder="10.x.x.x"
                      />
                      <input
                        value={dc.notes || ''}
                        onChange={(e) => updateDc(si, di, 'notes', e.target.value)}
                        placeholder="GC / preferred / notes"
                      />
                      <div className="dc-health">
                        {!result ? (
                          <span className="health unknown">NOT TESTED</span>
                        ) : result.loading ? (
                          <span className="health unknown">TESTING</span>
                        ) : (
                          <span className={'health ' + (result.ok ? 'good' : 'bad')}>
                            {result.ok ? 'ONLINE' : 'FAILED'}
                          </span>
                        )}
                        {result && result.ok && (
                          <small>
                            {isNative
                              ? 'Verified LDAPS · ' + result.host
                              : `DNS ${result.dns ? '✓' : '×'} · LDAP ${result.ldap ? '✓' : '×'} · KRB ${result.kerberos ? '✓' : '×'} · GC ${result.globalCatalog ? '✓' : '×'}`}
                          </small>
                        )}
                      </div>
                      <div className="dc-actions">
                        <button
                          title="Test DC"
                          disabled={!canUseWorker}
                          onClick={() => testDc(si, di)}
                        >
                          <Activity size={13} />
                        </button>
                        <button title="Remove DC" onClick={() => removeDc(si, di)}>
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>

        <div className="settings-footer">
          <span>
            {isNative
              ? 'Topology and the encrypted AD credential are stored locally. Opening the panel connects automatically.'
              : 'Topology is stored locally; the Windows worker uses its own domain identity.'}
          </span>
          <Button icon={Download} kind="primary" onClick={save} disabled={busy === 'save'}>
            SAVE ALL CHANGES
          </Button>
        </div>
      </section>
      {can('operators.manage') && <OperatorsPanel notify={notify} />}
    </div>
  );
}
