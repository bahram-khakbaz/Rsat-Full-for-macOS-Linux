import { useEffect, useState } from 'react';

export function Table({ rows, cols, onRow, selectedKey, rowKey = 'id', empty = 'NO RECORDS' }) {
  const [tablePage, setTablePage] = useState(1);
  const pageSize = 100,
    pageCount = Math.max(1, Math.ceil(rows.length / pageSize)),
    currentPage = Math.min(tablePage, pageCount);
  useEffect(() => {
    setTablePage(1);
  }, [rows]);
  const shown = rows.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  return (
    <div className="table-shell">
      <table>
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c.key}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((r, i) => {
            const key = r[rowKey] ?? r.samAccountName ?? r.name ?? i;
            return (
              <tr
                key={key}
                className={selectedKey === key ? 'selected' : ''}
                onClick={() => onRow && onRow(r)}
              >
                {cols.map((c) => (
                  <td key={c.key}>{c.render ? c.render(r[c.key], r) : String(r[c.key] ?? '—')}</td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      {!rows.length && <div className="empty">{empty}</div>}
      {rows.length > pageSize && (
        <div className="pagination-bar">
          <span>
            {(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, rows.length)} /{' '}
            {rows.length} records
          </span>
          <div className="pages">
            <button disabled={currentPage === 1} onClick={() => setTablePage(currentPage - 1)}>
              PREVIOUS
            </button>
            <span>
              PAGE {currentPage} / {pageCount}
            </span>
            <button
              disabled={currentPage === pageCount}
              onClick={() => setTablePage(currentPage + 1)}
            >
              NEXT
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
