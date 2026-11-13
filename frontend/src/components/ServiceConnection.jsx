import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import { Button } from './Button.jsx';
import { Field } from './Field.jsx';
import { Panel } from './Panel.jsx';

export function ServiceConnection({ notify, children }) {
  const [servers, setServers] = useState([]);
  const [cfg, setCfg] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    api('/api/network-connection')
      .then(setCfg)
      .catch((e) => setError(e.message));
    api('/api/network-connection/dhcp-servers')
      .then(setServers)
      .catch((e) => setError(e.message));
  }, []);
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api('/api/network-connection', {
        method: 'PUT',
        body: JSON.stringify({
          dns_host: cfg.dns_host,
          dhcp_host: cfg.dhcp_host,
          port: Number(cfg.port),
          dns_mode: cfg.dns_mode,
          dhcp_mode: cfg.dhcp_mode,
        }),
      });
      setRevision((x) => x + 1);
      notify('SERVICE CONNECTION SAVED', 'ok');
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="stack">
      <details className="service-details">
        <summary>
          SERVICE CONNECTION · {cfg?.dns_host} / {cfg?.dhcp_host} · SETTINGS
        </summary>
        <Panel title="DIRECT DNS / DHCP SERVICE CONNECTION" code="NET">
          <div className="identity-model-note">
            <div>
              <b>DIRECT MAC → SERVICE HOST / KERBEROS</b>
              <span>
                Uses your saved domain account automatically. Direct DNS and DHCP use encrypted
                Kerberos RPC; the server enforces your existing permissions. Select an authorized
                DHCP server below. LDAP mode provides DNS inventory only. WinRM is optional.
              </span>
            </div>
          </div>
          {error && <div className="error-box">{error}</div>}
          {cfg && (
            <form onSubmit={save} className="service-connection">
              <Field
                field={{ label: 'DNS SERVER FQDN' }}
                value={cfg.dns_host}
                onChange={(v) => setCfg({ ...cfg, dns_host: v })}
              />
              <Field
                field={{ label: 'DHCP SERVER FQDN' }}
                value={cfg.dhcp_host}
                onChange={(v) => setCfg({ ...cfg, dhcp_host: v })}
              />
              <Field
                field={{
                  label: 'DNS CONNECTION',
                  type: 'select',
                  options: ['Direct', 'LDAP', 'WinRM'],
                }}
                value={cfg.dns_mode}
                onChange={(v) => setCfg({ ...cfg, dns_mode: v })}
              />
              <Field
                field={{ label: 'DHCP CONNECTION', type: 'select', options: ['RPC', 'WinRM'] }}
                value={cfg.dhcp_mode}
                onChange={(v) => setCfg({ ...cfg, dhcp_mode: v })}
              />
              <Field
                field={{ label: 'WINRM PORT (WINRM MODE ONLY)', type: 'number' }}
                value={cfg.port}
                onChange={(v) => setCfg({ ...cfg, port: v })}
              />
              <Button perm="settings.write" type="submit" kind="primary" disabled={busy}>
                {busy ? 'SAVING...' : 'SAVE / RETRY'}
              </Button>
              <small>
                ACCOUNT: {cfg.username} ·{' '}
                {cfg.password_configured
                  ? 'SAVED DOMAIN PASSWORD'
                  : 'SAVE DOMAIN PASSWORD IN SETTINGS'}
              </small>
              {servers.length > 0 && (
                <label className="discovered-dhcp">
                  <span>AUTHORIZED DHCP SERVERS DISCOVERED FROM AD</span>
                  <select
                    value={servers.some((x) => x.host === cfg.dhcp_host) ? cfg.dhcp_host : ''}
                    onChange={(e) => setCfg({ ...cfg, dhcp_host: e.target.value })}
                  >
                    <option value="">SELECT DHCP SERVER</option>
                    {servers.map((x) => (
                      <option key={x.host} value={x.host}>
                        {x.host} / {x.ip}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </form>
          )}
        </Panel>
      </details>
      {cfg && (
        <div key={revision}>
          {React.cloneElement(children, {
            dnsReadOnly: cfg.dns_mode === 'LDAP',
            dnsZoneReadOnly: cfg.dns_mode !== 'WinRM',
            defaultZone: cfg.domain,
          })}
        </div>
      )}
    </div>
  );
}
