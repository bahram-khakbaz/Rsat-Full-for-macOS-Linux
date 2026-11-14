import {
  Activity,
  Archive,
  ChevronDown,
  Computer,
  Database,
  Folder,
  FolderTree,
  Globe2,
  Group,
  KeyRound,
  LockKeyhole,
  Network,
  RefreshCw,
  Server,
  ShieldCheck,
  SlidersHorizontal,
  Users,
} from 'lucide-react';
import { useSession } from '../session.jsx';

export function TreeItem({
  icon: Icon,
  label,
  active = false,
  indent = 0,
  onClick,
  open = false,
  muted = false,
  perm,
}) {
  const { can } = useSession();
  if (perm && !can(perm)) return null;
  return (
    <button
      className={'tree-item ' + (active ? 'active ' : '') + (muted ? 'muted' : '')}
      style={{ paddingLeft: 10 + indent * 18 }}
      onClick={onClick}
    >
      <span className="tree-guide">{indent ? '├' : '›'}</span>
      {open ? <ChevronDown size={11} /> : <span className="tree-spacer" />}
      {Icon && <Icon size={13} />}
      <span>{label}</span>
    </button>
  );
}

export function DirectoryTree({ section, setSection, shell }) {
  const domain = (
    shell.summary?.domain ||
    shell.settings?.native?.domain ||
    'DIRECTORY.LOCAL'
  ).toUpperCase();
  const ous = (shell.ous || []).slice(0, 7);
  return (
    <aside className="directory-tree window-frame">
      <div className="window-title">
        <span>ACTIVE DIRECTORY</span>
        <span>−</span>
      </div>
      <div className="tree-scroll">
        <TreeItem icon={Globe2} label={domain} open />
        <TreeItem
          icon={Activity}
          label="Dashboard"
          perm="domain.read"
          indent={1}
          active={section === 'overview'}
          onClick={() => setSection('overview')}
        />
        <TreeItem
          icon={Database}
          label="Domain Information"
          perm="domain.read"
          indent={1}
          active={section === 'domain'}
          onClick={() => setSection('domain')}
        />
        <TreeItem
          icon={Server}
          label="Domain Controllers"
          perm="domain.read"
          indent={1}
          onClick={() => setSection('domain')}
        />
        <TreeItem
          icon={RefreshCw}
          label="Replication Status"
          perm="domain.read"
          indent={1}
          onClick={() => setSection('domain')}
        />
        <TreeItem
          icon={KeyRound}
          label="FSMO Roles"
          perm="domain.read"
          indent={1}
          onClick={() => setSection('domain')}
        />
        <TreeItem
          icon={LockKeyhole}
          label="Password Policy"
          perm="domain.read"
          indent={1}
          onClick={() => setSection('domain')}
        />
        <TreeItem
          icon={ShieldCheck}
          label="Fine Grained Policies"
          perm="domain.read"
          indent={1}
          onClick={() => setSection('domain')}
        />
        <TreeItem
          icon={Archive}
          label="Recycle Bin"
          perm="ad.read"
          indent={1}
          active={section === 'recycle'}
          onClick={() => setSection('recycle')}
        />
        <div className="tree-separator" />
        <TreeItem
          icon={Users}
          label="Users"
          perm="ad.read"
          active={section === 'users'}
          onClick={() => setSection('users')}
        />
        <TreeItem
          icon={Group}
          label="Groups"
          perm="group.read"
          active={section === 'groups'}
          onClick={() => setSection('groups')}
        />
        <TreeItem
          icon={Computer}
          label="Computers"
          perm="computer.read"
          active={section === 'computers'}
          onClick={() => setSection('computers')}
        />
        <TreeItem
          icon={FolderTree}
          label="Organizational Units"
          perm="ou.read"
          open
          active={section === 'ous'}
          onClick={() => setSection('ous')}
        />
        <TreeItem
          icon={Folder}
          label={domain.split('.')[0]}
          perm="ou.read"
          indent={1}
          open
          onClick={() => setSection('ous')}
        />
        {ous.map((ou, i) => (
          <TreeItem
            key={ou.dn || i}
            icon={Folder}
            label={ou.name}
            perm="ou.read"
            indent={2}
            onClick={() => setSection('ous')}
          />
        ))}
        <div className="tree-separator" />
        <TreeItem
          icon={Network}
          label="Sites and Services"
          perm="domain.read"
          onClick={() => setSection('domain')}
        />
        <TreeItem
          icon={Globe2}
          label="DNS"
          perm="dns.read"
          active={section === 'dns'}
          onClick={() => setSection('dns')}
        />
        <TreeItem
          icon={Network}
          label="DHCP"
          perm="dhcp.read"
          active={section === 'dhcp'}
          onClick={() => setSection('dhcp')}
        />
        <TreeItem
          icon={ShieldCheck}
          label="Group Policy"
          perm="gpo.read"
          active={section === 'gpo'}
          onClick={() => setSection('gpo')}
        />
        <TreeItem
          icon={SlidersHorizontal}
          label="Settings"
          perm="settings.read"
          active={section === 'settings'}
          onClick={() => setSection('settings')}
        />
      </div>
    </aside>
  );
}
