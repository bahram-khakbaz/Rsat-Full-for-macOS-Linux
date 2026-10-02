import React,{useEffect,useMemo,useState} from 'react'
import {createRoot} from 'react-dom/client'
import {
  Activity,Archive,Box,ChevronDown,ChevronRight,Command,Computer,Database,Download,FileClock,Filter,Folder,FolderTree,
  Globe2,Group,HardDrive,KeyRound,Link2,LockKeyhole,LogOut,MoreHorizontal,Network,Plus,RefreshCw,
  Search,Server,ShieldCheck,SlidersHorizontal,Terminal,Trash2,UnlockKeyhole,Upload,UserRoundCog,Users,Wifi
} from 'lucide-react'
import './styles.css'

const TOKEN='rsat_token'
const enc=encodeURIComponent
const nav=[
  ['overview','1','Overview',Activity],
  ['domain','2','Domain / Forest',Server],
  ['users','3','Users',Users],
  ['groups','4','Groups',Group],
  ['computers','5','Computers',Computer],
  ['ous','6','Organizational Units',FolderTree],
  ['dns','7','DNS',Globe2],
  ['dhcp','8','DHCP',Network],
  ['gpo','9','Group Policy',ShieldCheck],
  ['audit','0','Audit Log',FileClock],
  ['settings','S','Settings',SlidersHorizontal],
]

async function api(path,init={}){
  const headers={'Content-Type':'application/json',...(init.headers||{})}
  const token=localStorage.getItem(TOKEN)
  if(token) headers.Authorization='Bearer '+token
  const res=await fetch(path,{...init,headers})
  if(res.status===401 && path!=='/api/auth/login'){
    localStorage.removeItem(TOKEN); location.reload(); throw new Error('Session expired')
  }
  if(!res.ok){
    let message='Request failed'
    try{const d=await res.json();message=typeof d.detail==='string'?d.detail:JSON.stringify(d.detail||d)}catch{message=await res.text()}
    throw new Error(message)
  }
  return res.status===204?null:res.json()
}

function Button({children,kind='',icon:Icon,onClick,type='button',disabled=false}){
  return <button type={type} disabled={disabled} className={'btn '+kind} onClick={onClick}>{Icon&&<Icon size={14}/>}<span>{children}</span></button>
}
function Status({ok,children}){return <span className={'status '+(ok===true?'ok':ok===false?'bad':'neutral')}><i/>{children}</span>}
function Field({field,value,onChange}){
  if(field.type==='select') return <label><span>{field.label}</span><select value={value??field.default??''} onChange={e=>onChange(e.target.value)}>{field.options.map(x=><option key={x} value={x}>{x}</option>)}</select></label>
  if(field.type==='checkbox') return <label className="check"><input type="checkbox" checked={Boolean(value)} onChange={e=>onChange(e.target.checked)}/><span>{field.label}</span></label>
  return <label><span>{field.label}</span><input type={field.type||'text'} value={value??''} placeholder={field.placeholder||''} onChange={e=>onChange(e.target.value)} /></label>
}
function Modal({title,subtitle,fields=[],initial={},submitLabel='EXECUTE',danger=false,onClose,onSubmit,children}){
  const[values,setValues]=useState(()=>Object.fromEntries(fields.map(f=>[f.name,initial[f.name]??f.default??(f.type==='checkbox'?false:'')])))
  const[busy,setBusy]=useState(false),[error,setError]=useState('')
  async function submit(e){e.preventDefault();setBusy(true);setError('');try{await onSubmit(values);onClose()}catch(err){setError(err.message)}finally{setBusy(false)}}
  return <div className="modal-backdrop" onMouseDown={e=>e.target===e.currentTarget&&onClose()}>
    <form className="modal" onSubmit={submit}>
      <div className="modal-head"><div><span className="eyebrow">SYSTEM DIALOG</span><h3>{title}</h3>{subtitle&&<p>{subtitle}</p>}</div><button type="button" className="x" onClick={onClose}>×</button></div>
      <div className="form-grid">{children||fields.map(f=><Field key={f.name} field={f} value={values[f.name]} onChange={v=>setValues({...values,[f.name]:v})}/>)}</div>
      {error&&<div className="error-box">{error}</div>}
      <div className="modal-actions"><Button onClick={onClose}>CANCEL</Button><Button type="submit" kind={danger?'danger':'primary'} disabled={busy}>{busy?'WORKING...':submitLabel}</Button></div>
    </form>
  </div>
}
function Table({rows,cols,onRow,selectedKey,rowKey='id',empty='NO RECORDS'}){
  return <div className="table-shell"><table><thead><tr>{cols.map(c=><th key={c.key}>{c.label}</th>)}</tr></thead><tbody>
    {rows.map((r,i)=>{const key=r[rowKey]??r.samAccountName??r.name??i;return <tr key={key} className={selectedKey===key?'selected':''} onClick={()=>onRow&&onRow(r)}>{cols.map(c=><td key={c.key}>{c.render?c.render(r[c.key],r):String(r[c.key]??'—')}</td>)}</tr>})}
  </tbody></table>{!rows.length&&<div className="empty">{empty}</div>}</div>
}
function Panel({title,code,actions,children,className=''}){return <section className={'panel '+className}><div className="panel-title"><div><b>[{code}]</b><span>{title}</span></div><div className="panel-actions">{actions}</div></div>{children}</section>}
function KV({items}){return <div className="kv">{items.map(([k,v])=><div key={k}><span>{k}</span><b>{String(v??'—')}</b></div>)}</div>}
function Toast({toast}){return toast?<div className={'toast '+toast.kind}><Terminal size={15}/>{toast.text}</div>:null}

function Login(){
  const[user,setUser]=useState('admin'),[pass,setPass]=useState(''),[err,setErr]=useState(''),[busy,setBusy]=useState(false)
  async function submit(e){e.preventDefault();setBusy(true);setErr('');try{const r=await api('/api/auth/login',{method:'POST',body:JSON.stringify({username:user,password:pass})});localStorage.setItem(TOKEN,r.access_token);location.reload()}catch(x){setErr(x.message)}finally{setBusy(false)}}
  return <div className="login-screen">
    <div className="boot-lines">RSAT FULL SYSTEM CONSOLE<br/>CROSS-PLATFORM DIRECTORY ADMINISTRATION<br/>BUILD 0.2.0 / SECURE SESSION</div>
    <form className="login" onSubmit={submit}>
      <div className="terminal-mark"><Command size={22}/></div>
      <div className="eyebrow">AUTHORIZED OPERATORS ONLY</div>
      <h1>RSAT//FULL</h1><p>ADMINISTRATION TERMINAL FOR macOS + LINUX</p>
      <label><span>OPERATOR</span><input autoFocus value={user} onChange={e=>setUser(e.target.value)}/></label>
      <label><span>PASSWORD</span><input type="password" value={pass} onChange={e=>setPass(e.target.value)}/></label>
      {err&&<div className="error-box">{err}</div>}
      <Button type="submit" kind="primary" icon={KeyRound} disabled={busy}>{busy?'AUTHENTICATING':'ENTER SYSTEM'}</Button>
      <small>ACCESS IS LOGGED AND AUDITED</small>
    </form>
  </div>
}


function TreeItem({icon:Icon,label,active=false,indent=0,onClick,open=false,muted=false}){
  return <button className={'tree-item '+(active?'active ':'')+(muted?'muted':'')} style={{paddingLeft:10+indent*18}} onClick={onClick}>
    <span className="tree-guide">{indent? '├':'›'}</span>{open?<ChevronDown size={11}/>:<span className="tree-spacer"/>}{Icon&&<Icon size={13}/>}<span>{label}</span>
  </button>
}

function DirectoryTree({section,setSection,shell}){
  const domain=(shell.summary?.domain||'DIRECTORY.LOCAL').toUpperCase()
  const ous=(shell.ous||[]).slice(0,7)
  return <aside className="directory-tree window-frame">
    <div className="window-title"><span>ACTIVE DIRECTORY</span><span>−</span></div>
    <div className="tree-scroll">
      <TreeItem icon={Globe2} label={domain} open />
      <TreeItem icon={Activity} label="Dashboard" indent={1} active={section==='overview'} onClick={()=>setSection('overview')}/>
      <TreeItem icon={Database} label="Domain Information" indent={1} active={section==='domain'} onClick={()=>setSection('domain')}/>
      <TreeItem icon={Server} label="Domain Controllers" indent={1} onClick={()=>setSection('domain')}/>
      <TreeItem icon={RefreshCw} label="Replication Status" indent={1} onClick={()=>setSection('domain')}/>
      <TreeItem icon={KeyRound} label="FSMO Roles" indent={1} onClick={()=>setSection('domain')}/>
      <TreeItem icon={LockKeyhole} label="Password Policy" indent={1} onClick={()=>setSection('domain')}/>
      <TreeItem icon={ShieldCheck} label="Fine Grained Policies" indent={1} onClick={()=>setSection('domain')}/>
      <TreeItem icon={Archive} label="Recycle Bin" indent={1} active={section==='recycle'} onClick={()=>setSection('recycle')}/>
      <div className="tree-separator"/>
      <TreeItem icon={Users} label="Users" active={section==='users'} onClick={()=>setSection('users')}/>
      <TreeItem icon={Group} label="Groups" active={section==='groups'} onClick={()=>setSection('groups')}/>
      <TreeItem icon={Computer} label="Computers" active={section==='computers'} onClick={()=>setSection('computers')}/>
      <TreeItem icon={FolderTree} label="Organizational Units" open active={section==='ous'} onClick={()=>setSection('ous')}/>
      <TreeItem icon={Folder} label={domain.split('.')[0]} indent={1} open onClick={()=>setSection('ous')}/>
      {ous.map((ou,i)=><TreeItem key={ou.dn||i} icon={Folder} label={ou.name} indent={2} onClick={()=>setSection('ous')}/>)}
      <div className="tree-separator"/>
      <TreeItem icon={Network} label="Sites and Services" onClick={()=>setSection('domain')}/>
      <TreeItem icon={Globe2} label="DNS" active={section==='dns'} onClick={()=>setSection('dns')}/>
      <TreeItem icon={Network} label="DHCP" active={section==='dhcp'} onClick={()=>setSection('dhcp')}/>
      <TreeItem icon={ShieldCheck} label="Group Policy" active={section==='gpo'} onClick={()=>setSection('gpo')}/>
      <TreeItem icon={SlidersHorizontal} label="Settings" active={section==='settings'} onClick={()=>setSection('settings')}/>
    </div>
  </aside>
}

