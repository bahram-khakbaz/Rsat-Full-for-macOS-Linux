import assert from 'node:assert/strict';
import test from 'node:test';
import {
  auditStatus,
  canOpenSection,
  hasPermission,
  resolveSection,
  SECTION_PERMISSIONS,
} from './permissions.mjs';

const order = ['overview', 'users', 'dns', 'audit', 'ssh', 'settings'];

test('wildcard grants everything and missing lists grant nothing', () => {
  assert.equal(hasPermission(['*'], 'gpo.write'), true);
  assert.equal(hasPermission(['ad.read'], 'ad.read'), true);
  assert.equal(hasPermission(['ad.read'], 'ad.update'), false);
  assert.equal(hasPermission(undefined, 'ad.read'), false);
  assert.equal(hasPermission(['*'], ''), false);
});

test('sections follow their read permission and unknown sections stay closed', () => {
  const network = ['ssh.read', 'ssh.connect', 'dns.read', 'audit.read', 'domain.read'];
  assert.equal(canOpenSection(network, 'dns'), true);
  assert.equal(canOpenSection(network, 'ssh-sessions'), true);
  assert.equal(canOpenSection(network, 'users'), false);
  assert.equal(canOpenSection(network, 'settings'), false);
  assert.equal(canOpenSection(['*'], 'not-a-section'), false);
  assert.ok(Object.values(SECTION_PERMISSIONS).every((name) => /^[a-z_]+\.[a-z_]+$/.test(name)));
});

test('an unavailable start section falls back to the first permitted one', () => {
  assert.equal(resolveSection(['*'], 'users', order), 'users');
  assert.equal(resolveSection(['dns.read', 'audit.read'], 'users', order), 'dns');
  assert.equal(resolveSection([], 'users', order), null);
});

test('audit statuses are distinguishable', () => {
  assert.deepEqual(auditStatus('success'), { ok: true, label: 'Command completed' });
  assert.equal(auditStatus('failed').ok, false);
  assert.equal(auditStatus('demo').ok, null);
  assert.notEqual(auditStatus('demo').label, auditStatus('requested').label);
  assert.equal(auditStatus(undefined).label, 'Check result');
});
