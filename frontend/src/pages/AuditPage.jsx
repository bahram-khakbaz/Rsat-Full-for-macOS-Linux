import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { api } from '../api.js';
import { Button } from '../components/Button.jsx';
import { Status } from '../components/Status.jsx';
import { Table } from '../components/Table.jsx';
import { Panel } from '../components/Panel.jsx';
import { auditStatus } from '../permissions.mjs';

export function AuditPage({ notify }) {
  const [rows, setRows] = useState([]);
  async function load() {
    try {
      setRows(await api('/api/audit?limit=300'));
    } catch (e) {
      notify(e.message, 'bad');
    }
  }
  useEffect(() => {
    load();
  }, []);
  return (
    <Panel
      title="IMMUTABLE CHANGE JOURNAL"
      code="AUD"
      actions={
        <Button icon={RefreshCw} onClick={load}>
          REFRESH
        </Button>
      }
    >
      <Table
        rows={rows}
        rowKey="id"
        cols={[
          { key: 'at', label: 'TIMESTAMP' },
          { key: 'actor', label: 'ACTOR' },
          { key: 'role', label: 'ROLE' },
          { key: 'action', label: 'ACTION' },
          { key: 'target', label: 'TARGET' },
          {
            key: 'status',
            label: 'RESULT',
            render: (v) => <Status ok={auditStatus(v).ok}>{v}</Status>,
          },
        ]}
      />
    </Panel>
  );
}