function DomainStatus({shell}){
  const s=shell.summary||{}, dcs=shell.controllers||[], repl=shell.replication||[]
  const healthy=repl.every(x=>Number(x.failures||0)===0)
  return <section className="bottom-window">
    <div className="window-title"><span>DOMAIN STATUS</span><span>⌃</span></div>
    <div className="status-list">
      <div><i/><span>Domain:</span><b>{s.domain||'—'}</b></div>
      <div><i/><span>Domain Functional Level:</span><b>{s.domainMode||'—'}</b></div>
      <div><i/><span>Forest Functional Level:</span><b>{s.forestMode||'—'}</b></div>
      <div><i/><span>Domain Controllers:</span><b>{dcs.length}</b></div>
      <div><i/><span>Global Catalog:</span><b>{dcs.filter(x=>x.globalCatalog).length}</b></div>
      <div><i/><span>FSMO Roles:</span><b className="green-text">{s.pdc?'Healthy':'Unknown'}</b></div>
      <div><i className={healthy?'':'err'}/><span>Replication:</span><b className={healthy?'green-text':'red-text'}>{healthy?'Healthy':'Attention'}</b></div>
    </div>
  </section>
}

function RecentActivity({rows=[]}){
  return <section className="bottom-window">
    <div className="window-title"><span>RECENT ACTIVITY</span><span>⌃</span></div>
    <div className="mini-table-wrap"><table className="mini-table"><thead><tr><th>Time</th><th>User</th><th>Action</th><th>Target</th><th>Details</th></tr></thead><tbody>
      {rows.slice(0,8).map(r=><tr key={r.id}><td>{r.at?new Date(r.at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'}):'—'}</td><td>{r.actor}</td><td>{r.action}</td><td>{r.target||'—'}</td><td>{r.status==='success'?'Command completed':'Check result'}</td></tr>)}
      {!rows.length&&<tr><td colSpan="5">No audit events loaded</td></tr>}
    </tbody></table></div>
  </section>
}

function SystemConsole({shell,section}){
  const now=new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'})
  const domain=shell.summary?.domain||'—'
  const dc=shell.controllers?.[0]?.hostName||shell.controllers?.[0]?.name||'—'
  const demo=shell.health?.demo_mode
  const lines=[
    `[${now}] Connected to control plane ........ OK`,
    `[${now}] Directory API ..................... OK`,
    `[${now}] Audit subsystem ................... ${shell.audit?'OK':'N/A'}`,
    `[${now}] Domain: ${domain}`,
    `[${now}] DC: ${dc}`,
    `[${now}] Mode: ${demo?'DEMO':'WINDOWS WORKER'}`,
    `[${now}] Module: ${section.toUpperCase()}`,
    `[${now}] Session ready`,
  ]
  return <section className="bottom-window console-window">
    <div className="window-title"><span>SYSTEM CONSOLE</span><span>⋮</span></div>
    <pre>{lines.map((x,i)=><span key={i} className={i<3?'console-ok':''}>{x}{'\n'}</span>)}</pre>
  </section>
}

function BottomDock({shell,section}){
  return <div className="bottom-dock"><DomainStatus shell={shell}/><RecentActivity rows={shell.audit}/><SystemConsole shell={shell} section={section}/></div>
}

function Overview({notify}){
  const[data,setData]=useState(null),[loading,setLoading]=useState(true)
  async function load(){setLoading(true);try{
    const[d,u,c,z,s,r]=await Promise.all([api('/api/domain/summary'),api('/api/ad/users'),api('/api/ad/computers'),api('/api/dns/zones'),api('/api/dhcp/scopes'),api('/api/domain/replication')])
    setData({d,u,c,z,s,r})
  }catch(e){notify(e.message,'bad')}finally{setLoading(false)}}
  useEffect(()=>{load()},[])
  if(loading)return <Panel title="SYSTEM SCAN" code="WAIT"><div className="loading">READING DIRECTORY SERVICES...</div></Panel>
  const locked=data.u.filter(x=>x.lockedOut).length,disabled=data.u.filter(x=>!x.enabled).length,repFail=data.r.reduce((a,x)=>a+Number(x.failures||0),0)
  return <div className="stack">
    <div className="hero-console"><div><span className="eyebrow">CONTROL PLANE / READY</span><h2>{data.d.domain}</h2><p>{data.d.forest} · {data.d.domainMode} · {data.d.forestMode}</p></div><div className="big-status">ONLINE<span>●</span></div></div>
    <div className="metrics">
      {[['DIRECTORY USERS',data.u.length,'USR'],['LOCKED ACCOUNTS',locked,'LCK'],['DISABLED USERS',disabled,'DSB'],['COMPUTERS',data.c.length,'CMP'],['DNS ZONES',data.z.length,'DNS'],['DHCP SCOPES',data.s.length,'DHC'],['REPL. FAILURES',repFail,'REP'],['RECYCLE BIN',data.d.recycleBin?'ON':'OFF','RCY']].map(x=><div className="metric" key={x[0]}><span>{x[2]}</span><strong>{x[1]}</strong><small>{x[0]}</small></div>)}
    </div>
    <div className="grid-2">
      <Panel title="FSMO ROLE OWNERS" code="FSMO"><KV items={[['PDC EMULATOR',data.d.pdc],['RID MASTER',data.d.rid],['INFRASTRUCTURE',data.d.infrastructure],['SCHEMA MASTER',data.d.schema],['NAMING MASTER',data.d.naming]]}/></Panel>
      <Panel title="REPLICATION STATUS" code="REPL" actions={<Button icon={RefreshCw} onClick={load}>REFRESH</Button>}><Table rows={data.r.slice(0,8)} rowKey="server" cols={[{key:'server',label:'SERVER'},{key:'partner',label:'PARTNER'},{key:'failures',label:'FAIL'},{key:'status',label:'STATE',render:v=><Status ok={v==='Healthy'}>{v}</Status>}]} /></Panel>
    </div>
  </div>
}

function Domain({notify}){
  const[state,setState]=useState({summary:null,controllers:[],replication:[],trusts:[],sites:[],subnets:[],policy:null,fgpp:[]}),[loading,setLoading]=useState(true)
  async function load(){setLoading(true);try{
    const[s,c,r,t,si,sn,p,fp]=await Promise.all(['/summary','/controllers','/replication','/trusts','/sites','/subnets','/password-policy','/password-policies'].map(x=>api('/api/domain'+x)))
    setState({summary:s,controllers:c,replication:r,trusts:t,sites:si,subnets:sn,policy:p,fgpp:fp})
  }catch(e){notify(e.message,'bad')}finally{setLoading(false)}}
  useEffect(()=>{load()},[])
  if(loading)return <div className="loading">QUERYING DOMAIN CONTROLLERS...</div>
  const s=state.summary||{},p=state.policy||{}
  return <div className="stack">
    <Panel title="DOMAIN / FOREST IDENTITY" code="ROOT" actions={<Button icon={RefreshCw} onClick={load}>REFRESH</Button>}><KV items={[['DOMAIN',s.domain],['FOREST',s.forest],['DOMAIN MODE',s.domainMode],['FOREST MODE',s.forestMode],['RECYCLE BIN',s.recycleBin?'ENABLED':'DISABLED']]}/></Panel>
    <Panel title="DOMAIN CONTROLLERS" code="DC"><Table rows={state.controllers} rowKey="name" cols={[{key:'name',label:'NAME'},{key:'site',label:'SITE'},{key:'ipv4',label:'IPV4'},{key:'os',label:'OS'},{key:'globalCatalog',label:'GC',render:v=><Status ok={v}>{v?'YES':'NO'}</Status>}]} /></Panel>
    <div className="grid-2">
      <Panel title="DEFAULT DOMAIN PASSWORD POLICY" code="PASS"><KV items={[['MIN LENGTH',p.minPasswordLength],['MAX AGE / DAYS',p.maxPasswordAgeDays],['HISTORY',p.passwordHistoryCount],['COMPLEXITY',p.complexityEnabled?'ENABLED':'DISABLED'],['LOCKOUT THRESHOLD',p.lockoutThreshold],['LOCKOUT DURATION / MIN',p.lockoutDurationMinutes]]}/></Panel>
      <Panel title="FINE-GRAINED PASSWORD POLICIES" code="FGPP"><Table rows={state.fgpp} rowKey="name" cols={[{key:'name',label:'POLICY'},{key:'precedence',label:'PRECEDENCE'},{key:'minPasswordLength',label:'MIN LEN'},{key:'maxPasswordAgeDays',label:'MAX AGE'},{key:'lockoutThreshold',label:'LOCKOUT'}]} /></Panel>
    </div>
    <div className="grid-2">
      <Panel title="TRUSTS" code="TRST"><Table rows={state.trusts} rowKey="name" cols={[{key:'name',label:'TRUST'},{key:'direction',label:'DIRECTION'},{key:'type',label:'TYPE'},{key:'transitive',label:'TRANSITIVE',render:v=><Status ok={v}>{v?'YES':'NO'}</Status>}]} /></Panel>
      <Panel title="SITES / SUBNETS" code="SITE"><Table rows={state.sites} rowKey="name" cols={[{key:'name',label:'SITE'},{key:'subnets',label:'SUBNETS'}]} /><div className="subsection"><span className="eyebrow">SUBNET DIRECTORY</span>{state.subnets.map(x=><div className="mini-row" key={x.name}><Wifi size={13}/><span>{x.name}</span><small>{x.site||'UNASSIGNED'}</small></div>)}</div></Panel>
    </div>
    <Panel title="REPLICATION PARTNERS" code="REPL"><Table rows={state.replication} rowKey="partner" cols={[{key:'server',label:'SERVER'},{key:'partner',label:'PARTNER'},{key:'lastSuccess',label:'LAST SUCCESS'},{key:'failures',label:'FAILURES'},{key:'status',label:'STATE',render:v=><Status ok={v==='Healthy'}>{v}</Status>}]} /></Panel>
  </div>
}

function UsersPage({notify}){
  const[rows,setRows]=useState([]),[q,setQ]=useState(''),[selected,setSelected]=useState(null),[detail,setDetail]=useState(null),[groups,setGroups]=useState([]),[modal,setModal]=useState(null),[tab,setTab]=useState('General'),[page,setPage]=useState(1)
  const perPage=15
  async function load(){try{const r=await api('/api/ad/users'+(q?'?q='+enc(q):''));setRows(r);setPage(1);if(!selected&&r[0])open(r[0])}catch(e){notify(e.message,'bad')}}
  async function open(r){setSelected(r);try{const[d,g]=await Promise.all([api('/api/ad/users/'+enc(r.samAccountName)),api('/api/ad/users/'+enc(r.samAccountName)+'/groups')]);setDetail(d);setGroups(g)}catch(e){notify(e.message,'bad')}}
  async function act(path,method='POST',body){try{await api(path,{method,body:body?JSON.stringify(body):undefined});notify('COMMAND COMPLETED','ok');await load();if(selected)await open(selected)}catch(e){notify(e.message,'bad')}}
  useEffect(()=>{load()},[])
  const createFields=[['sam_account_name','SAM ACCOUNT'],['given_name','GIVEN NAME'],['surname','SURNAME'],['display_name','DISPLAY NAME'],['email','EMAIL'],['department','DEPARTMENT'],['title','TITLE'],['company','COMPANY'],['manager','MANAGER (SAM/DN)'],['ou','TARGET OU DN'],['password','INITIAL PASSWORD','password']]
  const pageCount=Math.max(1,Math.ceil(rows.length/perPage)), visible=rows.slice((page-1)*perPage,page*perPage)
  const domain=(detail?.dn||'').split(',').filter(x=>x.startsWith('DC=')).map(x=>x.slice(3)).join('.').toUpperCase()||'ACTIVE DIRECTORY'
  function exportCsv(){
    const headers=['displayName','samAccountName','mail','department','title','enabled','lastLogon']
    const csv=[headers.join(','),...rows.map(r=>headers.map(h=>`"${String(r[h]??'').replaceAll('"','""')}"`).join(','))].join('\n')
    const blob=new Blob([csv],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a')
    a.href=url;a.download='rsat-users.csv';a.click();URL.revokeObjectURL(url);notify('CSV EXPORTED','ok')
  }
  const detailRows={
    General:[['Full Name',detail?.displayName],['Display Name',detail?.displayName],['Username',detail?.samAccountName],['Email',detail?.mail],['Department',detail?.department],['Title',detail?.title],['Company',detail?.company],['Manager',detail?.manager],['Mobile',detail?.mobile],['Employee ID',detail?.employeeId],['Distinguished Name',detail?.dn]],
    Organization:[['Department',detail?.department],['Title',detail?.title],['Company',detail?.company],['Manager',detail?.manager],['Office',detail?.office]],
    Account:[['Status',detail?.enabled?'Enabled':'Disabled'],['Locked Out',detail?.lockedOut?'Yes':'No'],['Last Logon',detail?.lastLogon],['Created',detail?.created],['Password Last Set',detail?.passwordLastSet],['Password Expires',detail?.passwordExpires],['Password Never Expires',detail?.passwordNeverExpires?'Yes':'No']],
    'Member Of':groups.map(g=>[g.name,g.scope||'Group']),
    Attributes:Object.entries(detail||{}).filter(([k])=>!['displayName'].includes(k)).map(([k,v])=>[k,typeof v==='object'?JSON.stringify(v):v])
  }
  return <div className="users-screen">
    <section className="directory-users window-frame">
      <div className="window-title"><span>DIRECTORY USERS &nbsp;[ {domain} ]</span><span>⌄ &nbsp;×</span></div>
      <div className="users-toolbar">
        <div className="main-search"><Search size={14}/><input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&load()} placeholder="Search users... (name, username, email, department)"/><button onClick={load}><Search size={14}/></button></div>
        <button className="square-tool" title="Filter"><Filter size={14}/></button>
        <button className="toolbar-btn" onClick={()=>setModal('create')}><Plus size={14}/> New User</button>
        <button className="toolbar-btn" onClick={()=>notify('Bulk import will require a CSV mapping profile','bad')}><Upload size={13}/> Import <ChevronDown size={11}/></button>
        <button className="toolbar-btn" onClick={exportCsv}><Download size={13}/> Export <ChevronDown size={11}/></button>
        <button className="square-tool"><MoreHorizontal size={15}/></button>
      </div>
      <div className="users-table-wrap">
        <table className="users-table"><thead><tr><th>#</th><th>Display Name</th><th>Username</th><th>Department</th><th>Title</th><th>Status</th><th>Last Logon ↓</th></tr></thead><tbody>
          {visible.map((r,i)=><tr key={r.samAccountName} className={selected?.samAccountName===r.samAccountName?'selected':''} onClick={()=>open(r)}>
            <td>{(page-1)*perPage+i+1}</td><td>{r.displayName}</td><td>{r.samAccountName}</td><td>{r.department||'—'}</td><td>{r.title||'—'}</td>
            <td><Status ok={r.enabled}>{r.enabled?'Enabled':'Disabled'}</Status>{r.lockedOut&&<span className="locked-flag">Locked</span>}</td><td>{r.lastLogon?new Date(r.lastLogon).toLocaleString():'—'}</td>
          </tr>)}
        </tbody></table>
      </div>
      <div className="pagination-bar">
        <span>Showing {(page-1)*perPage+1} to {Math.min(page*perPage,rows.length)} of {rows.length} users</span>
        <div className="pages"><button disabled={page===1} onClick={()=>setPage(Math.max(1,page-1))}>‹</button>{Array.from({length:Math.min(5,pageCount)},(_,i)=>i+1).map(n=><button key={n} className={page===n?'active':''} onClick={()=>setPage(n)}>{n}</button>)}{pageCount>5&&<><span>...</span><button onClick={()=>setPage(pageCount)}>{pageCount}</button></>}<button disabled={page===pageCount} onClick={()=>setPage(Math.min(pageCount,page+1))}>›</button></div>
        <label>Show: <select value={perPage} disabled><option>15</option></select></label>
      </div>
    </section>
    <aside className="user-inspector">
      <section className="window-frame user-details">
        <div className="window-title"><span>USER DETAILS</span><span>⌄ &nbsp;×</span></div>
        {!detail?<div className="empty">SELECT A USER</div>:<>
          <div className="identity-block">
            <div className="portrait"><Users size={34}/></div>
            <div className="identity-main"><h3>{detail.displayName}</h3><p>{detail.mail||detail.samAccountName}</p><div><span>Status:</span><Status ok={detail.enabled}>{detail.enabled?'Enabled':'Disabled'}</Status></div><div><span>Last Logon:</span><b>{detail.lastLogon?new Date(detail.lastLogon).toLocaleString():'—'}</b></div><div><span>Created:</span><b>{detail.created?new Date(detail.created).toLocaleString():'—'}</b></div><div><span>Password Last Set:</span><b>{detail.passwordLastSet?new Date(detail.passwordLastSet).toLocaleString():'—'}</b></div><div><span>Password Expires:</span><b>{detail.passwordExpires?new Date(detail.passwordExpires).toLocaleString():'—'}</b></div></div>
          </div>
          <div className="detail-tabs">{['General','Organization','Account','Member Of','Attributes'].map(x=><button key={x} className={tab===x?'active':''} onClick={()=>setTab(x)}>{x}</button>)}</div>
          <div className="detail-list">{(detailRows[tab]||[]).map(([k,v])=><div key={String(k)}><span>{k}</span><b>{String(v??'—')}</b></div>)}</div>
        </>}
      </section>
      <section className="window-frame action-window">
        <div className="window-title"><span>ACTIONS</span><span>×</span></div>
        <div className="inspector-actions">
          <Button icon={UserRoundCog} onClick={()=>detail&&setModal('edit')}>Edit Attributes</Button>
          <Button icon={UnlockKeyhole} onClick={()=>detail&&act('/api/ad/users/'+enc(detail.samAccountName)+'/unlock')}>Unlock Account</Button>
          <Button icon={KeyRound} onClick={()=>detail&&setModal('password')}>Reset Password</Button>
          <Button icon={LockKeyhole} onClick={()=>detail&&act('/api/ad/users/'+enc(detail.samAccountName)+'/disable')}>Disable Account</Button>
          <Button icon={FolderTree} onClick={()=>detail&&setModal('move')}>Move to OU</Button>
          <Button icon={UnlockKeyhole} onClick={()=>detail&&act('/api/ad/users/'+enc(detail.samAccountName)+'/enable')}>Enable Account</Button>
          <Button icon={Trash2} kind="danger" onClick={()=>detail&&setModal('delete')}>Delete User</Button>
          <Button icon={Group} onClick={()=>setTab('Member Of')}>Change Groups</Button>
        </div>
      </section>
    </aside>
    {modal==='create'&&<Modal title="CREATE DIRECTORY USER" fields={createFields.map(x=>({name:x[0],label:x[1],type:x[2]})).concat([{name:'enabled',label:'ACCOUNT ENABLED',type:'checkbox',default:true},{name:'must_change',label:'CHANGE PASSWORD AT LOGON',type:'checkbox',default:true}])} onClose={()=>setModal(null)} onSubmit={async v=>{await api('/api/ad/users',{method:'POST',body:JSON.stringify(v)});notify('USER CREATED','ok');load()}}/>}
    {modal==='edit'&&detail&&<Modal title={'EDIT '+detail.samAccountName} initial={{display_name:detail.displayName,email:detail.mail,department:detail.department,title:detail.title,company:detail.company,manager:detail.manager,mobile:detail.mobile}} fields={[{name:'display_name',label:'DISPLAY NAME'},{name:'email',label:'EMAIL'},{name:'department',label:'DEPARTMENT'},{name:'title',label:'TITLE'},{name:'company',label:'COMPANY'},{name:'manager',label:'MANAGER'},{name:'mobile',label:'MOBILE'}]} onClose={()=>setModal(null)} onSubmit={v=>act('/api/ad/users/'+enc(detail.samAccountName),'PATCH',v)}/>}
    {modal==='password'&&detail&&<Modal title={'RESET PASSWORD / '+detail.samAccountName} fields={[{name:'new_password',label:'NEW PASSWORD',type:'password'},{name:'must_change',label:'CHANGE AT NEXT LOGON',type:'checkbox',default:true}]} onClose={()=>setModal(null)} onSubmit={v=>act('/api/ad/users/'+enc(detail.samAccountName)+'/reset-password','POST',v)}/>}
    {modal==='move'&&detail&&<Modal title={'MOVE USER / '+detail.samAccountName} fields={[{name:'target_ou',label:'TARGET OU DISTINGUISHED NAME'}]} onClose={()=>setModal(null)} onSubmit={v=>act('/api/ad/users/'+enc(detail.samAccountName)+'/move','POST',v)}/>}
    {modal==='delete'&&detail&&<Modal title={'DELETE '+detail.samAccountName+' ?'} subtitle="This removes the Active Directory object. Use the Recycle Bin if recovery is required." fields={[]} danger submitLabel="DELETE OBJECT" onClose={()=>setModal(null)} onSubmit={()=>act('/api/ad/users/'+enc(detail.samAccountName),'DELETE')}/>}
  </div>
}

function GroupsPage({notify}){
  const[rows,setRows]=useState([]),[sel,setSel]=useState(null),[members,setMembers]=useState([]),[modal,setModal]=useState(null)
  async function load(){try{setRows(await api('/api/ad/groups'))}catch(e){notify(e.message,'bad')}}
  async function open(r){setSel(r);try{setMembers(await api('/api/ad/groups/'+enc(r.name)+'/members'))}catch(e){notify(e.message,'bad')}}
  async function command(path,method='POST',body){try{await api(path,{method,body:body?JSON.stringify(body):undefined});notify('GROUP COMMAND COMPLETED','ok');load();if(sel)open(sel)}catch(e){notify(e.message,'bad')}}
  useEffect(()=>{load()},[])
  return <div className="split"><Panel title="SECURITY / DISTRIBUTION GROUPS" code="GRP" actions={<><Button icon={Plus} kind="primary" onClick={()=>setModal('create')}>NEW GROUP</Button><Button icon={RefreshCw} onClick={load}>REFRESH</Button></>}>
    <Table rows={rows} rowKey="name" selectedKey={sel?.name} onRow={open} cols={[{key:'name',label:'GROUP'},{key:'category',label:'CATEGORY'},{key:'scope',label:'SCOPE'},{key:'members',label:'MEMBERS'}]}/>
  </Panel><Panel title="MEMBERSHIP INSPECTOR" code="MBR" className="inspector">{!sel?<div className="empty">SELECT A GROUP</div>:<>
    <div className="object-head"><div className="avatar"><Group/></div><div><h3>{sel.name}</h3><p>{sel.description||'NO DESCRIPTION'}</p></div></div>
    <div className="panel-actions left"><Button icon={Plus} onClick={()=>setModal('add')}>ADD MEMBER</Button><Button icon={Trash2} kind="danger" onClick={()=>setModal('delete')}>DELETE GROUP</Button></div>
    <div className="subsection">{members.map(m=><div className="mini-row" key={m.dn||m.samAccountName}><Users size={13}/><span>{m.name}</span><small>{m.objectClass}</small><button className="tiny-danger" onClick={()=>command('/api/ad/groups/'+enc(sel.name)+'/members/'+enc(m.samAccountName||m.dn),'DELETE')}>REMOVE</button></div>)}</div>
  </>}</Panel>
  {modal==='create'&&<Modal title="CREATE GROUP" fields={[{name:'name',label:'GROUP NAME'},{name:'scope',label:'SCOPE',type:'select',options:['Global','DomainLocal','Universal'],default:'Global'},{name:'category',label:'CATEGORY',type:'select',options:['Security','Distribution'],default:'Security'},{name:'path',label:'TARGET OU DN'},{name:'description',label:'DESCRIPTION'}]} onClose={()=>setModal(null)} onSubmit={async v=>{await api('/api/ad/groups',{method:'POST',body:JSON.stringify(v)});notify('GROUP CREATED','ok');load()}}/>}
  {modal==='add'&&sel&&<Modal title={'ADD MEMBER / '+sel.name} fields={[{name:'member',label:'USER OR OBJECT IDENTITY'}]} onClose={()=>setModal(null)} onSubmit={v=>command('/api/ad/groups/'+enc(sel.name)+'/members','POST',v)}/>}
  {modal==='delete'&&sel&&<Modal title={'DELETE GROUP / '+sel.name} fields={[]} danger submitLabel="DELETE GROUP" onClose={()=>setModal(null)} onSubmit={()=>command('/api/ad/groups/'+enc(sel.name),'DELETE')}/>}
  </div>
}

function ComputersPage({notify}){
  const[rows,setRows]=useState([]),[q,setQ]=useState(''),[sel,setSel]=useState(null),[modal,setModal]=useState(null)
  async function load(){try{setRows(await api('/api/ad/computers'+(q?'?q='+enc(q):'')))}catch(e){notify(e.message,'bad')}}
  async function command(path,method='POST',body){try{await api(path,{method,body:body?JSON.stringify(body):undefined});notify('COMPUTER COMMAND COMPLETED','ok');load()}catch(e){notify(e.message,'bad')}}
  useEffect(()=>{load()},[])
  return <div className="split"><Panel title="DOMAIN COMPUTERS" code="CMP" actions={<><div className="searchbox"><Search size={14}/><input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&load()} placeholder="hostname"/></div><Button icon={RefreshCw} onClick={load}>REFRESH</Button></>}>
    <Table rows={rows} rowKey="name" selectedKey={sel?.name} onRow={setSel} cols={[{key:'name',label:'HOSTNAME'},{key:'os',label:'OPERATING SYSTEM'},{key:'ipv4',label:'IPV4'},{key:'enabled',label:'STATE',render:v=><Status ok={v}>{v?'ENABLED':'DISABLED'}</Status>},{key:'lastLogon',label:'LAST LOGON'}]}/>
  </Panel><Panel title="COMPUTER OBJECT" code="OBJ" className="inspector">{!sel?<div className="empty">SELECT A COMPUTER</div>:<>
    <div className="object-head"><div className="avatar"><Computer/></div><div><h3>{sel.name}</h3><p>{sel.os}</p></div></div><KV items={[['IPV4',sel.ipv4],['LAST LOGON',sel.lastLogon],['OU',sel.ou],['STATE',sel.enabled?'ENABLED':'DISABLED']]}/>
    <div className="action-grid"><Button onClick={()=>command('/api/ad/computers/'+enc(sel.name)+'/'+(sel.enabled?'disable':'enable'))}>{sel.enabled?'DISABLE':'ENABLE'}</Button><Button icon={RefreshCw} onClick={()=>setModal('reset')}>RESET ACCOUNT</Button><Button icon={FolderTree} onClick={()=>setModal('move')}>MOVE OU</Button><Button icon={Trash2} kind="danger" onClick={()=>setModal('delete')}>DELETE</Button></div>
  </>}</Panel>
  {modal==='move'&&sel&&<Modal title={'MOVE '+sel.name} fields={[{name:'target_ou',label:'TARGET OU DN'}]} onClose={()=>setModal(null)} onSubmit={v=>command('/api/ad/computers/'+enc(sel.name)+'/move','POST',v)}/>}
  {modal==='reset'&&sel&&<Modal title={'RESET COMPUTER ACCOUNT / '+sel.name} subtitle="The workstation may need its secure channel repaired or to be rejoined." fields={[]} submitLabel="RESET ACCOUNT" onClose={()=>setModal(null)} onSubmit={()=>command('/api/ad/computers/'+enc(sel.name)+'/reset')}/>}
  {modal==='delete'&&sel&&<Modal title={'DELETE COMPUTER / '+sel.name} fields={[]} danger submitLabel="DELETE OBJECT" onClose={()=>setModal(null)} onSubmit={()=>command('/api/ad/computers/'+enc(sel.name),'DELETE')}/>}
  </div>
}

function OUsPage({notify}){
  const[rows,setRows]=useState([]),[sel,setSel]=useState(null),[modal,setModal]=useState(null)
  async function load(){try{setRows(await api('/api/ad/ous'))}catch(e){notify(e.message,'bad')}}
  useEffect(()=>{load()},[])
  async function create(v){try{await api('/api/ad/ous',{method:'POST',body:JSON.stringify(v)});notify('OU CREATED','ok');load()}catch(e){throw e}}
  async function del(v){try{await api('/api/ad/ous/delete',{method:'POST',body:JSON.stringify({dn:sel.dn,recursive:v.recursive})});notify('OU DELETED','ok');setSel(null);load()}catch(e){throw e}}
  return <div className="split"><Panel title="ORGANIZATIONAL UNIT TREE" code="OU" actions={<><Button icon={Plus} kind="primary" onClick={()=>setModal('create')}>NEW OU</Button><Button icon={RefreshCw} onClick={load}>REFRESH</Button></>}><Table rows={rows} rowKey="dn" selectedKey={sel?.dn} onRow={setSel} cols={[{key:'name',label:'OU'},{key:'dn',label:'DISTINGUISHED NAME'},{key:'protected',label:'PROTECTED',render:v=><Status ok={v}>{v?'YES':'NO'}</Status>}]} /></Panel>
  <Panel title="OU INSPECTOR" code="OBJ" className="inspector">{sel?<><KV items={[['NAME',sel.name],['DN',sel.dn],['ACCIDENTAL DELETE PROTECTION',sel.protected?'ENABLED':'DISABLED']]}/><Button icon={Trash2} kind="danger" onClick={()=>setModal('delete')}>DELETE OU</Button></>:<div className="empty">SELECT AN OU</div>}</Panel>
  {modal==='create'&&<Modal title="CREATE ORGANIZATIONAL UNIT" fields={[{name:'name',label:'OU NAME'},{name:'path',label:'PARENT DN'},{name:'protected',label:'PROTECT FROM ACCIDENTAL DELETION',type:'checkbox',default:true}]} onClose={()=>setModal(null)} onSubmit={create}/>}
  {modal==='delete'&&sel&&<Modal title={'DELETE OU / '+sel.name} subtitle="Recursive deletion will remove all child objects. Keep it off unless explicitly required." fields={[{name:'recursive',label:'RECURSIVE DELETE',type:'checkbox',default:false}]} danger submitLabel="DELETE OU" onClose={()=>setModal(null)} onSubmit={del}/>}
  </div>
}

function RecyclePage({notify}){
  const[rows,setRows]=useState([]),[sel,setSel]=useState(null),[modal,setModal]=useState(null)
  async function load(){try{setRows(await api('/api/ad/deleted'))}catch(e){notify(e.message,'bad')}}
  useEffect(()=>{load()},[])
  async function restore(v){await api('/api/ad/deleted/restore',{method:'POST',body:JSON.stringify({object_guid:sel.objectGuid,target_path:v.target_path||''})});notify('OBJECT RESTORED','ok');setSel(null);load()}
  return <div className="split"><Panel title="ACTIVE DIRECTORY RECYCLE BIN" code="RCY" actions={<Button icon={RefreshCw} onClick={load}>REFRESH</Button>}><Table rows={rows} rowKey="objectGuid" selectedKey={sel?.objectGuid} onRow={setSel} cols={[{key:'name',label:'DELETED OBJECT'},{key:'objectClass',label:'CLASS'},{key:'lastKnownParent',label:'LAST KNOWN PARENT'},{key:'deletedAt',label:'DELETED AT'}]}/></Panel>
  <Panel title="RESTORE INSPECTOR" code="OBJ" className="inspector">{sel?<><div className="object-head"><div className="avatar"><Archive/></div><div><h3>{sel.name}</h3><p>{sel.objectGuid}</p></div></div><KV items={[['CLASS',sel.objectClass],['LAST KNOWN PARENT',sel.lastKnownParent],['DELETED AT',sel.deletedAt]]}/><div className="action-grid"><Button icon={RefreshCw} kind="primary" onClick={()=>setModal('restore')}>RESTORE OBJECT</Button></div></>:<div className="empty">SELECT A DELETED OBJECT</div>}</Panel>
  {modal==='restore'&&sel&&<Modal title={'RESTORE / '+sel.name} subtitle="Leave target empty to restore to last known parent, or provide a different DN." fields={[{name:'target_path',label:'OPTIONAL TARGET DN'}]} onClose={()=>setModal(null)} onSubmit={restore}/>}
  </div>
}

function DNSPage({notify}){
  const[zones,setZones]=useState([]),[zone,setZone]=useState(''),[records,setRecords]=useState([]),[sel,setSel]=useState(null),[modal,setModal]=useState(null)
  async function loadZones(){const z=await api('/api/dns/zones');setZones(z);if(!zone&&z[0])setZone(z[0].name);if(zone&&!z.some(x=>x.name===zone))setZone(z[0]?.name||'')}
  async function loadRecords(){try{setRecords(await api('/api/dns/records'+(zone?'?zone='+enc(zone):'')))}catch(e){notify(e.message,'bad')}}
  useEffect(()=>{loadZones().catch(e=>notify(e.message,'bad'))},[])
  useEffect(()=>{if(zone)loadRecords()},[zone])
  async function create(v){await api('/api/dns/records',{method:'POST',body:JSON.stringify(v)});notify('DNS RECORD CREATED','ok');loadRecords()}
  async function del(){await api('/api/dns/records/delete',{method:'POST',body:JSON.stringify(sel)});notify('DNS RECORD REMOVED','ok');setSel(null);loadRecords()}
  async function createZone(v){await api('/api/dns/zones',{method:'POST',body:JSON.stringify(v)});notify('DNS ZONE CREATED','ok');await loadZones()}
  async function deleteZone(){await api('/api/dns/zones/delete',{method:'POST',body:JSON.stringify({name:zone})});notify('DNS ZONE DELETED','ok');setSel(null);setZone('');await loadZones()}
  const z=zones.find(x=>x.name===zone)
  return <div className="split"><Panel title="DNS RESOURCE RECORDS" code="DNS" actions={<><select className="toolbar-select" value={zone} onChange={e=>setZone(e.target.value)}>{zones.map(z=><option key={z.name}>{z.name}</option>)}</select><Button icon={Plus} onClick={()=>setModal('zone')}>NEW ZONE</Button><Button icon={Plus} kind="primary" disabled={!zone} onClick={()=>setModal('create')}>NEW RECORD</Button><Button icon={RefreshCw} onClick={loadRecords}>REFRESH</Button></>}><Table rows={records} rowKey="name" selectedKey={sel?.name} onRow={setSel} cols={[{key:'name',label:'NAME'},{key:'type',label:'TYPE'},{key:'value',label:'VALUE'},{key:'ttl',label:'TTL'}]}/></Panel>
  <Panel title="ZONE / RECORD INSPECTOR" code="OBJ" className="inspector"><KV items={[['ZONE',zone],['ZONE TYPE',z?.type],['AD INTEGRATED',z?.integrated?'YES':'NO'],['REVERSE LOOKUP',z?.reverse?'YES':'NO']]}/>{zone&&<div className="action-grid"><Button icon={Trash2} kind="danger" onClick={()=>setModal('zoneDelete')}>DELETE ZONE</Button></div>}{sel&&<><div className="subsection"><KV items={[['RECORD',sel.name],['TYPE',sel.type],['VALUE',sel.value],['TTL',sel.ttl]]}/></div><div className="action-grid"><Button icon={Trash2} kind="danger" onClick={()=>setModal('delete')}>DELETE RECORD</Button></div></>}</Panel>
  {modal==='zone'&&<Modal title="CREATE AD-INTEGRATED DNS ZONE" fields={[{name:'name',label:'ZONE NAME'},{name:'replication_scope',label:'REPLICATION SCOPE',type:'select',options:['Domain','Forest','Legacy'],default:'Domain'},{name:'dynamic_update',label:'DYNAMIC UPDATE',type:'select',options:['Secure','NonsecureAndSecure','None'],default:'Secure'}]} onClose={()=>setModal(null)} onSubmit={createZone}/>}
  {modal==='zoneDelete'&&zone&&<Modal title={'DELETE DNS ZONE / '+zone} subtitle="This removes the entire DNS zone and all records in it." fields={[]} danger submitLabel="DELETE ZONE" onClose={()=>setModal(null)} onSubmit={deleteZone}/>}
  {modal==='create'&&<Modal title={'CREATE DNS RECORD / '+zone} initial={{zone,type:'A',ttl:3600}} fields={[{name:'zone',label:'ZONE'},{name:'name',label:'NAME'},{name:'type',label:'TYPE',type:'select',options:['A','AAAA','CNAME','PTR'],default:'A'},{name:'value',label:'VALUE / TARGET'},{name:'ttl',label:'TTL SECONDS',type:'number',default:3600}]} onClose={()=>setModal(null)} onSubmit={create}/>}
  {modal==='delete'&&sel&&<Modal title={'DELETE DNS RECORD / '+sel.name} fields={[]} danger submitLabel="DELETE RECORD" onClose={()=>setModal(null)} onSubmit={del}/>}
  </div>
}

function DHCPPage({notify}){
  const[scopes,setScopes]=useState([]),[scope,setScope]=useState(''),[leases,setLeases]=useState([]),[reservations,setReservations]=useState([]),[tab,setTab]=useState('leases'),[sel,setSel]=useState(null),[modal,setModal]=useState(null)
  async function loadScopes(){const s=await api('/api/dhcp/scopes');setScopes(s);if(!scope&&s[0])setScope(s[0].scopeId);if(scope&&!s.some(x=>x.scopeId===scope))setScope(s[0]?.scopeId||'')}
  async function loadData(){if(!scope)return;try{const[l,r]=await Promise.all([api('/api/dhcp/leases?scope_id='+enc(scope)),api('/api/dhcp/reservations?scope_id='+enc(scope))]);setLeases(l);setReservations(r)}catch(e){notify(e.message,'bad')}}
  useEffect(()=>{loadScopes().catch(e=>notify(e.message,'bad'))},[])
  useEffect(()=>{loadData()},[scope])
  async function create(v){await api('/api/dhcp/reservations',{method:'POST',body:JSON.stringify(v)});notify('RESERVATION CREATED','ok');loadData()}
  async function del(){await api('/api/dhcp/reservations/delete',{method:'POST',body:JSON.stringify({scope_id:sel.scopeId,ip_address:sel.ipAddress})});notify('RESERVATION REMOVED','ok');setSel(null);loadData()}
  async function createScope(v){await api('/api/dhcp/scopes',{method:'POST',body:JSON.stringify(v)});notify('DHCP SCOPE CREATED','ok');await loadScopes()}
  async function scopeState(state){await api('/api/dhcp/scopes/state',{method:'POST',body:JSON.stringify({scope_id:scope,state})});notify('SCOPE STATE UPDATED','ok');await loadScopes()}
  async function deleteScope(){await api('/api/dhcp/scopes/delete',{method:'POST',body:JSON.stringify({scope_id:scope})});notify('DHCP SCOPE DELETED','ok');setScope('');await loadScopes()}
  const s=scopes.find(x=>x.scopeId===scope)
  return <div className="stack"><Panel title="DHCP SCOPE SELECTOR" code="DHC" actions={<><select className="toolbar-select" value={scope} onChange={e=>setScope(e.target.value)}>{scopes.map(x=><option key={x.scopeId} value={x.scopeId}>{x.scopeId} / {x.name}</option>)}</select><Button icon={Plus} kind="primary" onClick={()=>setModal('scopeCreate')}>NEW SCOPE</Button>{s&&<Button onClick={()=>scopeState(s.state==='Active'?'Inactive':'Active')}>{s.state==='Active'?'DEACTIVATE':'ACTIVATE'}</Button>}{s&&<Button icon={Trash2} kind="danger" onClick={()=>setModal('scopeDelete')}>DELETE SCOPE</Button>}<Button icon={RefreshCw} onClick={loadData}>REFRESH</Button></>}><div className="metrics compact">{s&&[['STATE',s.state,'STA'],['RANGE',s.startRange+' — '+s.endRange,'RNG'],['IN USE',s.inUse,'USE'],['FREE',s.free,'FRE']].map(x=><div className="metric" key={x[0]}><span>{x[2]}</span><strong>{x[1]}</strong><small>{x[0]}</small></div>)}</div></Panel>
  <Panel title="ADDRESS ALLOCATION" code="ADDR" actions={<><Button kind={tab==='leases'?'active':''} onClick={()=>{setTab('leases');setSel(null)}}>LEASES</Button><Button kind={tab==='reservations'?'active':''} onClick={()=>{setTab('reservations');setSel(null)}}>RESERVATIONS</Button>{tab==='reservations'&&<Button icon={Plus} kind="primary" onClick={()=>setModal('create')}>NEW RESERVATION</Button>}</>}>
    {tab==='leases'?<Table rows={leases} rowKey="ipAddress" cols={[{key:'ipAddress',label:'IP ADDRESS'},{key:'hostName',label:'HOSTNAME'},{key:'clientId',label:'CLIENT ID'},{key:'state',label:'STATE'},{key:'expiry',label:'EXPIRY'}]}/>:<Table rows={reservations} rowKey="ipAddress" selectedKey={sel?.ipAddress} onRow={setSel} cols={[{key:'ipAddress',label:'IP ADDRESS'},{key:'name',label:'NAME'},{key:'clientId',label:'CLIENT ID'},{key:'description',label:'DESCRIPTION'}]}/>}
    {tab==='reservations'&&sel&&<div className="inline-tools"><Button icon={Trash2} kind="danger" onClick={()=>setModal('delete')}>DELETE SELECTED RESERVATION</Button></div>}
  </Panel>
  {modal==='scopeCreate'&&<Modal title="CREATE DHCP IPV4 SCOPE" fields={[{name:'name',label:'SCOPE NAME'},{name:'start_range',label:'START RANGE'},{name:'end_range',label:'END RANGE'},{name:'subnet_mask',label:'SUBNET MASK'},{name:'lease_days',label:'LEASE DAYS',type:'number',default:8},{name:'state',label:'INITIAL STATE',type:'select',options:['Active','Inactive'],default:'Active'},{name:'description',label:'DESCRIPTION'}]} onClose={()=>setModal(null)} onSubmit={createScope}/>}
  {modal==='scopeDelete'&&s&&<Modal title={'DELETE DHCP SCOPE / '+scope} subtitle="All leases, reservations and scope settings will be removed." fields={[]} danger submitLabel="DELETE SCOPE" onClose={()=>setModal(null)} onSubmit={deleteScope}/>}
  {modal==='create'&&<Modal title={'CREATE DHCP RESERVATION / '+scope} initial={{scope_id:scope}} fields={[{name:'scope_id',label:'SCOPE ID'},{name:'ip_address',label:'IP ADDRESS'},{name:'client_id',label:'CLIENT ID / MAC'},{name:'name',label:'NAME'},{name:'description',label:'DESCRIPTION'}]} onClose={()=>setModal(null)} onSubmit={create}/>}
  {modal==='delete'&&sel&&<Modal title={'DELETE RESERVATION / '+sel.ipAddress} fields={[]} danger submitLabel="DELETE RESERVATION" onClose={()=>setModal(null)} onSubmit={del}/>}
  </div>
}

function GPOPage({notify}){
  const[rows,setRows]=useState([]),[links,setLinks]=useState([]),[sel,setSel]=useState(null),[permissions,setPermissions]=useState([]),[modal,setModal]=useState(null),[report,setReport]=useState(null)
  async function load(){try{const[g,l]=await Promise.all([api('/api/gpo'),api('/api/gpo/links')]);setRows(g);setLinks(l)}catch(e){notify(e.message,'bad')}}
  async function open(r){setSel(r);try{setPermissions(await api('/api/gpo/'+enc(r.id)+'/permissions'))}catch(e){notify(e.message,'bad')}}
  useEffect(()=>{load()},[])
  async function command(path,method='POST',body){try{const r=await api(path,{method,body:body?JSON.stringify(body):undefined});notify('GPO COMMAND COMPLETED','ok');load();if(sel)open(sel);return r}catch(e){notify(e.message,'bad');throw e}}
  return <div className="split"><Panel title="GROUP POLICY OBJECTS" code="GPO" actions={<><Button icon={Plus} kind="primary" onClick={()=>setModal('create')}>NEW GPO</Button><Button icon={RefreshCw} onClick={load}>REFRESH</Button></>}><Table rows={rows} rowKey="id" selectedKey={sel?.id} onRow={open} cols={[{key:'displayName',label:'GPO'},{key:'status',label:'STATUS'},{key:'owner',label:'OWNER'},{key:'modified',label:'MODIFIED'}]}/></Panel>
  <Panel title="GPO INSPECTOR" code="OBJ" className="inspector">{!sel?<div className="empty">SELECT A POLICY OBJECT</div>:<>
    <div className="object-head"><div className="avatar"><ShieldCheck/></div><div><h3>{sel.displayName}</h3><p>{sel.id}</p></div></div><KV items={[['STATUS',sel.status],['OWNER',sel.owner],['MODIFIED',sel.modified]]}/>
    <div className="action-grid"><Button icon={Link2} onClick={()=>setModal('link')}>LINK</Button><Button icon={Archive} onClick={()=>setModal('backup')}>BACKUP</Button><Button onClick={()=>setModal('status')}>SET STATUS</Button><Button onClick={async()=>{const r=await command('/api/gpo/'+enc(sel.id)+'/report','GET');setReport(r)}}>REPORT</Button><Button icon={KeyRound} onClick={()=>setModal('permission')}>SET ACL</Button><Button icon={Trash2} kind="danger" onClick={()=>setModal('delete')}>DELETE</Button></div>
    <div className="subsection"><span className="eyebrow">SECURITY FILTER / PERMISSIONS</span>{permissions.map((x,i)=><div className="mini-row" key={i}><KeyRound size={13}/><span>{x.trustee}</span><small>{x.permission}</small></div>)}</div>
    <div className="subsection"><span className="eyebrow">LINKS</span>{links.filter(x=>x.displayName===sel.displayName).map((x,i)=><div className="mini-row" key={i}><Link2 size={13}/><span>{x.target}</span><small>{x.enforced?'ENFORCED':'NORMAL'}</small><button className="tiny-danger" onClick={()=>command('/api/gpo/'+enc(sel.id)+'/unlink','POST',{target:x.target,enforced:false,enabled:true})}>UNLINK</button></div>)}</div>
  </>}</Panel>
  {modal==='create'&&<Modal title="CREATE GROUP POLICY OBJECT" fields={[{name:'name',label:'GPO NAME'},{name:'comment',label:'COMMENT'}]} onClose={()=>setModal(null)} onSubmit={v=>command('/api/gpo','POST',v)}/>}
  {modal==='link'&&sel&&<Modal title={'LINK GPO / '+sel.displayName} fields={[{name:'target',label:'TARGET DOMAIN / OU DN'},{name:'enabled',label:'LINK ENABLED',type:'checkbox',default:true},{name:'enforced',label:'ENFORCED',type:'checkbox',default:false},{name:'order',label:'LINK ORDER',type:'number'}]} onClose={()=>setModal(null)} onSubmit={v=>command('/api/gpo/'+enc(sel.id)+'/link','POST',v)}/>}
  {modal==='permission'&&sel&&<Modal title={'SET GPO PERMISSION / '+sel.displayName} fields={[{name:'trustee',label:'USER / GROUP NAME'},{name:'target_type',label:'TARGET TYPE',type:'select',options:['User','Group','Computer'],default:'Group'},{name:'permission',label:'PERMISSION',type:'select',options:['GpoRead','GpoApply','GpoEdit','GpoEditDeleteModifySecurity'],default:'GpoRead'},{name:'replace',label:'REPLACE EXISTING PERMISSION',type:'checkbox',default:false}]} onClose={()=>setModal(null)} onSubmit={v=>command('/api/gpo/'+enc(sel.id)+'/permissions','POST',v)}/>}
  {modal==='backup'&&sel&&<Modal title={'BACKUP GPO / '+sel.displayName} fields={[{name:'path',label:'WINDOWS WORKER BACKUP PATH',default:'C:\\ProgramData\\RsatFull\\GpoBackups'}]} onClose={()=>setModal(null)} onSubmit={v=>command('/api/gpo/'+enc(sel.id)+'/backup','POST',v)}/>}
  {modal==='status'&&sel&&<Modal title={'SET GPO STATUS / '+sel.displayName} fields={[{name:'status',label:'STATUS',type:'select',options:['AllSettingsEnabled','UserSettingsDisabled','ComputerSettingsDisabled','AllSettingsDisabled'],default:sel.status}]} onClose={()=>setModal(null)} onSubmit={v=>command('/api/gpo/'+enc(sel.id)+'/status','POST',v)}/>}
  {modal==='delete'&&sel&&<Modal title={'DELETE GPO / '+sel.displayName} fields={[]} danger submitLabel="DELETE GPO" onClose={()=>setModal(null)} onSubmit={()=>command('/api/gpo/'+enc(sel.id),'DELETE')}/>}
  {report&&<div className="modal-backdrop"><div className="modal report"><div className="modal-head"><div><span className="eyebrow">GPO XML REPORT</span><h3>{report.displayName}</h3></div><button className="x" onClick={()=>setReport(null)}>×</button></div><pre>{report.xml||JSON.stringify(report,null,2)}</pre></div></div>}
  </div>
}

function SettingsPage({notify}){
  const blankDc=()=>({name:'',host:'',ip:'',enabled:true,notes:''})
  const blankSite=()=>({name:'',code:'',description:'',dcs:[blankDc(),blankDc()]})
  const[cfg,setCfg]=useState({demo_mode:true,worker_url:'',worker_token:'',worker_token_configured:false,sites:[]})
  const[loading,setLoading]=useState(true),[busy,setBusy]=useState(''),[tests,setTests]=useState({}),[workerTest,setWorkerTest]=useState(null)

  async function load(){
    setLoading(true)
    try{
      const r=await api('/api/settings')
      setCfg({...r,worker_token:''})
    }catch(e){notify(e.message,'bad')}
    finally{setLoading(false)}
  }
  useEffect(()=>{load()},[])

  function updateSite(si,key,value){
    const sites=cfg.sites.map((s,i)=>i===si?{...s,[key]:value}:s)
    setCfg({...cfg,sites})
  }
  function updateDc(si,di,key,value){
    const sites=cfg.sites.map((s,i)=>i===si?{...s,dcs:s.dcs.map((d,j)=>j===di?{...d,[key]:value}:d)}:s)
    setCfg({...cfg,sites})
  }
  function addSite(){setCfg({...cfg,sites:[...cfg.sites,blankSite()]})}
  function removeSite(si){setCfg({...cfg,sites:cfg.sites.filter((_,i)=>i!==si)})}
  function addDc(si){
    const sites=cfg.sites.map((s,i)=>i===si?{...s,dcs:[...s.dcs,blankDc()]}:s)
    setCfg({...cfg,sites})
  }
  function removeDc(si,di){
    const sites=cfg.sites.map((s,i)=>i===si?{...s,dcs:s.dcs.filter((_,j)=>j!==di)}:s)
    setCfg({...cfg,sites})
  }
  async function save(){
    setBusy('save')
    try{
      await api('/api/settings',{method:'PUT',body:JSON.stringify({
        demo_mode:cfg.demo_mode,worker_url:cfg.worker_url,worker_token:cfg.worker_token||null,
        sites:cfg.sites.map(s=>({name:s.name,code:s.code||'',description:s.description||'',dcs:s.dcs.map(d=>({name:d.name,host:d.host,ip:d.ip||'',enabled:d.enabled!==false,notes:d.notes||''}))}))
      })})
      notify('SETTINGS SAVED — ACTIVE WITHOUT RESTART','ok')
      await load()
    }catch(e){notify(e.message,'bad')}finally{setBusy('')}
  }
  async function testWorker(){
    setBusy('worker')
    try{
      const r=await api('/api/settings/test-worker',{method:'POST',body:JSON.stringify({
        demo_mode:cfg.demo_mode,worker_url:cfg.worker_url,worker_token:cfg.worker_token||null,sites:[]
      })})
      setWorkerTest(r)
      notify('WINDOWS WORKER CONNECTION OK','ok')
    }catch(e){setWorkerTest({ok:false,error:e.message});notify(e.message,'bad')}finally{setBusy('')}
  }
  async function discover(){
    setBusy('discover')
    try{
      const rows=await api('/api/settings/discover-dcs',{method:'POST',body:JSON.stringify({worker_url:cfg.worker_url,worker_token:cfg.worker_token||null,demo_mode:cfg.demo_mode})})
      const grouped={}
      for(const dc of rows){
        const site=dc.site||'Unknown'
        if(!grouped[site]) grouped[site]=[]
        grouped[site].push({name:dc.name||'',host:dc.host||'',ip:dc.ip||'',enabled:dc.enabled!==false,notes:dc.globalCatalog?'Global Catalog':''})
      }
      const sites=Object.entries(grouped).map(([name,dcs])=>({name,code:name.toUpperCase().replace(/[^A-Z0-9]+/g,'-').slice(0,20),description:'Discovered from Active Directory',dcs}))
      setCfg({...cfg,sites})
      notify('DOMAIN CONTROLLERS DISCOVERED — REVIEW AND SAVE','ok')
    }catch(e){notify(e.message,'bad')}finally{setBusy('')}
  }
  async function testDc(si,di){
    const dc=cfg.sites[si].dcs[di]
    if(!dc.host){notify('DC HOST/FQDN IS REQUIRED','bad');return}
    const key=si+'-'+di
    setTests({...tests,[key]:{loading:true}})
    try{
      const r=await api('/api/settings/test-dc',{method:'POST',body:JSON.stringify({host:dc.host,worker_url:cfg.worker_url,worker_token:cfg.worker_token||null,demo_mode:cfg.demo_mode})})
      setTests(x=>({...x,[key]:r}))
      notify((r.ok?'DC REACHABLE: ':'DC CHECK FAILED: ')+dc.host,r.ok?'ok':'bad')
    }catch(e){setTests(x=>({...x,[key]:{ok:false,error:e.message}}));notify(e.message,'bad')}
  }

  const totalDcs=cfg.sites.reduce((n,s)=>n+s.dcs.length,0)
  const activeDcs=cfg.sites.reduce((n,s)=>n+s.dcs.filter(d=>d.enabled!==false).length,0)
  if(loading)return <div className="loading">LOADING SYSTEM CONFIGURATION...</div>
  return <div className="settings-page">
    <section className="window-frame settings-connection">
      <div className="window-title"><span>CONNECTION PROFILE</span><span>CONFIGURATION</span></div>
      <div className="settings-summary">
        <div><span>MODE</span><b>{cfg.demo_mode?'DEMO':'PRODUCTION'}</b></div>
        <div><span>SITES</span><b>{cfg.sites.length}</b></div>
        <div><span>DOMAIN CONTROLLERS</span><b>{totalDcs}</b></div>
        <div><span>ENABLED DCS</span><b>{activeDcs}</b></div>
      </div>
      <div className="connection-config">
        <label className="settings-check"><input type="checkbox" checked={cfg.demo_mode} onChange={e=>setCfg({...cfg,demo_mode:e.target.checked})}/><span>DEMO MODE</span><small>Disable this to use the real Windows RSAT worker.</small></label>
        <label><span>WINDOWS WORKER URL</span><input value={cfg.worker_url||''} onChange={e=>setCfg({...cfg,worker_url:e.target.value})} placeholder="http://windows-management-host:8765"/></label>
        <label><span>WORKER TOKEN</span><input type="password" value={cfg.worker_token||''} onChange={e=>setCfg({...cfg,worker_token:e.target.value})} placeholder={cfg.worker_token_configured?'••••••••  token already configured':'enter worker token'}/><small>{cfg.worker_token_configured?'Leave blank to keep the saved encrypted token.':'Token is encrypted before database storage.'}</small></label>
        <div className="connection-buttons">
          <Button icon={Wifi} onClick={testWorker} disabled={busy==='worker'}>{busy==='worker'?'TESTING...':'TEST WORKER'}</Button>
          <Button icon={Search} onClick={discover} disabled={busy==='discover'}>{busy==='discover'?'DISCOVERING...':'DISCOVER DCS FROM AD'}</Button>
          <Button icon={Download} kind="primary" onClick={save} disabled={busy==='save'}>{busy==='save'?'SAVING...':'SAVE SETTINGS'}</Button>
        </div>
      </div>
      {workerTest&&<div className={'connection-result '+(workerTest.ok?'ok':'bad')}>
        <b>{workerTest.ok?'WORKER ONLINE':'WORKER ERROR'}</b>
        <span>{workerTest.ok?JSON.stringify(workerTest.worker):workerTest.error}</span>
      </div>}
    </section>

    <section className="window-frame sites-config">
      <div className="window-title"><span>SITE / DOMAIN CONTROLLER MATRIX</span><span>{cfg.sites.length} SITES / {totalDcs} DCS</span></div>
      <div className="sites-toolbar">
        <div><b>MULTI-SITE DIRECTORY TOPOLOGY</b><span>Each site can contain two or more domain controllers. Use FQDN whenever possible.</span></div>
        <Button icon={Plus} onClick={addSite}>ADD SITE</Button>
      </div>
      <div className="site-list">
        {!cfg.sites.length&&<div className="empty">NO SITES CONFIGURED — ADD A SITE OR DISCOVER DCS FROM ACTIVE DIRECTORY</div>}
        {cfg.sites.map((site,si)=><section className="site-card" key={si}>
          <div className="site-head">
            <div className="site-fields">
              <label><span>SITE NAME</span><input value={site.name||''} onChange={e=>updateSite(si,'name',e.target.value)} placeholder="Site name"/></label>
              <label><span>CODE</span><input value={site.code||''} onChange={e=>updateSite(si,'code',e.target.value)} placeholder="HQ"/></label>
              <label className="site-description"><span>DESCRIPTION</span><input value={site.description||''} onChange={e=>updateSite(si,'description',e.target.value)} placeholder="Optional description"/></label>
            </div>
            <div className="site-tools"><span>{site.dcs.length} DC</span><Button icon={Plus} onClick={()=>addDc(si)}>ADD DC</Button><Button icon={Trash2} kind="danger" onClick={()=>removeSite(si)}>REMOVE SITE</Button></div>
          </div>
          <div className="dc-table">
            <div className="dc-header"><span>ENABLED</span><span>DC NAME</span><span>HOST / FQDN</span><span>IP ADDRESS</span><span>NOTES</span><span>HEALTH</span><span>ACTIONS</span></div>
            {site.dcs.map((dc,di)=>{
              const result=tests[si+'-'+di]
              return <div className="dc-row" key={di}>
                <label className="dc-enabled"><input type="checkbox" checked={dc.enabled!==false} onChange={e=>updateDc(si,di,'enabled',e.target.checked)}/></label>
                <input value={dc.name||''} onChange={e=>updateDc(si,di,'name',e.target.value)} placeholder="DC01"/>
                <input value={dc.host||''} onChange={e=>updateDc(si,di,'host',e.target.value)} placeholder="dc01.domain.local"/>
                <input value={dc.ip||''} onChange={e=>updateDc(si,di,'ip',e.target.value)} placeholder="10.x.x.x"/>
                <input value={dc.notes||''} onChange={e=>updateDc(si,di,'notes',e.target.value)} placeholder="GC / primary / notes"/>
                <div className="dc-health">{!result?<span className="health unknown">NOT TESTED</span>:result.loading?<span className="health unknown">TESTING</span>:<span className={'health '+(result.ok?'good':'bad')}>{result.ok?'ONLINE':'FAILED'}</span>}{result&&result.ok&&<small>LDAP {result.ldap?'✓':'×'} · KRB {result.kerberos?'✓':'×'} · GC {result.globalCatalog?'✓':'×'}</small>}</div>
                <div className="dc-actions"><button title="Test DC" onClick={()=>testDc(si,di)}><Activity size={13}/></button><button title="Remove DC" onClick={()=>removeDc(si,di)}><Trash2 size={13}/></button></div>
              </div>
            })}
          </div>
        </section>)}
      </div>
      <div className="settings-footer"><span>Changes are stored in PostgreSQL and become active immediately after save.</span><Button icon={Download} kind="primary" onClick={save} disabled={busy==='save'}>SAVE ALL CHANGES</Button></div>
    </section>
  </div>
}

function AuditPage({notify}){
  const[rows,setRows]=useState([])
  async function load(){try{setRows(await api('/api/audit?limit=300'))}catch(e){notify(e.message,'bad')}}
  useEffect(()=>{load()},[])
  return <Panel title="IMMUTABLE CHANGE JOURNAL" code="AUD" actions={<Button icon={RefreshCw} onClick={load}>REFRESH</Button>}><Table rows={rows} rowKey="id" cols={[{key:'at',label:'TIMESTAMP'},{key:'actor',label:'ACTOR'},{key:'role',label:'ROLE'},{key:'action',label:'ACTION'},{key:'target',label:'TARGET'},{key:'status',label:'RESULT',render:v=><Status ok={v==='success'}>{v}</Status>}]} /></Panel>
}

function App(){
  const[section,setSection]=useState('users'),[me,setMe]=useState(null),[toast,setToast]=useState(null),[clock,setClock]=useState(new Date()),[shell,setShell]=useState({summary:null,controllers:[],replication:[],ous:[],audit:[],health:null})
  function notify(text,kind='ok'){setToast({text,kind});setTimeout(()=>setToast(null),3200)}
  async function refreshShell(){
    const results=await Promise.allSettled([api('/api/domain/summary'),api('/api/domain/controllers'),api('/api/domain/replication'),api('/api/ad/ous'),api('/api/audit?limit=12'),api('/api/health')])
    const val=i=>results[i].status==='fulfilled'?results[i].value:null
    setShell({summary:val(0),controllers:val(1)||[],replication:val(2)||[],ous:val(3)||[],audit:val(4)||[],health:val(5)})
  }
  useEffect(()=>{api('/api/auth/me').then(setMe).catch(()=>{});refreshShell();const tick=setInterval(()=>setClock(new Date()),1000);const poll=setInterval(refreshShell,30000);return()=>{clearInterval(tick);clearInterval(poll)}},[])
  const Page=useMemo(()=>({overview:Overview,domain:Domain,users:UsersPage,groups:GroupsPage,computers:ComputersPage,ous:OUsPage,recycle:RecyclePage,dns:DNSPage,dhcp:DHCPPage,gpo:GPOPage,audit:AuditPage,settings:SettingsPage})[section]||Overview,[section])
  const domain=(shell.summary?.domain||'DIRECTORY.LOCAL').toUpperCase(),dc=shell.controllers?.[0]?.name||'—'
  return <div className="admin-desktop">
    <header className="app-titlebar">
      <div className="app-ident"><span className="app-icon">▣</span><b>RSAT FULL :: ACTIVE DIRECTORY ADMINISTRATION CENTER</b><small>v1.2.3</small></div>
      <div className="connection-strip"><span className="connected">[ Connected ]</span><span>Domain: <b className="green-text">{domain}</b></span><span>DC: <u>{dc}</u></span><span>{clock.toLocaleDateString()} &nbsp; {clock.toLocaleTimeString()}</span><span>▣ &nbsp; {me?.username||'admin'}⌄</span></div>
    </header>
    <nav className="module-tabs">{nav.map(([id,num,label,Icon])=><button key={id} className={section===id?'active':''} onClick={()=>setSection(id)}><span>[{num}]</span><Icon size={13}/>{label}</button>)}</nav>
    <div className="desktop-main">
      <DirectoryTree section={section} setSection={setSection} shell={shell}/>
      <div className="page-host"><Page notify={notify}/></div>
    </div>
    <BottomDock shell={shell} section={section}/>
    <Toast toast={toast}/>
  </div>
}

createRoot(document.getElementById('root')).render(localStorage.getItem(TOKEN)?<App/>:<Login/>)
