import { Terminal } from 'lucide-react';
import { SshTerminal } from './SshTerminal.jsx';

export function SshSessionWorkspace({ state, dispatch, visible }) {
  if (!state.items.length)
    return (
      <section className="ssh-session-workspace" hidden={!visible}>
        <div className="identity-model-note">
          <span>
            No open SSH sessions. Select a host in Linux Servers or SSH Switches and click Connect.
          </span>
        </div>
      </section>
    );
  return (
    <section className="ssh-session-workspace" hidden={!visible} aria-label="SSH sessions">
      <div className="ssh-session-tabs" role="tablist" aria-label="Open SSH sessions">
        {state.items.map((session, index) => (
          <div
            className={'ssh-session-tab ' + (state.activeId === session.id ? 'active' : '')}
            key={session.id}
          >
            <button
              role="tab"
              id={'ssh-tab-' + session.id}
              aria-controls={'ssh-pane-' + session.id}
              aria-selected={state.activeId === session.id}
              onClick={() => dispatch({ type: 'select', id: session.id })}
              title={session.device.host + ' · ' + session.device.username}
            >
              <Terminal size={13} />
              <span>
                {index + 1}. {session.device.name}
              </span>
              <small>
                {session.baseUrl.endsWith('linux-servers') ? 'SERVER' : 'SWITCH'} · {session.status}
              </small>
            </button>
            <button
              className="ssh-session-close"
              aria-label={'Close SSH session ' + session.device.name + ' ' + (index + 1)}
              onClick={() => dispatch({ type: 'close', id: session.id })}
            >
              ×
            </button>
          </div>
        ))}
      </div>
      {state.items.map((session) => (
        <div
          key={session.id}
          className="ssh-session-pane"
          role="tabpanel"
          id={'ssh-pane-' + session.id}
          aria-labelledby={'ssh-tab-' + session.id}
          hidden={state.activeId !== session.id}
        >
          <SshTerminal
            device={session.device}
            baseUrl={session.baseUrl}
            sessionId={session.id}
            sessionDispatch={dispatch}
            visible={visible && state.activeId === session.id}
            onClose={() => dispatch({ type: 'close', id: session.id })}
          />
        </div>
      ))}
      <div className="identity-model-note">
        <span>
          Sessions stay open while you switch modules or tabs. Close an individual tab to disconnect
          it. Reloading or closing RSAT ends all sessions.
        </span>
      </div>
    </section>
  );
}
