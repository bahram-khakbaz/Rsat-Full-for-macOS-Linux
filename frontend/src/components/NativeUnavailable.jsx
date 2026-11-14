import { Panel } from './Panel.jsx';

export function NativeUnavailable({ section }) {
  return (
    <Panel title={section.toUpperCase()} code="N/A">
      <div className="identity-model-note">
        <div>
          <b>UNAVAILABLE IN DIRECT MAC MODE</b>
          <span>
            This connector does not implement this Windows management protocol. No data or
            successful status is simulated.
          </span>
        </div>
      </div>
    </Panel>
  );
}
