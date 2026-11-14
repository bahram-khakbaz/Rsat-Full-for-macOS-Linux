import assert from 'node:assert/strict';
import test from 'node:test';
import {
  fingerprintsMatch,
  isInsecureWorkerUrl,
  normalizeFingerprint,
  normalizeWorkerUrl,
  workerTlsLabel,
} from './worker-pairing.mjs';

const fingerprint = Array.from({ length: 32 }, (_, i) => i.toString(16).padStart(2, '0')).join(':');

test('bare hosts default to https and explicit schemes are kept', () => {
  assert.equal(normalizeWorkerUrl(' mgmt.example.test:8765/ '), 'https://mgmt.example.test:8765');
  assert.equal(
    normalizeWorkerUrl('https://mgmt.example.test:8765'),
    'https://mgmt.example.test:8765',
  );
  assert.equal(
    normalizeWorkerUrl('http://mgmt.example.test:8765'),
    'http://mgmt.example.test:8765',
  );
  assert.equal(normalizeWorkerUrl(''), '');
  assert.equal(normalizeWorkerUrl(undefined), '');
});

test('only plain http is reported as insecure', () => {
  assert.equal(isInsecureWorkerUrl('http://mgmt.example.test:8765'), true);
  assert.equal(isInsecureWorkerUrl('HTTP://mgmt.example.test'), true);
  assert.equal(isInsecureWorkerUrl('https://mgmt.example.test:8765'), false);
  assert.equal(isInsecureWorkerUrl('mgmt.example.test'), false);
});

test('fingerprints compare without separators or case and must be complete', () => {
  assert.equal(normalizeFingerprint('AB:cd 01'), 'abcd01');
  assert.equal(
    fingerprintsMatch(fingerprint, fingerprint.toUpperCase().replaceAll(':', ' ')),
    true,
  );
  assert.equal(fingerprintsMatch(fingerprint, fingerprint.replace('00', '01')), false);
  assert.equal(fingerprintsMatch('ab:cd', 'ab:cd'), false);
  assert.equal(fingerprintsMatch('', ''), false);
});

test('transport labels distinguish pinned, CA and insecure workers', () => {
  const labels = ['pinned', 'ca', 'insecure', 'none'].map((mode) => workerTlsLabel({ mode }));
  assert.equal(new Set(labels).size, 4);
  assert.match(workerTlsLabel({ mode: 'insecure' }), /NOT ENCRYPTED/);
  assert.equal(workerTlsLabel(undefined), 'NOT PAIRED');
});
