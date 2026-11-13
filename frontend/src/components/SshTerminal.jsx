import { useEffect, useState, useRef } from 'react';
import { LogOut } from 'lucide-react';
import { Terminal as XTerminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { api } from '../api.js';
import { Button } from './Button.jsx';
import { Status } from './Status.jsx';
import { Panel } from './Panel.jsx';

export function SshTerminal({
  device,
  onClose,
  baseUrl = '/api/ssh/switches',
  visible = true,
  sessionId,
  sessionDispatch,
}) {
  const element = useRef(null),
    [status, setStatus] = useState('CONNECTING'),
    [error, setError] = useState('');
  const controller = useRef(null),
    shown = useRef(visible);
  useEffect(() => {
    shown.current = visible;
    if (visible) {
      controller.current?.fit();
      controller.current?.focus();
    }
  }, [visible]);
  useEffect(() => {
    sessionDispatch?.({ type: 'status', id: sessionId, status });
  }, [status, sessionId, sessionDispatch]);
  useEffect(() => {
    let active = true,
      socket = null,
      observer = null,
      keepalive = null;
    const term = new XTerminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: 'Menlo, monospace',
      scrollback: 3000,
      theme: { background: '#071516', foreground: '#d4eeee' },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(element.current);
    const fitVisible = () => {
      if (element.current?.clientWidth && element.current?.clientHeight) fit.fit();
    };
    controller.current = { fit: fitVisible, focus: () => term.focus() };
    fitVisible();
    const send = (x) => {
      if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(x));
    };
    const input = term.onData((data) => send({ type: 'input', data }));
    const resize = term.onResize(({ cols, rows }) => send({ type: 'resize', cols, rows }));
    api(baseUrl + '/' + device.id + '/ticket', { method: 'POST' })
      .then(({ ticket }) => {
        if (!active) return;
        socket = new WebSocket(
          (location.protocol === 'https:' ? 'wss://' : 'ws://') +
            location.host +
            baseUrl +
            '/' +
            device.id +
            '/terminal',
        );
        socket.onopen = () => send({ ticket });
        socket.onmessage = (e) => {
          const m = JSON.parse(e.data);
          if (m.type === 'ready') {
            setStatus('CONNECTED');
            fitVisible();
            send({ type: 'resize', cols: term.cols, rows: term.rows });
            if (shown.current) term.focus();
          } else if (m.type === 'output') {
            term.write(Uint8Array.from(atob(m.data), (c) => c.charCodeAt(0)));
          } else if (m.type === 'error') {
            setError(m.message);
            setStatus('FAILED');
          }
        };
        socket.onclose = () => {
          if (active) setStatus((x) => (x === 'FAILED' ? x : 'DISCONNECTED'));
        };
        socket.onerror = () => {
          if (active) setError('Terminal channel failed. Click Disconnect and connect again.');
        };
        keepalive = setInterval(() => send({ type: 'ping' }), 30000);
        observer = new ResizeObserver(fitVisible);
        observer.observe(element.current);
      })
      .catch((e) => {
        if (active) {
          setStatus('FAILED');
          setError(e.message);
        }
      });
    return () => {
      active = false;
      controller.current = null;
      clearInterval(keepalive);
      send({ type: 'disconnect' });
      socket?.close();
      observer?.disconnect();
      input.dispose();
      resize.dispose();
      term.dispose();
    };
  }, [device.id, baseUrl]);
  return (
    <Panel
      title={'SSH / ' + device.name + ' / ' + device.host}
      code="PTY"
      actions={
        <>
          <Status ok={status === 'CONNECTED'}>{status}</Status>
          <Button icon={LogOut} onClick={onClose}>
            DISCONNECT
          </Button>
        </>
      }
    >
      {error && <div className="error-box">{error}</div>}
      <div ref={element} className="ssh-terminal" />
      <div className="identity-model-note">
        <span>
          Interactive SSH terminal. The saved account is used when you connect. Terminal content is
          not recorded in the audit log.
        </span>
      </div>
    </Panel>
  );
}
