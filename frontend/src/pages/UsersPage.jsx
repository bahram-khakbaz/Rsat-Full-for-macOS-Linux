import { useEffect, useState } from 'react';
import {
  ChevronDown,
  Download,
  Filter,
  FolderTree,
  Group,
  KeyRound,
  LockKeyhole,
  MoreHorizontal,
  Plus,
  Search,
  Trash2,
  UnlockKeyhole,
  Upload,
  UserRoundCog,
  Users,
} from 'lucide-react';
import { enc, api } from '../api.js';
import { Button } from '../components/Button.jsx';
import { Status } from '../components/Status.jsx';
import { Modal } from '../components/Modal.jsx';
import { useSession } from '../session.jsx';

export function UsersPage({ notify, native = false }) {
  const [rows, setRows] = useState([]),
    [q, setQ] = useState(''),
    [selected, setSelected] = useState(null),
    [detail, setDetail] = useState(null),
    [groups, setGroups] = useState([]),
    [modal, setModal] = useState(null),
    [tab, setTab] = useState('General'),
    [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true),
    [loadError, setLoadError] = useState(''),
    [paged, setPaged] = useState(false),
    [nextCursor, setNextCursor] = useState(null),
    [loadedQuery, setLoadedQuery] = useState(''),
    [pageCache, setPageCache] = useState({});
  const perPage = 15;
  const { can } = useSession();
  async function load(targetPage = 1, cursor = null, query = q) {
    if (typeof targetPage !== 'number') targetPage = 1;
    setLoading(true);
    setLoadError('');
    try {
      const search = new URLSearchParams({ q: query });
      // Demo, direct and worker modes all answer { items, next_cursor, has_more, total }.
      search.set('page_size', String(perPage));
      if (cursor) search.set('cursor', cursor);
      const result = await api('/api/ad/users?' + search);
      const isPaged = Array.isArray(result.items),
        items = isPaged ? result.items : result;
      setRows(items);
      setPaged(isPaged);
      setPage(targetPage);
      setLoadedQuery(query);
      setNextCursor(result.next_cursor || null);
      setPageCache((x) => (targetPage === 1 ? { 1: result } : { ...x, [targetPage]: result }));
      if (items[0]) await open(items[0]);
      else {
        setSelected(null);
        setDetail(null);
        setGroups([]);
      }
    } catch (e) {
      setLoadError(e.message);
      notify(e.message, 'bad');
    } finally {
      setLoading(false);
    }
  }
  function goTo(targetPage) {
    const cached = pageCache[targetPage];
    if (cached?.items) {
      setRows(cached.items);
      setNextCursor(cached.next_cursor || null);
      setPage(targetPage);
      if (cached.items[0]) open(cached.items[0]);
    } else load(targetPage, nextCursor, loadedQuery);
  }
  async function open(r) {
    setSelected(r);
    try {
      const [d, g] = await Promise.all([
        api('/api/ad/users/' + enc(r.samAccountName)),
        can('group.read')
          ? api('/api/ad/users/' + enc(r.samAccountName) + '/groups')
          : Promise.resolve([]),
      ]);
      setDetail(d);
      setGroups(g);
    } catch (e) {
      notify(e.message, 'bad');
    }
  }
  async function act(path, method = 'POST', body, keepModal = false) {
    try {
      await api(path, { method, body: body ? JSON.stringify(body) : undefined });
      notify('COMMAND COMPLETED', 'ok');
      await load();
      if (selected) await open(selected);
    } catch (e) {
      if (keepModal) throw e;
      notify(e.message, 'bad');
    }
  }
  useEffect(() => {
    load();
  }, [native]);
  const createFields = [
    ['sam_account_name', 'SAM ACCOUNT'],
    ['given_name', 'GIVEN NAME'],
    ['surname', 'SURNAME'],
    ['display_name', 'DISPLAY NAME'],
    ['email', 'EMAIL'],
    ['department', 'DEPARTMENT'],
    ['title', 'TITLE'],
    ['company', 'COMPANY'],
    ['manager', 'MANAGER (SAM/DN)'],
    ['ou', 'TARGET OU DN'],
    ['password', 'INITIAL PASSWORD', 'password'],
  ];
  const pageCount = Math.max(1, Math.ceil(rows.length / perPage)),
    visible = paged ? rows : rows.slice((page - 1) * perPage, page * perPage);
  const domain =
    (detail?.dn || '')
      .split(',')
      .filter((x) => x.startsWith('DC='))
      .map((x) => x.slice(3))
      .join('.')
      .toUpperCase() || 'ACTIVE DIRECTORY';
  async function exportCsv() {
    const headers = [
      'displayName',
      'samAccountName',
      'mail',
      'department',
      'title',
      'enabled',
      'lastLogon',
    ];
    // Walk every page of the current search so the file is not limited to one screen.
    const exportPageSize = 100,
      maxPages = 100;
    const all = [];
    let cursor = null,
      truncated = false;
    try {
      for (let pageIndex = 0; ; pageIndex++) {
        const search = new URLSearchParams({ q: loadedQuery, page_size: String(exportPageSize) });
        if (cursor) search.set('cursor', cursor);
        const result = await api('/api/ad/users?' + search);
        all.push(...(Array.isArray(result) ? result : result.items || []));
        cursor = Array.isArray(result) ? null : result.next_cursor;
        if (!cursor) break;
        if (pageIndex + 1 >= maxPages) {
          truncated = true;
          break;
        }
      }
    } catch (e) {
      notify(e.message, 'bad');
      return;
    }
    const csv = [
      headers.join(','),
      ...all.map((r) =>
        headers.map((h) => `"${String(r[h] ?? '').replaceAll('"', '""')}"`).join(','),
      ),
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' }),
      url = URL.createObjectURL(blob),
      a = document.createElement('a');
    a.href = url;
    a.download = 'rsat-users.csv';
    a.click();
    URL.revokeObjectURL(url);
    if (truncated)
      notify(`CSV EXPORTED — FIRST ${all.length} USERS ONLY; NARROW THE SEARCH`, 'bad');
    else notify(`CSV EXPORTED — ${all.length} USERS`, 'ok');
  }
  const detailRows = {
    General: [
      ['Full Name', detail?.displayName],
      ['Last Modified (DC)', detail?.modified ? new Date(detail.modified).toLocaleString() : '—'],
      ['Display Name', detail?.displayName],
      ['Username', detail?.samAccountName],
      ['Email', detail?.mail],
      ['Department', detail?.department],
      ['Title', detail?.title],
      ['Company', detail?.company],
      ['Manager', detail?.manager],
      ['Mobile', detail?.directoryMobile || detail?.mobile || '—'],
      ['Mobile Attribute', detail?.mobileAttribute || 'mobile'],
      [
        'Additional Mobile',
        Array.isArray(detail?.otherMobile)
          ? detail.otherMobile.join(' · ') || '—'
          : detail?.otherMobile || '—',
      ],
      ['Office Phone', detail?.telephoneNumber || '—'],
      ['Home Phone', detail?.homePhone || '—'],
      ['IP Phone', detail?.ipPhone || '—'],
      ['Employee ID', detail?.employeeId],
      ['Distinguished Name', detail?.dn],
    ],
    Organization: [
      ['Department', detail?.department],
      ['Title', detail?.title],
      ['Company', detail?.company],
      ['Manager', detail?.manager],
      ['Office', detail?.office],
    ],
    Account: [
      ['Status', detail?.enabled ? 'Enabled' : 'Disabled'],
      ['Locked Out', detail?.lockedOut ? 'Yes' : 'No'],
      ['Last Logon', detail?.lastLogon],
      ['Created', detail?.created],
      ['Last Modified (DC)', detail?.modified],
      ['Source DC', detail?.sourceDC || 'Windows Worker'],
      ['Account Expires', detail?.accountNeverExpires ? 'Never' : detail?.accountExpires],
      ['Change Password At Next Logon', detail?.changePasswordAtLogon ? 'Yes' : 'No'],
      ['Smart Card Required', detail?.smartcardRequired ? 'Yes' : 'No'],
      ['Sensitive / Not Delegated', detail?.sensitiveNotDelegated ? 'Yes' : 'No'],
      ['Logon Workstations', detail?.logonWorkstations || 'All'],
      ['Password Last Set', detail?.passwordLastSet],
      ['Password Expires', detail?.passwordExpires],
      ['Password Never Expires', detail?.passwordNeverExpires ? 'Yes' : 'No'],
    ],
    'Member Of': groups.map((g) => [g.name, g.scope || 'Group']),
    Attributes: Object.entries(detail || {})
      .filter(([k]) => !['displayName'].includes(k))
      .map(([k, v]) => [k, typeof v === 'object' ? JSON.stringify(v) : v]),
  };
  return (
    <div className="users-screen">
      <section className="directory-users window-frame">
        <div className="window-title">
          <span>DIRECTORY USERS &nbsp;[ {domain} ]</span>
          <span>⌄ &nbsp;×</span>
        </div>
        <div className="users-toolbar">
          <div className="main-search">
            <Search size={14} />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && load()}
              placeholder="Search users... (username, name or email)"
            />
            <button onClick={load}>
              <Search size={14} />
            </button>
          </div>
          <button className="square-tool" title="Filter">
            <Filter size={14} />
          </button>
          <button
            className="toolbar-btn"
            disabled={native || !can('ad.create')}
            title={
              native
                ? 'User creation is unavailable in direct mode'
                : can('ad.create')
                  ? 'Create user'
                  : 'Your role does not include ad.create'
            }
            onClick={() => setModal('create')}
          >
            <Plus size={14} /> New User
          </button>
          <button
            className="toolbar-btn"
            onClick={() => notify('Bulk import will require a CSV mapping profile', 'bad')}
          >
            <Upload size={13} /> Import <ChevronDown size={11} />
          </button>
          <button className="toolbar-btn" onClick={exportCsv}>
            <Download size={13} /> Export <ChevronDown size={11} />
          </button>
          <button className="square-tool">
            <MoreHorizontal size={15} />
          </button>
        </div>
        {loadError && (
          <div className="error-box" role="alert">
            {loadError}
          </div>
        )}
        {loading && (
          <div className="directory-loading">READING USER PAGE FROM ACTIVE DIRECTORY...</div>
        )}
        <div className="users-table-wrap">
          <table className="users-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Display Name</th>
                <th>Username</th>
                <th>Department</th>
                <th>Title</th>
                <th>Status</th>
                <th>Last Logon ↓</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((r, i) => (
                <tr
                  key={r.samAccountName}
                  className={selected?.samAccountName === r.samAccountName ? 'selected' : ''}
                  onClick={() => open(r)}
                >
                  <td>{(page - 1) * perPage + i + 1}</td>
                  <td>{r.displayName}</td>
                  <td>{r.samAccountName}</td>
                  <td>{r.department || '—'}</td>
                  <td>{r.title || '—'}</td>
                  <td>
                    <Status ok={r.enabled}>{r.enabled ? 'Enabled' : 'Disabled'}</Status>
                    {r.lockedOut && <span className="locked-flag">Locked</span>}
                  </td>
                  <td>{r.lastLogon ? new Date(r.lastLogon).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && !loadError && !rows.length && <div className="empty">NO MATCHING USERS</div>}
        </div>
        <div className="pagination-bar">
          <span>
            {paged
              ? `Showing ${rows.length ? (page - 1) * perPage + 1 : 0} to ${(page - 1) * perPage + rows.length} · ${nextCursor ? 'More users available' : 'End of results'}`
              : `Showing ${rows.length ? (page - 1) * perPage + 1 : 0} to ${Math.min(page * perPage, rows.length)} of ${rows.length} users`}
          </span>
          {paged ? (
            <div className="pages">
              <button disabled={page === 1 || loading} onClick={() => goTo(page - 1)}>
                PREVIOUS
              </button>
              <span>PAGE {page}</span>
              <button disabled={!nextCursor || loading} onClick={() => goTo(page + 1)}>
                NEXT
              </button>
            </div>
          ) : (
            <div className="pages">
              <button disabled={page === 1} onClick={() => setPage(Math.max(1, page - 1))}>
                ‹
              </button>
              {Array.from({ length: Math.min(5, pageCount) }, (_, i) => i + 1).map((n) => (
                <button key={n} className={page === n ? 'active' : ''} onClick={() => setPage(n)}>
                  {n}
                </button>
              ))}
              {pageCount > 5 && (
                <>
                  <span>...</span>
                  <button onClick={() => setPage(pageCount)}>{pageCount}</button>
                </>
              )}
              <button
                disabled={page === pageCount}
                onClick={() => setPage(Math.min(pageCount, page + 1))}
              >
                ›
              </button>
            </div>
          )}
          <label>
            Show:{' '}
            <select value={perPage} disabled>
              <option>15</option>
            </select>
          </label>
        </div>
      </section>
      <aside className="user-inspector">
        <section className="window-frame user-details">
          <div className="window-title">
            <span>USER DETAILS</span>
            <span>⌄ &nbsp;×</span>
          </div>
          {!detail ? (
            <div className="empty">SELECT A USER</div>
          ) : (
            <>
              <div className="identity-block">
                <div className="portrait">
                  <Users size={34} />
                </div>
                <div className="identity-main">
                  <h3>{detail.displayName}</h3>
                  <p>{detail.mail || detail.samAccountName}</p>
                  <div>
                    <span>Status:</span>
                    <Status ok={detail.enabled}>{detail.enabled ? 'Enabled' : 'Disabled'}</Status>
                  </div>
                  <div>
                    <span>Last Logon:</span>
                    <b>{detail.lastLogon ? new Date(detail.lastLogon).toLocaleString() : '—'}</b>
                  </div>
                  <div>
                    <span>Created:</span>
                    <b>{detail.created ? new Date(detail.created).toLocaleString() : '—'}</b>
                  </div>
                  <div>
                    <span>Password Last Set:</span>
                    <b>
                      {detail.passwordLastSet
                        ? new Date(detail.passwordLastSet).toLocaleString()
                        : '—'}
                    </b>
                  </div>
                  <div>
                    <span>Password Expires:</span>
                    <b>
                      {detail.passwordExpires
                        ? new Date(detail.passwordExpires).toLocaleString()
                        : '—'}
                    </b>
                  </div>
                </div>
              </div>
              <div className="detail-tabs">
                {['General', 'Organization', 'Account', 'Member Of', 'Attributes'].map((x) => (
                  <button key={x} className={tab === x ? 'active' : ''} onClick={() => setTab(x)}>
                    {x}
                  </button>
                ))}
              </div>
              <div className="detail-list">
                {(detailRows[tab] || []).map(([k, v]) => (
                  <div key={String(k)}>
                    <span>{k}</span>
                    <b>{String(v ?? '—')}</b>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
        <section className="window-frame action-window">
          <div className="window-title">
            <span>ACTIONS</span>
            <span>×</span>
          </div>
          <div className="inspector-actions">
            <Button
              perm="ad.update"
              icon={UserRoundCog}
              onClick={() => detail && setModal('options')}
            >
              Account Options
            </Button>
            <Button perm="ad.update" icon={UserRoundCog} onClick={() => detail && setModal('edit')}>
              Edit Attributes
            </Button>
            <Button
              perm="ad.unlock"
              icon={UnlockKeyhole}
              onClick={() =>
                detail && act('/api/ad/users/' + enc(detail.samAccountName) + '/unlock')
              }
            >
              Unlock Account
            </Button>
            <Button
              perm="ad.password"
              icon={KeyRound}
              onClick={() => detail && setModal('password')}
            >
              Reset Password
            </Button>
            <Button
              perm="ad.enable_disable"
              icon={LockKeyhole}
              onClick={() =>
                detail && act('/api/ad/users/' + enc(detail.samAccountName) + '/disable')
              }
            >
              Disable Account
            </Button>
            <Button perm="ad.update" icon={FolderTree} onClick={() => detail && setModal('move')}>
              Move to OU
            </Button>
            <Button
              perm="ad.enable_disable"
              icon={UnlockKeyhole}
              onClick={() =>
                detail && act('/api/ad/users/' + enc(detail.samAccountName) + '/enable')
              }
            >
              Enable Account
            </Button>
            <Button
              perm="ad.delete"
              icon={Trash2}
              kind="danger"
              onClick={() => detail && setModal('delete')}
            >
              Delete User
            </Button>
            <Button icon={Group} onClick={() => setTab('Member Of')}>
              Change Groups
            </Button>
          </div>
        </section>
      </aside>
      {modal === 'create' && (
        <Modal
          title="CREATE DIRECTORY USER"
          fields={createFields
            .map((x) => ({ name: x[0], label: x[1], type: x[2] }))
            .concat([
              { name: 'enabled', label: 'ACCOUNT ENABLED', type: 'checkbox', default: true },
              {
                name: 'must_change',
                label: 'CHANGE PASSWORD AT LOGON',
                type: 'checkbox',
                default: true,
              },
            ])}
          onClose={() => setModal(null)}
          onSubmit={async (v) => {
            await api('/api/ad/users', { method: 'POST', body: JSON.stringify(v) });
            notify('USER CREATED', 'ok');
            load();
          }}
        />
      )}
      {modal === 'edit' && detail && (
        <Modal
          title={'EDIT ' + detail.samAccountName}
          initial={{
            display_name: detail.displayName,
            email: detail.mail,
            department: detail.department,
            title: detail.title,
            company: detail.company,
            manager: detail.manager,
            mobile: detail.mobile,
          }}
          fields={[
            { name: 'display_name', label: 'DISPLAY NAME' },
            { name: 'email', label: 'EMAIL' },
            { name: 'department', label: 'DEPARTMENT' },
            { name: 'title', label: 'TITLE' },
            { name: 'company', label: 'COMPANY' },
            { name: 'manager', label: 'MANAGER' },
            { name: 'mobile', label: 'MOBILE (STANDARD AD ATTRIBUTE)' },
          ]}
          onClose={() => setModal(null)}
          onSubmit={(v) => act('/api/ad/users/' + enc(detail.samAccountName), 'PATCH', v)}
        />
      )}
      {modal === 'options' && detail && (
        <Modal
          title={'ACCOUNT OPTIONS / ' + detail.samAccountName}
          submitLabel="SAVE ACCOUNT OPTIONS"
          subtitle="Account expiry is separate from password expiry. Dates use this Mac’s local time and are saved as UTC. Password expiry follows AD policy. These options do not edit the password-change ACL, logon hours, or delegation permissions."
          initial={{
            password_never_expires: detail.passwordNeverExpires,
            change_password_at_logon: detail.changePasswordAtLogon,
            smartcard_required: detail.smartcardRequired,
            sensitive_not_delegated: detail.sensitiveNotDelegated,
            account_never_expires: detail.accountNeverExpires !== false,
            account_expires: detail.accountExpires
              ? new Date(
                  new Date(detail.accountExpires).getTime() -
                    new Date(detail.accountExpires).getTimezoneOffset() * 60000,
                )
                  .toISOString()
                  .slice(0, 16)
              : '',
            logon_workstations: detail.logonWorkstations || '',
          }}
          fields={[
            { name: 'password_never_expires', label: 'PASSWORD NEVER EXPIRES', type: 'checkbox' },
            {
              name: 'change_password_at_logon',
              label: 'CHANGE PASSWORD AT NEXT LOGON',
              type: 'checkbox',
            },
            {
              name: 'smartcard_required',
              label: 'SMART CARD REQUIRED FOR INTERACTIVE LOGON',
              type: 'checkbox',
            },
            {
              name: 'sensitive_not_delegated',
              label: 'ACCOUNT IS SENSITIVE AND CANNOT BE DELEGATED',
              type: 'checkbox',
            },
            { name: 'account_never_expires', label: 'ACCOUNT NEVER EXPIRES', type: 'checkbox' },
            {
              name: 'account_expires',
              label: 'ACCOUNT EXPIRATION DATE / LOCAL TIME',
              type: 'datetime-local',
            },
            {
              name: 'logon_workstations',
              label: 'LOGON WORKSTATIONS (COMMA SEPARATED; EMPTY = ALL)',
            },
          ]}
          onClose={() => setModal(null)}
          onSubmit={(v) => {
            const body = { ...v };
            if (v.account_never_expires) delete body.account_expires;
            else {
              if (!v.account_expires)
                throw new Error(
                  'Choose an account expiration date or enable account never expires',
                );
              body.account_expires = new Date(v.account_expires).toISOString();
            }
            return act(
              '/api/ad/users/' + enc(detail.samAccountName) + '/account-options',
              'PATCH',
              body,
              true,
            );
          }}
        />
      )}
      {modal === 'password' && detail && (
        <Modal
          title={'RESET PASSWORD / ' + detail.samAccountName}
          initial={{ must_change: !detail.passwordNeverExpires }}
          fields={[
            {
              name: 'new_password',
              label: 'NEW PASSWORD (8–256 CHARACTERS)',
              type: 'password',
              minLength: 8,
              maxLength: 256,
              required: true,
            },
            { name: 'must_change', label: 'CHANGE AT NEXT LOGON', type: 'checkbox', default: true },
          ]}
          onClose={() => setModal(null)}
          subtitle="Domain complexity and password history rules also apply."
          onSubmit={(v) =>
            act('/api/ad/users/' + enc(detail.samAccountName) + '/reset-password', 'POST', v, true)
          }
        />
      )}
      {modal === 'move' && detail && (
        <Modal
          title={'MOVE USER / ' + detail.samAccountName}
          fields={[{ name: 'target_ou', label: 'TARGET OU DISTINGUISHED NAME' }]}
          onClose={() => setModal(null)}
          onSubmit={(v) => act('/api/ad/users/' + enc(detail.samAccountName) + '/move', 'POST', v)}
        />
      )}
      {modal === 'delete' && detail && (
        <Modal
          title={'DELETE ' + detail.samAccountName + ' ?'}
          subtitle="This removes the Active Directory object. Use the Recycle Bin if recovery is required."
          fields={[]}
          danger
          submitLabel="DELETE OBJECT"
          onClose={() => setModal(null)}
          onSubmit={() => act('/api/ad/users/' + enc(detail.samAccountName), 'DELETE')}
        />
      )}
    </div>
  );
}
