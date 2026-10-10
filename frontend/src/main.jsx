import React,{useEffect,useMemo,useState,useRef} from 'react'
import {createRoot} from 'react-dom/client'
import {
  Activity,Archive,Box,ChevronDown,ChevronRight,Command,Computer,Database,Download,FileClock,Filter,Folder,FolderTree,
  Globe2,Group,HardDrive,KeyRound,Link2,LockKeyhole,LogOut,MoreHorizontal,Network,Plus,RefreshCw,
  Search,Server,ShieldCheck,SlidersHorizontal,Terminal,Trash2,UnlockKeyhole,Upload,UserRoundCog,Users,Wifi
} from 'lucide-react'
import {Terminal as XTerminal} from '@xterm/xterm'
import {FitAddon} from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import './styles.css'
import {formatApiError} from './api-errors.mjs'

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
  ['ssh','H','SSH Switches',Terminal],
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
    try{message=formatApiError(await res.json())}catch{message='Request failed (HTTP '+res.status+')'}
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
  return <label><span>{field.label}</span><input type={field.type||'text'} value={value??''} placeholder={field.placeholder||''} minLength={field.minLength} maxLength={field.maxLength} required={field.required||false} onChange={e=>onChange(e.target.value)} /></label>
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
  const[tablePage,setTablePage]=useState(1)
  const pageSize=100,pageCount=Math.max(1,Math.ceil(rows.length/pageSize)),currentPage=Math.min(tablePage,pageCount)
  useEffect(()=>{setTablePage(1)},[rows])
  const shown=rows.slice((currentPage-1)*pageSize,currentPage*pageSize)
  return <div className="table-shell"><table><thead><tr>{cols.map(c=><th key={c.key}>{c.label}</th>)}</tr></thead><tbody>
    {shown.map((r,i)=>{const key=r[rowKey]??r.samAccountName??r.name??i;return <tr key={key} className={selectedKey===key?'selected':''} onClick={()=>onRow&&onRow(r)}>{cols.map(c=><td key={c.key}>{c.render?c.render(r[c.key],r):String(r[c.key]??'—')}</td>)}</tr>})}
  </tbody></table>{!rows.length&&<div className="empty">{empty}</div>}
  {rows.length>pageSize&&<div className="pagination-bar"><span>{(currentPage-1)*pageSize+1}–{Math.min(currentPage*pageSize,rows.length)} / {rows.length} records</span><div className="pages"><button disabled={currentPage===1} onClick={()=>setTablePage(currentPage-1)}>PREVIOUS</button><span>PAGE {currentPage} / {pageCount}</span><button disabled={currentPage===pageCount} onClick={()=>setTablePage(currentPage+1)}>NEXT</button></div></div>}
  </div>
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
  const domain=(shell.summary?.domain||shell.settings?.native?.domain||'DIRECTORY.LOCAL').toUpperCase()
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
  const healthy=repl.length>0&&repl.every(x=>Number(x.failures||0)===0)
  return <section className="bottom-window">
    <div className="window-title"><span>DOMAIN STATUS</span><span>⌃</span></div>
    <div className="status-list">
      <div><i/><span>Domain:</span><b>{s.domain||'—'}</b></div>
      <div><i/><span>Domain Functional Level:</span><b>{s.domainMode||'—'}</b></div>
      <div><i/><span>Forest Functional Level:</span><b>{s.forestMode||'—'}</b></div>
      <div><i/><span>Domain Controllers:</span><b>{shell.summary?dcs.length:'—'}</b></div>
      <div><i/><span>Global Catalog:</span><b>{shell.summary?dcs.filter(x=>x.globalCatalog).length:'—'}</b></div>
      <div><i/><span>FSMO Roles:</span><b className="green-text">{s.pdc?'Owner known':'Unknown'}</b></div>
      <div><i className={healthy?'':'err'}/><span>Replication:</span><b className={healthy?'green-text':'red-text'}>{!repl.length?'Unavailable':healthy?'Healthy':'Attention'}</b></div>
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
    `[${now}] Directory API ..................... ${shell.summary?'OK':'UNAVAILABLE'}`,
    `[${now}] Audit subsystem ................... ${shell.audit?'OK':'N/A'}`,
    `[${now}] Domain: ${domain}`,
    `[${now}] DC: ${dc}`,
    `[${now}] Mode: ${demo?'DEMO':shell.health?.connection_mode==='native'?'DIRECT MAC / LDAPS':'WINDOWS WORKER'}`,
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

function Overview({notify,native=false}){
  const[data,setData]=useState(null),[loading,setLoading]=useState(true)
  async function load(){setLoading(true);try{
    const paths=['/api/domain/summary',native?'/api/ad/users?page_size=15':'/api/ad/users','/api/ad/computers','/api/dns/zones','/api/dhcp/scopes','/api/domain/replication']
    const results=await Promise.allSettled(paths.map(apiPath=>api(apiPath)))
    const value=(i,fallback)=>results[i].status==='fulfilled'?results[i].value:fallback
    setData({d:value(0,{}),u:value(1,[])?.items||value(1,[]),userTotalsAvailable:!native,c:value(2,[]),z:value(3,[]),s:value(4,[]),r:value(5,[]),online:results[0].status==='fulfilled',unavailable:results.map((r,i)=>r.status==='rejected'?paths[i]:null).filter(Boolean)})
    if(results[0].status==='rejected')notify(results[0].reason.message,'bad')
  }catch(e){notify(e.message,'bad')}finally{setLoading(false)}}
  useEffect(()=>{load()},[])
  if(loading)return <Panel title="SYSTEM SCAN" code="WAIT"><div className="loading">READING DIRECTORY SERVICES...</div></Panel>
  if(!data)return <div className="error-box">Directory unavailable. Open Settings to configure the connection.</div>
  const locked=data.u.filter(x=>x.lockedOut).length,disabled=data.u.filter(x=>!x.enabled).length,repFail=data.r.reduce((a,x)=>a+Number(x.failures||0),0)
  return <div className="stack">
    <div className="hero-console"><div><span className="eyebrow">CONTROL PLANE / READY</span><h2>{data.d.domain}</h2><p>{data.d.forest} · {data.d.domainMode} · {data.d.forestMode}</p></div><div className="big-status">{data.online?'ONLINE':'OFFLINE'}<span>●</span></div></div>
    {native&&<div className="identity-model-note"><span>Users are browsed and searched directly in AD by page. Domain-wide user totals require a full scan and are not inferred from the current page.</span></div>}
    <div className="metrics">
      {[['DIRECTORY USERS',data.userTotalsAvailable?data.u.length:'—','USR'],['LOCKED ACCOUNTS',data.userTotalsAvailable?locked:'—','LCK'],['DISABLED USERS',data.userTotalsAvailable?disabled:'—','DSB'],['COMPUTERS',data.c.length,'CMP'],['DNS ZONES',data.unavailable.includes('/api/dns/zones')?'N/A':data.z.length,'DNS'],['DHCP SCOPES',data.unavailable.includes('/api/dhcp/scopes')?'N/A':data.s.length,'DHC'],['REPL. FAILURES',data.unavailable.includes('/api/domain/replication')?'N/A':repFail,'REP'],['RECYCLE BIN',data.d.recycleBin==null?'UNKNOWN':data.d.recycleBin?'ON':'OFF','RCY']].map(x=><div className="metric" key={x[0]}><span>{x[2]}</span><strong>{x[1]??'—'}</strong><small>{x[0]}</small></div>)}
    </div>
    <div className="grid-2">
      <Panel title="FSMO ROLE OWNERS" code="FSMO"><KV items={[['PDC EMULATOR',data.d.pdc],['RID MASTER',data.d.rid],['INFRASTRUCTURE',data.d.infrastructure],['SCHEMA MASTER',data.d.schema],['NAMING MASTER',data.d.naming]]}/></Panel>
      <Panel title="REPLICATION STATUS" code="REPL" actions={<Button icon={RefreshCw} onClick={load}>REFRESH</Button>}><Table empty="Replication data unavailable" rows={data.r.slice(0,8)} rowKey="server" cols={[{key:'server',label:'SERVER'},{key:'partner',label:'PARTNER'},{key:'failures',label:'FAIL'},{key:'status',label:'STATE',render:v=><Status ok={v==='Healthy'}>{v}</Status>}]} /></Panel>
    </div>
  </div>
}

function Domain({notify}){
  const[state,setState]=useState({summary:null,controllers:[],replication:[],trusts:[],sites:[],subnets:[],policy:null,fgpp:[]}),[loading,setLoading]=useState(true)
  async function load(){setLoading(true);try{
    const keys=['summary','controllers','replication','trusts','sites','subnets','policy','fgpp']
    const results=await Promise.allSettled(['/summary','/controllers','/replication','/trusts','/sites','/subnets','/password-policy','/password-policies'].map(x=>api('/api/domain'+x)))
    setState(Object.fromEntries(keys.map((key,i)=>[key,results[i].status==='fulfilled'?results[i].value:(i===0||i===6?null:[])])))
    const failed=results.filter((r,i)=>r.status==='rejected'&&i!==2)
    if(failed.length)notify(failed[0].reason.message,'bad')
  }catch(e){notify(e.message,'bad')}finally{setLoading(false)}}
  useEffect(()=>{load()},[])
  if(loading)return <div className="loading">QUERYING DOMAIN CONTROLLERS...</div>
  const s=state.summary||{},p=state.policy||{}
  return <div className="stack">
    <Panel title="DOMAIN / FOREST IDENTITY" code="ROOT" actions={<Button icon={RefreshCw} onClick={load}>REFRESH</Button>}><KV items={[['DOMAIN',s.domain],['FOREST',s.forest],['DOMAIN MODE',s.domainMode],['FOREST MODE',s.forestMode],['RECYCLE BIN',s.recycleBin==null?'UNKNOWN':s.recycleBin?'ENABLED':'DISABLED']]}/></Panel>
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

function UsersPage({notify,native=false}){
  const[rows,setRows]=useState([]),[q,setQ]=useState(''),[selected,setSelected]=useState(null),[detail,setDetail]=useState(null),[groups,setGroups]=useState([]),[modal,setModal]=useState(null),[tab,setTab]=useState('General'),[page,setPage]=useState(1)
  const[loading,setLoading]=useState(true),[loadError,setLoadError]=useState(''),[paged,setPaged]=useState(false),[nextCursor,setNextCursor]=useState(null),[loadedQuery,setLoadedQuery]=useState(''),[pageCache,setPageCache]=useState({})
  const perPage=15
  async function load(targetPage=1,cursor=null,query=q){
    if(typeof targetPage!=='number')targetPage=1
    setLoading(true);setLoadError('')
    try{
      const search=new URLSearchParams({q:query})
      if(native){search.set('page_size',String(perPage));if(cursor)search.set('cursor',cursor)}
      const result=await api('/api/ad/users?'+search)
      const isPaged=Boolean(result.items),items=isPaged?result.items:result
      setRows(items);setPaged(isPaged);setPage(targetPage);setLoadedQuery(query);setNextCursor(result.next_cursor||null)
      setPageCache(x=>targetPage===1?{1:result}:{...x,[targetPage]:result})
      if(items[0])open(items[0]);else{setSelected(null);setDetail(null);setGroups([])}
    }catch(e){setLoadError(e.message);notify(e.message,'bad')}finally{setLoading(false)}
  }
  function goTo(targetPage){
    const cached=pageCache[targetPage]
    if(cached?.items){setRows(cached.items);setNextCursor(cached.next_cursor||null);setPage(targetPage);if(cached.items[0])open(cached.items[0])}
    else load(targetPage,nextCursor,loadedQuery)
  }
  async function open(r){setSelected(r);try{const[d,g]=await Promise.all([api('/api/ad/users/'+enc(r.samAccountName)),api('/api/ad/users/'+enc(r.samAccountName)+'/groups')]);setDetail(d);setGroups(g)}catch(e){notify(e.message,'bad')}}
  async function act(path,method='POST',body,keepModal=false){try{await api(path,{method,body:body?JSON.stringify(body):undefined});notify('COMMAND COMPLETED','ok');await load();if(selected)await open(selected)}catch(e){if(keepModal)throw e;notify(e.message,'bad')}}
  useEffect(()=>{load()},[native])
  const createFields=[['sam_account_name','SAM ACCOUNT'],['given_name','GIVEN NAME'],['surname','SURNAME'],['display_name','DISPLAY NAME'],['email','EMAIL'],['department','DEPARTMENT'],['title','TITLE'],['company','COMPANY'],['manager','MANAGER (SAM/DN)'],['ou','TARGET OU DN'],['password','INITIAL PASSWORD','password']]
  const pageCount=Math.max(1,Math.ceil(rows.length/perPage)), visible=paged?rows:rows.slice((page-1)*perPage,page*perPage)
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
        <div className="main-search"><Search size={14}/><input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&load()} placeholder={native?'Search users... (username, name or email prefix)':'Search users... (name, username, email, department)'}/><button onClick={load}><Search size={14}/></button></div>
        <button className="square-tool" title="Filter"><Filter size={14}/></button>
        <button className="toolbar-btn" disabled={native} title={native?'User creation is unavailable in direct mode':'Create user'} onClick={()=>setModal('create')}><Plus size={14}/> New User</button>
        <button className="toolbar-btn" onClick={()=>notify('Bulk import will require a CSV mapping profile','bad')}><Upload size={13}/> Import <ChevronDown size={11}/></button>
        <button className="toolbar-btn" onClick={exportCsv}><Download size={13}/> Export <ChevronDown size={11}/></button>
        <button className="square-tool"><MoreHorizontal size={15}/></button>
      </div>
      {loadError&&<div className="error-box" role="alert">{loadError}</div>}
      {loading&&<div className="directory-loading">READING USER PAGE FROM ACTIVE DIRECTORY...</div>}
      <div className="users-table-wrap">
        <table className="users-table"><thead><tr><th>#</th><th>Display Name</th><th>Username</th><th>Department</th><th>Title</th><th>Status</th><th>Last Logon ↓</th></tr></thead><tbody>
          {visible.map((r,i)=><tr key={r.samAccountName} className={selected?.samAccountName===r.samAccountName?'selected':''} onClick={()=>open(r)}>
            <td>{(page-1)*perPage+i+1}</td><td>{r.displayName}</td><td>{r.samAccountName}</td><td>{r.department||'—'}</td><td>{r.title||'—'}</td>
            <td><Status ok={r.enabled}>{r.enabled?'Enabled':'Disabled'}</Status>{r.lockedOut&&<span className="locked-flag">Locked</span>}</td><td>{r.lastLogon?new Date(r.lastLogon).toLocaleString():'—'}</td>
          </tr>)}
        </tbody></table>
        {!loading&&!loadError&&!rows.length&&<div className="empty">NO MATCHING USERS</div>}
      </div>
      <div className="pagination-bar">
        <span>{paged?`Showing ${rows.length?(page-1)*perPage+1:0} to ${(page-1)*perPage+rows.length} · ${nextCursor?'More users available':'End of results'}`:`Showing ${rows.length?(page-1)*perPage+1:0} to ${Math.min(page*perPage,rows.length)} of ${rows.length} users`}</span>
        {paged?<div className="pages"><button disabled={page===1||loading} onClick={()=>goTo(page-1)}>PREVIOUS</button><span>PAGE {page}</span><button disabled={!nextCursor||loading} onClick={()=>goTo(page+1)}>NEXT</button></div>:<div className="pages"><button disabled={page===1} onClick={()=>setPage(Math.max(1,page-1))}>‹</button>{Array.from({length:Math.min(5,pageCount)},(_,i)=>i+1).map(n=><button key={n} className={page===n?'active':''} onClick={()=>setPage(n)}>{n}</button>)}{pageCount>5&&<><span>...</span><button onClick={()=>setPage(pageCount)}>{pageCount}</button></>}<button disabled={page===pageCount} onClick={()=>setPage(Math.min(pageCount,page+1))}>›</button></div>}
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
    {modal==='password'&&detail&&<Modal title={'RESET PASSWORD / '+detail.samAccountName} fields={[{name:'new_password',label:'NEW PASSWORD (8–256 CHARACTERS)',type:'password',minLength:8,maxLength:256,required:true},{name:'must_change',label:'CHANGE AT NEXT LOGON',type:'checkbox',default:true}]} onClose={()=>setModal(null)} subtitle='Domain complexity and password history rules also apply.' onSubmit={v=>act('/api/ad/users/'+enc(detail.samAccountName)+'/reset-password','POST',v,true)}/>}
    {modal==='move'&&detail&&<Modal title={'MOVE USER / '+detail.samAccountName} fields={[{name:'target_ou',label:'TARGET OU DISTINGUISHED NAME'}]} onClose={()=>setModal(null)} onSubmit={v=>act('/api/ad/users/'+enc(detail.samAccountName)+'/move','POST',v)}/>}
    {modal==='delete'&&detail&&<Modal title={'DELETE '+detail.samAccountName+' ?'} subtitle="This removes the Active Directory object. Use the Recycle Bin if recovery is required." fields={[]} danger submitLabel="DELETE OBJECT" onClose={()=>setModal(null)} onSubmit={()=>act('/api/ad/users/'+enc(detail.samAccountName),'DELETE')}/>}
  </div>
}

function GroupsPage({notify}){
  const[rows,setRows]=useState([]),[sel,setSel]=useState(null),[members,setMembers]=useState([]),[modal,setModal]=useState(null)
  const[loading,setLoading]=useState(true),[loadError,setLoadError]=useState('')
  async function load(){setLoading(true);setLoadError('');try{setRows(await api('/api/ad/groups'))}catch(e){setLoadError(e.message);notify(e.message,'bad')}finally{setLoading(false)}}
  async function open(r){setSel(r);try{setMembers(await api('/api/ad/groups/'+enc(r.name)+'/members'))}catch(e){notify(e.message,'bad')}}
  async function command(path,method='POST',body){try{await api(path,{method,body:body?JSON.stringify(body):undefined});notify('GROUP COMMAND COMPLETED','ok');load();if(sel)open(sel)}catch(e){notify(e.message,'bad')}}
  useEffect(()=>{load()},[])
  return <div className="stack">{loading&&<div className="directory-loading">READING ACTIVE DIRECTORY...</div>}{loadError&&<div className="error-box" role="alert">{loadError}</div>}<div className="split"><Panel title="SECURITY / DISTRIBUTION GROUPS" code="GRP" actions={<><Button icon={Plus} kind="primary" onClick={()=>setModal('create')}>NEW GROUP</Button><Button icon={RefreshCw} onClick={load}>REFRESH</Button></>}>
    <Table rows={rows} rowKey="name" selectedKey={sel?.name} onRow={open} cols={[{key:'name',label:'GROUP'},{key:'category',label:'CATEGORY'},{key:'scope',label:'SCOPE'},{key:'members',label:'MEMBERS'}]}/>
  </Panel><Panel title="MEMBERSHIP INSPECTOR" code="MBR" className="inspector">{!sel?<div className="empty">SELECT A GROUP</div>:<>
    <div className="object-head"><div className="avatar"><Group/></div><div><h3>{sel.name}</h3><p>{sel.description||'NO DESCRIPTION'}</p></div></div>
    <div className="panel-actions left"><Button icon={Plus} onClick={()=>setModal('add')}>ADD MEMBER</Button><Button icon={Trash2} kind="danger" onClick={()=>setModal('delete')}>DELETE GROUP</Button></div>
    <div className="subsection">{members.map(m=><div className="mini-row" key={m.dn||m.samAccountName}><Users size={13}/><span>{m.name}</span><small>{m.objectClass}</small><button className="tiny-danger" onClick={()=>command('/api/ad/groups/'+enc(sel.name)+'/members/'+enc(m.samAccountName||m.dn),'DELETE')}>REMOVE</button></div>)}</div>
  </>}</Panel>
  {modal==='create'&&<Modal title="CREATE GROUP" fields={[{name:'name',label:'GROUP NAME'},{name:'scope',label:'SCOPE',type:'select',options:['Global','DomainLocal','Universal'],default:'Global'},{name:'category',label:'CATEGORY',type:'select',options:['Security','Distribution'],default:'Security'},{name:'path',label:'TARGET OU DN'},{name:'description',label:'DESCRIPTION'}]} onClose={()=>setModal(null)} onSubmit={async v=>{await api('/api/ad/groups',{method:'POST',body:JSON.stringify(v)});notify('GROUP CREATED','ok');load()}}/>}
  {modal==='add'&&sel&&<Modal title={'ADD MEMBER / '+sel.name} fields={[{name:'member',label:'USER OR OBJECT IDENTITY'}]} onClose={()=>setModal(null)} onSubmit={v=>command('/api/ad/groups/'+enc(sel.name)+'/members','POST',v)}/>}
  {modal==='delete'&&sel&&<Modal title={'DELETE GROUP / '+sel.name} fields={[]} danger submitLabel="DELETE GROUP" onClose={()=>setModal(null)} onSubmit={()=>command('/api/ad/groups/'+enc(sel.name),'DELETE')}/>}
  </div></div>
}

function ComputersPage({notify,native=false}){
  const[rows,setRows]=useState([]),[q,setQ]=useState(''),[sel,setSel]=useState(null),[modal,setModal]=useState(null)
  const[loading,setLoading]=useState(true),[loadError,setLoadError]=useState('')
  async function load(){setLoading(true);setLoadError('');try{setRows(await api('/api/ad/computers'+(q?'?q='+enc(q):'')))}catch(e){setLoadError(e.message);notify(e.message,'bad')}finally{setLoading(false)}}
  async function command(path,method='POST',body){try{await api(path,{method,body:body?JSON.stringify(body):undefined});notify('COMPUTER COMMAND COMPLETED','ok');load()}catch(e){notify(e.message,'bad')}}
  useEffect(()=>{load()},[])
  return <div className="stack">{loading&&<div className="directory-loading">READING ACTIVE DIRECTORY...</div>}{loadError&&<div className="error-box" role="alert">{loadError}</div>}<div className="split"><Panel title="DOMAIN COMPUTERS" code="CMP" actions={<><div className="searchbox"><Search size={14}/><input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&load()} placeholder="hostname"/></div><Button icon={RefreshCw} onClick={load}>REFRESH</Button></>}>
    <Table rows={rows} rowKey="name" selectedKey={sel?.name} onRow={setSel} cols={[{key:'name',label:'HOSTNAME'},{key:'os',label:'OPERATING SYSTEM'},{key:'ipv4',label:'IPV4'},{key:'enabled',label:'STATE',render:v=><Status ok={v}>{v?'ENABLED':'DISABLED'}</Status>},{key:'lastLogon',label:'LAST LOGON'}]}/>
  </Panel><Panel title="COMPUTER OBJECT" code="OBJ" className="inspector">{!sel?<div className="empty">SELECT A COMPUTER</div>:<>
    <div className="object-head"><div className="avatar"><Computer/></div><div><h3>{sel.name}</h3><p>{sel.os}</p></div></div><KV items={[['IPV4',sel.ipv4],['LAST LOGON',sel.lastLogon],['OU',sel.ou],['STATE',sel.enabled?'ENABLED':'DISABLED']]}/>
    <div className="action-grid"><Button onClick={()=>command('/api/ad/computers/'+enc(sel.name)+'/'+(sel.enabled?'disable':'enable'))}>{sel.enabled?'DISABLE':'ENABLE'}</Button><Button icon={RefreshCw} onClick={()=>setModal('reset')} disabled={native}>RESET ACCOUNT</Button><Button icon={FolderTree} onClick={()=>setModal('move')}>MOVE OU</Button><Button icon={Trash2} kind="danger" onClick={()=>setModal('delete')}>DELETE</Button></div>
  </>}</Panel>
  {modal==='move'&&sel&&<Modal title={'MOVE '+sel.name} fields={[{name:'target_ou',label:'TARGET OU DN'}]} onClose={()=>setModal(null)} onSubmit={v=>command('/api/ad/computers/'+enc(sel.name)+'/move','POST',v)}/>}
  {modal==='reset'&&sel&&<Modal title={'RESET COMPUTER ACCOUNT / '+sel.name} subtitle="The workstation may need its secure channel repaired or to be rejoined." fields={[]} submitLabel="RESET ACCOUNT" onClose={()=>setModal(null)} onSubmit={()=>command('/api/ad/computers/'+enc(sel.name)+'/reset')}/>}
  {modal==='delete'&&sel&&<Modal title={'DELETE COMPUTER / '+sel.name} fields={[]} danger submitLabel="DELETE OBJECT" onClose={()=>setModal(null)} onSubmit={()=>command('/api/ad/computers/'+enc(sel.name),'DELETE')}/>}
  </div></div>
}

function OUsPage({notify,native=false}){
  const[rows,setRows]=useState([]),[sel,setSel]=useState(null),[modal,setModal]=useState(null)
  const[loading,setLoading]=useState(true),[loadError,setLoadError]=useState('')
  async function load(){setLoading(true);setLoadError('');try{setRows(await api('/api/ad/ous'))}catch(e){setLoadError(e.message);notify(e.message,'bad')}finally{setLoading(false)}}
  useEffect(()=>{load()},[])
  async function create(v){try{await api('/api/ad/ous',{method:'POST',body:JSON.stringify(v)});notify('OU CREATED','ok');load()}catch(e){throw e}}
  async function del(v){try{await api('/api/ad/ous/delete',{method:'POST',body:JSON.stringify({dn:sel.dn,recursive:v.recursive})});notify('OU DELETED','ok');setSel(null);load()}catch(e){throw e}}
  return <div className="stack">{loading&&<div className="directory-loading">READING ACTIVE DIRECTORY...</div>}{loadError&&<div className="error-box" role="alert">{loadError}</div>}<div className="split"><Panel title="ORGANIZATIONAL UNIT TREE" code="OU" actions={<><Button icon={Plus} kind="primary" onClick={()=>setModal('create')} disabled={native}>NEW OU</Button><Button icon={RefreshCw} onClick={load}>REFRESH</Button></>}><Table rows={rows} rowKey="dn" selectedKey={sel?.dn} onRow={setSel} cols={[{key:'name',label:'OU'},{key:'dn',label:'DISTINGUISHED NAME'},{key:'protected',label:'PROTECTED',render:v=><Status ok={v}>{v==null?'UNKNOWN':v?'YES':'NO'}</Status>}]} /></Panel>
  <Panel title="OU INSPECTOR" code="OBJ" className="inspector">{sel?<><KV items={[['NAME',sel.name],['DN',sel.dn],['ACCIDENTAL DELETE PROTECTION',sel.protected==null?'NOT READ BY LDAP CONNECTOR':sel.protected?'ENABLED':'DISABLED']]}/><Button icon={Trash2} kind="danger" onClick={()=>setModal('delete')}>DELETE OU</Button></>:<div className="empty">SELECT AN OU</div>}</Panel>
  {modal==='create'&&<Modal title="CREATE ORGANIZATIONAL UNIT" fields={[{name:'name',label:'OU NAME'},{name:'path',label:'PARENT DN'},{name:'protected',label:'PROTECT FROM ACCIDENTAL DELETION',type:'checkbox',default:true}]} onClose={()=>setModal(null)} onSubmit={create}/>}
  {modal==='delete'&&sel&&<Modal title={'DELETE OU / '+sel.name} subtitle="Recursive deletion will remove all child objects. Keep it off unless explicitly required." fields={[{name:'recursive',label:'RECURSIVE DELETE',type:'checkbox',default:false}]} danger submitLabel="DELETE OU" onClose={()=>setModal(null)} onSubmit={del}/>}
  </div></div>
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

function DNSPage({notify,dnsReadOnly=false,dnsZoneReadOnly=false,defaultZone=''}){
  const readGeneration=useRef(0)
  const[query,setQuery]=useState('')
  const[loadError,setLoadError]=useState(''),[loading,setLoading]=useState(false)
  const[zones,setZones]=useState([]),[zone,setZone]=useState(''),[records,setRecords]=useState([]),[sel,setSel]=useState(null),[modal,setModal]=useState(null)
  async function loadZones(){setLoading(true);try{const z=await api('/api/dns/zones');setZones(z);setLoadError('');if(!zone&&z[0])setZone(z.find(x=>x.name.toLowerCase()===defaultZone.toLowerCase())?.name||z[0].name);if(zone&&!z.some(x=>x.name===zone))setZone(z[0]?.name||'')}catch(e){setLoadError(e.message);setZones([])}finally{setLoading(false)}}
  async function loadRecords(){const generation=++readGeneration.current;setLoading(true);try{const rows=await api('/api/dns/records'+(zone?'?zone='+enc(zone):''));if(generation===readGeneration.current){setRecords(rows.map((r,i)=>({...r,id:i})));setLoadError('')}}catch(e){if(generation===readGeneration.current){setLoadError(e.message);setRecords([])}}finally{if(generation===readGeneration.current)setLoading(false)}}
  useEffect(()=>{loadZones().catch(e=>notify(e.message,'bad'))},[])
  useEffect(()=>{if(zone)loadRecords()},[zone])
  async function create(v){await api('/api/dns/records',{method:'POST',body:JSON.stringify(v)});notify('DNS RECORD CREATED','ok');loadRecords()}
  async function edit(v){await api('/api/dns/records/update',{method:'POST',body:JSON.stringify({...sel,value:v.value,ttl:Number(v.ttl),old_value:sel.value,old_ttl:sel.ttl})});notify('DNS RECORD UPDATED','ok');setSel(null);await loadRecords()}
  async function del(){await api('/api/dns/records/delete',{method:'POST',body:JSON.stringify(sel)});notify('DNS RECORD REMOVED','ok');setSel(null);loadRecords()}
  async function createZone(v){await api('/api/dns/zones',{method:'POST',body:JSON.stringify(v)});notify('DNS ZONE CREATED','ok');await loadZones()}
  async function deleteZone(){await api('/api/dns/zones/delete',{method:'POST',body:JSON.stringify({name:zone})});notify('DNS ZONE DELETED','ok');setSel(null);setZone('');await loadZones()}
  const z=zones.find(x=>x.name===zone)
  return <div className="stack dns-page">{loading&&<div className="directory-loading">READING DNS...</div>}{loadError&&<div className="error-box">{loadError}</div>}<div className="split"><Panel title={'DNS RECORDS / '+zone+' / '+records.length} code="DNS" actions={<><div className="searchbox"><Search size={14}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search DNS name, value or type"/></div><select className="toolbar-select" value={zone} onChange={e=>{readGeneration.current++;setSel(null);setRecords([]);setQuery('');setZone(e.target.value)}}>{zones.map(z=><option key={z.name}>{z.name}</option>)}</select><Button icon={Plus} disabled={dnsReadOnly||dnsZoneReadOnly} onClick={()=>setModal('zone')}>NEW ZONE</Button><Button icon={Plus} kind="primary" disabled={!zone||dnsReadOnly} onClick={()=>setModal('create')}>NEW RECORD</Button><Button disabled={!sel||dnsReadOnly||!['A','AAAA','CNAME','PTR','NS','MX','SRV','TXT'].includes(sel?.type)} onClick={()=>setModal('edit')}>EDIT RECORD</Button><Button icon={Trash2} kind="danger" disabled={!sel||dnsReadOnly||!['A','AAAA','CNAME','PTR','NS','MX','SRV','TXT'].includes(sel?.type)} onClick={()=>setModal('delete')}>DELETE RECORD</Button><Button icon={RefreshCw} onClick={async()=>{await loadZones();if(zone)await loadRecords()}}>REFRESH</Button></>}><Table rows={records.filter(r=>!query||[r.name,r.value,r.type].some(v=>String(v).toLowerCase().includes(query.toLowerCase())))} rowKey="id" selectedKey={sel?.id} onRow={setSel} cols={[{key:'name',label:'NAME'},{key:'type',label:'TYPE'},{key:'value',label:'VALUE'},{key:'ttl',label:'TTL'}]}/></Panel>
  <Panel title="ZONE / RECORD INSPECTOR" code="OBJ" className="inspector"><KV items={[['ZONE',zone],['ZONE TYPE',z?.type],['AD INTEGRATED',z?z.integrated?'YES':'NO':'—'],['REVERSE LOOKUP',z?.reverse?'YES':'NO']]}/>{zone&&<div className="action-grid"><Button icon={Trash2} kind="danger" disabled={dnsReadOnly||dnsZoneReadOnly} onClick={()=>setModal('zoneDelete')}>DELETE ZONE</Button></div>}{!sel&&<div className="empty">SELECT A RECORD TO EDIT OR DELETE</div>}{sel&&<><div className="subsection"><KV items={[['RECORD',sel.name],['TYPE',sel.type],['VALUE',sel.value],['TTL',sel.ttl]]}/></div></>}</Panel>
  {modal==='zone'&&<Modal title="CREATE AD-INTEGRATED DNS ZONE" fields={[{name:'name',label:'ZONE NAME'},{name:'replication_scope',label:'REPLICATION SCOPE',type:'select',options:['Domain','Forest','Legacy'],default:'Domain'},{name:'dynamic_update',label:'DYNAMIC UPDATE',type:'select',options:['Secure','NonsecureAndSecure','None'],default:'Secure'}]} onClose={()=>setModal(null)} onSubmit={createZone}/>}
  {modal==='zoneDelete'&&zone&&<Modal title={'DELETE DNS ZONE / '+zone} subtitle="This removes the entire DNS zone and all records in it." fields={[]} danger submitLabel="DELETE ZONE" onClose={()=>setModal(null)} onSubmit={deleteZone}/>}
  {modal==='create'&&<Modal title={'CREATE DNS RECORD / '+zone} subtitle={'MX: priority target · SRV: priority weight port target · TXT: quote each text segment, e.g. \"text with spaces\"'} initial={{zone,type:'A',ttl:3600}} fields={[{name:'zone',label:'ZONE'},{name:'name',label:'NAME'},{name:'type',label:'TYPE',type:'select',options:['A','AAAA','CNAME','PTR','NS','MX','SRV','TXT'],default:'A'},{name:'value',label:'VALUE / TARGET'},{name:'ttl',label:'TTL SECONDS',type:'number',default:3600}]} onClose={()=>setModal(null)} onSubmit={create}/>}
  {modal==='edit'&&sel&&<Modal title={'EDIT DNS RECORD / '+sel.name} subtitle={sel.zone+' · '+sel.type+' · MX: priority target; SRV: priority weight port target; TXT: quote text segments'} initial={{value:sel.value,ttl:sel.ttl}} fields={[{name:'value',label:'VALUE / TARGET'},{name:'ttl',label:'TTL SECONDS',type:'number'}]} onClose={()=>setModal(null)} onSubmit={edit}/>}
  {modal==='delete'&&sel&&<Modal title={'DELETE DNS RECORD / '+sel.name} fields={[]} danger submitLabel="DELETE RECORD" onClose={()=>setModal(null)} onSubmit={del}/>}
  </div></div>
}

function DHCPPage({notify}){
  const readGeneration=useRef(0)
  const[loadError,setLoadError]=useState(''),[loading,setLoading]=useState(false)
  const[scopes,setScopes]=useState([]),[scope,setScope]=useState(''),[leases,setLeases]=useState([]),[reservations,setReservations]=useState([]),[tab,setTab]=useState('leases'),[sel,setSel]=useState(null),[modal,setModal]=useState(null)
  async function loadScopes(){setLoading(true);try{const s=await api('/api/dhcp/scopes');setScopes(s);setLoadError('');if(!scope&&s[0])setScope(s[0].scopeId);if(scope&&!s.some(x=>x.scopeId===scope))setScope(s[0]?.scopeId||'')}catch(e){setLoadError(e.message);setScopes([])}finally{setLoading(false)}}
  async function loadData(){const generation=++readGeneration.current;if(!scope)return;try{const[l,r]=await Promise.all([api('/api/dhcp/leases?scope_id='+enc(scope)),api('/api/dhcp/reservations?scope_id='+enc(scope))]);if(generation===readGeneration.current){setLeases(l);setReservations(r);setLoadError('')}}catch(e){if(generation===readGeneration.current){setLeases([]);setReservations([]);setLoadError(e.message)}}}
  useEffect(()=>{loadScopes().catch(e=>notify(e.message,'bad'))},[])
  useEffect(()=>{setSel(null);setLeases([]);setReservations([]);loadData()},[scope])
  async function create(v){await api('/api/dhcp/reservations',{method:'POST',body:JSON.stringify(v)});notify('RESERVATION CREATED','ok');loadData()}
  async function del(){await api('/api/dhcp/reservations/delete',{method:'POST',body:JSON.stringify({scope_id:sel.scopeId,ip_address:sel.ipAddress})});notify('RESERVATION REMOVED','ok');setSel(null);loadData()}
  async function createScope(v){await api('/api/dhcp/scopes',{method:'POST',body:JSON.stringify(v)});notify('DHCP SCOPE CREATED','ok');await loadScopes()}
  async function scopeState(state){await api('/api/dhcp/scopes/state',{method:'POST',body:JSON.stringify({scope_id:scope,state})});notify('SCOPE STATE UPDATED','ok');await loadScopes()}
  async function deleteScope(){await api('/api/dhcp/scopes/delete',{method:'POST',body:JSON.stringify({scope_id:scope})});notify('DHCP SCOPE DELETED','ok');setScope('');await loadScopes()}
  const s=scopes.find(x=>x.scopeId===scope)
  return <div className="stack">{loading&&<div className="directory-loading">READING DHCP...</div>}{loadError&&<div className="error-box">{loadError}</div>}<Panel title="DHCP SCOPE SELECTOR" code="DHC" actions={<><select className="toolbar-select" value={scope} onChange={e=>{readGeneration.current++;setSel(null);setLeases([]);setReservations([]);setScope(e.target.value)}}>{scopes.map(x=><option key={x.scopeId} value={x.scopeId}>{x.scopeId} / {x.name}</option>)}</select><Button icon={Plus} kind="primary" onClick={()=>setModal('scopeCreate')}>NEW SCOPE</Button>{s&&<Button onClick={()=>scopeState(s.state==='Active'?'Inactive':'Active')}>{s.state==='Active'?'DEACTIVATE':'ACTIVATE'}</Button>}{s&&<Button icon={Trash2} kind="danger" onClick={()=>setModal('scopeDelete')}>DELETE SCOPE</Button>}<Button icon={RefreshCw} onClick={async()=>{await loadScopes();await loadData()}}>REFRESH</Button></>}><div className="metrics compact">{s&&[['STATE',s.state,'STA'],['RANGE',s.startRange+' — '+s.endRange,'RNG'],['IN USE',s.inUse,'USE'],['FREE',s.free,'FRE']].map(x=><div className="metric" key={x[0]}><span>{x[2]}</span><strong>{x[1]??'—'}</strong><small>{x[0]}</small></div>)}</div></Panel>
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
  const[cfg,setCfg]=useState({
    demo_mode:true,worker_url:'',worker_paired:false,worker_identity:null,
    authentication_model:'domain-integrated-worker',sites:[]
  })
  const[pairingCode,setPairingCode]=useState('')
  const[nativeForm,setNativeForm]=useState({domain:'',username:'',preferred_dc:'',password:'',ca_pem:''}),[nativeTest,setNativeTest]=useState(null),[certificate,setCertificate]=useState(null),[certificateHost,setCertificateHost]=useState('')
  const[loading,setLoading]=useState(true),[busy,setBusy]=useState(''),[tests,setTests]=useState({}),[workerTest,setWorkerTest]=useState(null)

  async function load(){
    setLoading(true)
    try{
      const r=await api('/api/settings')
      setCfg(r)
      setNativeForm(x=>({...x,...r.native,password:''}))
      setCertificateHost(x=>x||r.native?.preferred_dc||r.sites.flatMap(s=>s.dcs).find(d=>d.enabled!==false)?.host||'')
    }catch(e){notify(e.message,'bad')}
    finally{setLoading(false)}
  }
  useEffect(()=>{load()},[])

  function updateSite(si,key,value){
    setCfg(x=>({...x,sites:x.sites.map((s,i)=>i===si?{...s,[key]:value}:s)}))
  }
  function updateDc(si,di,key,value){
    setCfg(x=>({...x,sites:x.sites.map((s,i)=>i===si?{...s,dcs:s.dcs.map((d,j)=>j===di?{...d,[key]:value}:d)}:s)}))
  }
  function addSite(){setCfg(x=>({...x,sites:[...x.sites,blankSite()]}))}
  function removeSite(si){setCfg(x=>({...x,sites:x.sites.filter((_,i)=>i!==si)}))}
  function addDc(si){setCfg(x=>({...x,sites:x.sites.map((s,i)=>i===si?{...s,dcs:[...s.dcs,blankDc()]}:s)}))}
  function removeDc(si,di){setCfg(x=>({...x,sites:x.sites.map((s,i)=>i===si?{...s,dcs:s.dcs.filter((_,j)=>j!==di)}:s)}))}

  async function save(){
    setBusy('save')
    try{
      await api('/api/settings',{method:'PUT',body:JSON.stringify({
        demo_mode:cfg.demo_mode,connection_mode:cfg.connection_mode,
        worker_url:cfg.worker_url,
        sites:cfg.sites.map(s=>({
          name:s.name,code:s.code||'',description:s.description||'',
          dcs:s.dcs.map(d=>({name:d.name,host:d.host,ip:d.ip||'',enabled:d.enabled!==false,notes:d.notes||''}))
        }))
      })})
      notify('SETTINGS SAVED — ACTIVE WITHOUT RESTART','ok')
      window.dispatchEvent(new Event('directory-settings-changed'))
      await load()
    }catch(e){notify(e.message,'bad')}finally{setBusy('')}
  }

  async function pairWorker(){
    if(!cfg.worker_url){notify('WINDOWS WORKER URL IS REQUIRED','bad');return}
    if(!pairingCode){notify('ENTER THE ONE-TIME PAIRING CODE SHOWN ON THE WINDOWS WORKER','bad');return}
    setBusy('pair')
    try{
      const r=await api('/api/settings/pair-worker',{method:'POST',body:JSON.stringify({
        worker_url:cfg.worker_url,pairing_code:pairingCode
      })})
      setPairingCode('')
      setWorkerTest({ok:true,worker:{identity:r.worker_identity}})
      notify('WINDOWS WORKER PAIRED SECURELY','ok')
      await load()
    }catch(e){notify(e.message,'bad')}finally{setBusy('')}
  }

  async function unpairWorker(){
    setBusy('unpair')
    try{
      await api('/api/settings/unpair-worker',{method:'POST'})
      setWorkerTest(null)
      notify('WINDOWS WORKER UNPAIRED','ok')
      await load()
    }catch(e){notify(e.message,'bad')}finally{setBusy('')}
  }

  async function testWorker(){
    setBusy('worker')
    try{
      const r=await api('/api/settings/test-worker',{method:'POST',body:JSON.stringify({
        worker_url:cfg.worker_url,demo_mode:cfg.demo_mode
      })})
      setWorkerTest(r)
      notify('WINDOWS WORKER CONNECTION OK','ok')
    }catch(e){setWorkerTest({ok:false,error:e.message});notify(e.message,'bad')}finally{setBusy('')}
  }

  async function discover(){
    setBusy('discover')
    try{
      const rows=await api('/api/settings/discover-dcs',{method:'POST',body:JSON.stringify({
        worker_url:cfg.worker_url,demo_mode:cfg.demo_mode
      })})
      const grouped={}
      for(const dc of rows){
        const site=dc.site||'Unknown'
        if(!grouped[site]) grouped[site]=[]
        grouped[site].push({
          name:dc.name||'',host:dc.host||'',ip:dc.ip||'',enabled:dc.enabled!==false,
          notes:dc.globalCatalog?'Global Catalog':''
        })
      }
      const sites=Object.entries(grouped).map(([name,dcs])=>({
        name,code:name.toUpperCase().replace(/[^A-Z0-9]+/g,'-').slice(0,20),
        description:'Discovered from Active Directory',dcs
      }))
      setCfg(x=>({...x,sites}))
      notify('DOMAIN CONTROLLERS DISCOVERED — REVIEW AND SAVE','ok')
    }catch(e){notify(e.message,'bad')}finally{setBusy('')}
  }

  async function testDc(si,di){
    const dc=cfg.sites[si].dcs[di]
    if(!dc.host){notify('DC HOST/FQDN IS REQUIRED','bad');return}
    const key=si+'-'+di
    setTests(x=>({...x,[key]:{loading:true}}))
    try{
      const r=await api('/api/settings/test-dc',{method:'POST',body:JSON.stringify({
        host:dc.host,worker_url:cfg.worker_url,demo_mode:cfg.demo_mode
      })})
      setTests(x=>({...x,[key]:r}))
      notify((r.ok?'DC REACHABLE: ':'DC CHECK FAILED: ')+dc.host,r.ok?'ok':'bad')
    }catch(e){
      setTests(x=>({...x,[key]:{ok:false,error:e.message}}))
      notify(e.message,'bad')
    }
  }

  const totalDcs=cfg.sites.reduce((n,s)=>n+s.dcs.length,0)
  const activeDcs=cfg.sites.reduce((n,s)=>n+s.dcs.filter(d=>d.enabled!==false).length,0)
  const identity=cfg.worker_identity||workerTest?.worker?.identity||null
  const isNative=cfg.connection_mode==='native'
  const canUseWorker=isNative?Boolean(cfg.native?.password_configured):cfg.demo_mode||cfg.worker_paired

  async function saveNative(){
    setBusy('native');setNativeTest(null)
    try{
      const body={domain:nativeForm.domain,username:nativeForm.username,preferred_dc:nativeForm.preferred_dc,ca_pem:nativeForm.ca_pem}
      if(nativeForm.password)body.password=nativeForm.password
      await api('/api/settings/native',{method:'PUT',body:JSON.stringify(body)})
      setNativeForm(x=>({...x,password:''}))
      await load()
      const result=await api('/api/settings/native/test',{method:'POST'})
      setNativeTest(result);notify('DIRECT MAC CONNECTION READY','ok')
      window.dispatchEvent(new Event('directory-settings-changed'))
    }catch(e){setNativeTest({ok:false,error:e.message});notify(e.message,'bad')}finally{setBusy('')}
  }
  async function inspectCertificate(){
    setBusy('certificate');setCertificate(null)
    try{setCertificate(await api('/api/settings/native/certificate',{method:'POST',body:JSON.stringify({host:certificateHost})}))}
    catch(e){notify(e.message,'bad')}finally{setBusy('')}
  }
  async function trustCertificate(){
    setBusy('trust')
    try{
      await api('/api/settings/native/trust-certificate',{method:'POST',body:JSON.stringify({host:certificate.host,fingerprint:certificate.fingerprint})})
      await load();notify('DC CERTIFICATE APPROVED — NOW SAVE YOUR ACCOUNT','ok');setCertificate(null)
    }catch(e){notify(e.message,'bad')}finally{setBusy('')}
  }
  async function testNative(){
    setBusy('native-test')
    try{setNativeTest(await api('/api/settings/native/test',{method:'POST'}))}
    catch(e){setNativeTest({ok:false,error:e.message})}finally{setBusy('')}
  }
  async function forgetNative(){
    await api('/api/settings/native/credentials',{method:'DELETE'});setNativeTest(null);await load();window.dispatchEvent(new Event('directory-settings-changed'))
  }

  if(loading)return <div className="loading">LOADING SYSTEM CONFIGURATION...</div>

  return <div className="settings-page">
    <section className="window-frame settings-connection direct-connection">
      <div className="window-title"><span>DIRECT MAC CONNECTION / NO WINDOWS WORKER</span><span>LDAPS · PORT 636</span></div>
      <div className="identity-model-note"><ShieldCheck size={18}/><div><b>CONNECT ONCE — DIRECTORY LOADS AUTOMATICALLY</b><span>The Mac backend connects directly to enabled DCs. Password is encrypted at rest; TLS requires a trusted CA or an explicitly approved DC certificate; hostname and certificate validity are checked. Corporate network/VPN and corporate DNS must be reachable.</span></div></div>
      <div className="connection-config">
        <label><span>AD DOMAIN</span><input value={nativeForm.domain||''} onChange={e=>setNativeForm({...nativeForm,domain:e.target.value})}/></label>
        <label><span>DOMAIN USER / UPN</span><input autoComplete="username" value={nativeForm.username||''} onChange={e=>setNativeForm({...nativeForm,username:e.target.value})}/></label>
        <label><span>AD PASSWORD</span><input type="password" autoComplete="new-password" value={nativeForm.password} placeholder={cfg.native?.password_configured?'Saved securely — leave blank to keep':'Enter your domain password here'} onChange={e=>setNativeForm({...nativeForm,password:e.target.value})}/></label>
        <label><span>PREFERRED DC / OPTIONAL</span><input value={nativeForm.preferred_dc||''} placeholder="Automatic: use enabled DCs below" onChange={e=>setNativeForm({...nativeForm,preferred_dc:e.target.value})}/></label>
        <label style={{gridColumn:'1 / -1'}}><span>AD CA CERTIFICATE / PEM</span><textarea rows={4} value={nativeForm.ca_pem||''} placeholder="Paste the corporate root/intermediate CA certificate if the DC certificate uses an internal CA" onChange={e=>setNativeForm({...nativeForm,ca_pem:e.target.value})}/><small>Public CA roots are already trusted. For an internal CA, paste its PEM certificate chain. If you do not have it, approve a DC certificate below instead.</small></label>
        <div className="connection-buttons">
          <Button kind="primary" icon={KeyRound} disabled={Boolean(busy)} onClick={saveNative}>{busy==='native'?'CONNECTING...':'SAVE & CONNECT DIRECTLY'}</Button>
          <Button icon={Wifi} disabled={Boolean(busy)||!cfg.native?.password_configured} onClick={testNative}>TEST DIRECT CONNECTION</Button>
          <Button icon={Search} disabled={Boolean(busy)||!isNative||!cfg.native?.password_configured} onClick={discover}>DISCOVER ALL DCS</Button>
          {cfg.native?.password_configured&&<Button kind="danger" disabled={Boolean(busy)} onClick={()=>forgetNative().catch(e=>notify(e.message,'bad'))}>FORGET AD PASSWORD</Button>}
        </div>
      </div>
      <div className="connection-config">
        <label><span>NO CA FILE? INSPECT A DC CERTIFICATE</span><select value={certificateHost} onChange={e=>{setCertificateHost(e.target.value);setCertificate(null)}}>{cfg.sites.flatMap(s=>s.dcs).filter(d=>d.enabled!==false).map(d=><option key={d.host} value={d.host}>{d.host}</option>)}</select><small>Inspect sends no password. Verify this fingerprint against a trusted company source before approving it. Approval trusts this DC only; a CA enables automatic failover to other DCs.</small></label>
        <div className="connection-buttons"><Button disabled={Boolean(busy)||!certificateHost} onClick={inspectCertificate}>INSPECT DC CERTIFICATE</Button></div>
        {certificate&&<div style={{gridColumn:'1 / -1'}}><KV items={[["DC",certificate.host],["SHA-256",certificate.fingerprint],["ISSUER",certificate.issuer],["VALID UNTIL",certificate.valid_until],["HOSTNAME / DATE",certificate.hostname_valid&&certificate.time_valid?'MATCH / VALID':'INVALID']]}/><Button kind="primary" disabled={Boolean(busy)||!certificate.hostname_valid||!certificate.time_valid} onClick={trustCertificate}>I VERIFIED THIS CERTIFICATE — TRUST THIS DC</Button></div>}
        {Boolean(cfg.native?.trusted_dc_certificates?.length)&&<small>Approved DCs: {cfg.native.trusted_dc_certificates.join(', ')}</small>}
      </div>
      <KV items={[["ACTIVE CONNECTION",isNative?'DIRECT MAC / LDAPS':'WINDOWS WORKER'],['ACCOUNT',cfg.native?.username||'Not configured'],['PASSWORD',cfg.native?.password_configured?'Encrypted / saved':'Required'],['AUTO CONNECTION','Enabled after saving the account']]}/>
      {nativeTest&&<div className={'connection-result '+(nativeTest.ok?'ok':'bad')}><b>{nativeTest.ok?'DIRECT AD ONLINE':'DIRECT AD ERROR'}</b><span>{nativeTest.ok?`${nativeTest.username} → ${nativeTest.host} · ${nativeTest.authentication}`:nativeTest.error}</span></div>}
      <div className="identity-model-note"><div><b>DIRECT MODE CAPABILITIES</b><span>Users, groups, computers, OU inventory, sites, trusts, password policies and GPO inventory. Supports unlock, password reset, enable/disable, attribute edits, moves, deletions and group membership. User creation, OU protection, computer account reset, DNS/DHCP administration, GPO editing, replication health and recycle bin are unavailable.</span></div></div>
    </section>
    {!isNative&&<section className="window-frame settings-connection">
      <div className="window-title"><span>CONNECTION / IDENTITY MODEL</span><span>DOMAIN-INTEGRATED</span></div>

      <div className="settings-summary settings-summary-five">
        <div><span>MODE</span><b>{cfg.demo_mode?'DEMO':'PRODUCTION'}</b></div>
        <div><span>WORKER</span><b className={cfg.worker_paired?'green-text':''}>{cfg.demo_mode?'SIMULATED':cfg.worker_paired?'PAIRED':'NOT PAIRED'}</b></div>
        <div><span>SITES</span><b>{cfg.sites.length}</b></div>
        <div><span>DOMAIN CONTROLLERS</span><b>{totalDcs}</b></div>
        <div><span>ENABLED DCS</span><b>{activeDcs}</b></div>
      </div>

      <div className="identity-model-note">
        <ShieldCheck size={18}/>
        <div>
          <b>NO ACTIVE DIRECTORY PASSWORD IS STORED ON THE MAC</b>
          <span>The Windows Worker runs under a domain identity (recommended: gMSA or delegated service account). AD, DNS, DHCP and GPO cmdlets use Windows Integrated Authentication / Kerberos.</span>
        </div>
      </div>

      <div className="connection-config pairing-config">
        <label className="settings-check">
          <input type="checkbox" checked={cfg.demo_mode} onChange={e=>setCfg({...cfg,demo_mode:e.target.checked})}/>
          <span>DEMO MODE</span>
          <small>Disable this after the Windows Worker is installed and paired.</small>
        </label>

        <label>
          <span>WINDOWS WORKER URL</span>
          <input value={cfg.worker_url||''} onChange={e=>setCfg({...cfg,worker_url:e.target.value})} placeholder="http://windows-management-host:8765"/>
          <small>Use a dedicated domain-joined Windows management host, not a Domain Controller.</small>
        </label>

        <label>
          <span>ONE-TIME PAIRING CODE</span>
          <input type="password" autoComplete="off" value={pairingCode} onChange={e=>setPairingCode(e.target.value)} placeholder={cfg.worker_paired?'restart worker only if re-pairing is required':'shown when run-worker.ps1 starts'}/>
          <small>The code expires after 15 minutes, works once, and is never stored.</small>
        </label>

        <div className="connection-buttons">
          {!cfg.worker_paired&&!cfg.demo_mode&&<Button icon={KeyRound} kind="primary" onClick={pairWorker} disabled={busy==='pair'}>{busy==='pair'?'PAIRING...':'PAIR WORKER'}</Button>}
          {cfg.worker_paired&&!cfg.demo_mode&&<Button icon={Wifi} onClick={testWorker} disabled={busy==='worker'}>{busy==='worker'?'TESTING...':'TEST WORKER'}</Button>}
          {cfg.worker_paired&&!cfg.demo_mode&&<Button icon={Trash2} kind="danger" onClick={unpairWorker} disabled={busy==='unpair'}>{busy==='unpair'?'UNPAIRING...':'UNPAIR'}</Button>}
          <Button icon={Search} onClick={discover} disabled={busy==='discover'||!canUseWorker}>{busy==='discover'?'DISCOVERING...':'DISCOVER DCS FROM AD'}</Button>
          <Button icon={Download} onClick={save} disabled={busy==='save'}>{busy==='save'?'SAVING...':'SAVE SETTINGS'}</Button>
        </div>
      </div>

      {identity&&<div className="worker-identity">
        <div><span>WORKER COMPUTER</span><b>{identity.computer||'—'}</b></div>
        <div><span>RUN-AS IDENTITY</span><b>{identity.runAs||'—'}</b></div>
        <div><span>AD DOMAIN</span><b>{identity.domain||'—'}</b></div>
        <div><span>AUTHENTICATION</span><b className="green-text">WINDOWS INTEGRATED / KERBEROS</b></div>
      </div>}

      {workerTest&&<div className={'connection-result '+(workerTest.ok?'ok':'bad')}>
        <b>{workerTest.ok?'WORKER ONLINE':'WORKER ERROR'}</b>
        <span>{workerTest.ok?'Authenticated management channel is operational.':workerTest.error}</span>
      </div>}
    </section>}

    <section className="window-frame sites-config">
      <div className="window-title"><span>SITE / DOMAIN CONTROLLER MATRIX</span><span>{cfg.sites.length} SITES / {totalDcs} DCS</span></div>
      <div className="sites-toolbar">
        <div>
          <b>MULTI-SITE DIRECTORY TOPOLOGY</b>
          <span>Enabled DCs are used automatically in direct Mac mode. Discovery reads all sites/DCs through one authenticated AD connection; review and save the resulting topology.</span>
        </div>
        <Button icon={Plus} onClick={addSite}>ADD SITE</Button>
      </div>

      <div className="site-list">
        {!cfg.sites.length&&<div className="empty">NO SITES CONFIGURED — ADD A DC OR CONNECT AND DISCOVER ACTIVE DIRECTORY</div>}
        {cfg.sites.map((site,si)=><section className="site-card" key={si}>
          <div className="site-head">
            <div className="site-fields">
              <label><span>SITE NAME</span><input value={site.name||''} onChange={e=>updateSite(si,'name',e.target.value)} placeholder="Site name"/></label>
              <label><span>CODE</span><input value={site.code||''} onChange={e=>updateSite(si,'code',e.target.value)} placeholder="HQ"/></label>
              <label className="site-description"><span>DESCRIPTION</span><input value={site.description||''} onChange={e=>updateSite(si,'description',e.target.value)} placeholder="Optional description"/></label>
            </div>
            <div className="site-tools">
              <span>{site.dcs.length} DC</span>
              <Button icon={Plus} onClick={()=>addDc(si)}>ADD DC</Button>
              <Button icon={Trash2} kind="danger" onClick={()=>removeSite(si)}>REMOVE SITE</Button>
            </div>
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
                <input value={dc.notes||''} onChange={e=>updateDc(si,di,'notes',e.target.value)} placeholder="GC / preferred / notes"/>
                <div className="dc-health">
                  {!result?<span className="health unknown">NOT TESTED</span>:result.loading?<span className="health unknown">TESTING</span>:<span className={'health '+(result.ok?'good':'bad')}>{result.ok?'ONLINE':'FAILED'}</span>}
                  {result&&result.ok&&<small>{isNative?'Verified LDAPS · '+result.host:`DNS ${result.dns?'✓':'×'} · LDAP ${result.ldap?'✓':'×'} · KRB ${result.kerberos?'✓':'×'} · GC ${result.globalCatalog?'✓':'×'}`}</small>}
                </div>
                <div className="dc-actions">
                  <button title="Test DC" disabled={!canUseWorker} onClick={()=>testDc(si,di)}><Activity size={13}/></button>
                  <button title="Remove DC" onClick={()=>removeDc(si,di)}><Trash2 size={13}/></button>
                </div>
              </div>
            })}
          </div>
        </section>)}
      </div>

      <div className="settings-footer">
        <span>{isNative?'Topology and the encrypted AD credential are stored locally. Opening the panel connects automatically.':'Topology is stored locally; the Windows worker uses its own domain identity.'}</span>
        <Button icon={Download} kind="primary" onClick={save} disabled={busy==='save'}>SAVE ALL CHANGES</Button>
      </div>
    </section>
  </div>
}

function NativeUnavailable({section}){
  return <Panel title={section.toUpperCase()} code="N/A"><div className="identity-model-note"><div><b>UNAVAILABLE IN DIRECT MAC MODE</b><span>This connector does not implement this Windows management protocol. No data or successful status is simulated.</span></div></div></Panel>
}
function NativeGPO({notify}){
  const[rows,setRows]=useState([])
  async function load(){try{setRows(await api('/api/gpo'))}catch(e){notify(e.message,'bad')}}
  useEffect(()=>{load()},[])
  return <Panel title="GROUP POLICY / AD INVENTORY" code="GPO" actions={<Button icon={RefreshCw} onClick={load}>REFRESH</Button>}><div className="identity-model-note"><span>LDAP inventory only. GPO editing, permissions, links, backup and SYSVOL reports are unavailable.</span></div><Table rows={rows} rowKey="id" cols={[{key:'displayName',label:'NAME'},{key:'id',label:'GUID'},{key:'status',label:'STATUS'},{key:'modified',label:'MODIFIED'}]}/></Panel>
}

function AuditPage({notify}){
  const[rows,setRows]=useState([])
  async function load(){try{setRows(await api('/api/audit?limit=300'))}catch(e){notify(e.message,'bad')}}
  useEffect(()=>{load()},[])
  return <Panel title="IMMUTABLE CHANGE JOURNAL" code="AUD" actions={<Button icon={RefreshCw} onClick={load}>REFRESH</Button>}><Table rows={rows} rowKey="id" cols={[{key:'at',label:'TIMESTAMP'},{key:'actor',label:'ACTOR'},{key:'role',label:'ROLE'},{key:'action',label:'ACTION'},{key:'target',label:'TARGET'},{key:'status',label:'RESULT',render:v=><Status ok={v==='success'}>{v}</Status>}]} /></Panel>
}


function ServiceConnection({notify,children}){
  const[servers,setServers]=useState([])
  const[cfg,setCfg]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[revision,setRevision]=useState(0)
  useEffect(()=>{api('/api/network-connection').then(setCfg).catch(e=>setError(e.message));api('/api/network-connection/dhcp-servers').then(setServers).catch(e=>setError(e.message))},[])
  async function save(e){e.preventDefault();setBusy(true);setError('');try{await api('/api/network-connection',{method:'PUT',body:JSON.stringify({dns_host:cfg.dns_host,dhcp_host:cfg.dhcp_host,port:Number(cfg.port),dns_mode:cfg.dns_mode,dhcp_mode:cfg.dhcp_mode})});setRevision(x=>x+1);notify('SERVICE CONNECTION SAVED','ok')}catch(e){setError(e.message)}finally{setBusy(false)}}
  return <div className="stack"><details className="service-details"><summary>SERVICE CONNECTION · {cfg?.dns_host} / {cfg?.dhcp_host} · SETTINGS</summary><Panel title="DIRECT DNS / DHCP SERVICE CONNECTION" code="NET"><div className="identity-model-note"><div><b>DIRECT MAC → SERVICE HOST / KERBEROS</b><span>Uses your saved domain account automatically. Direct DNS and DHCP use encrypted Kerberos RPC; the server enforces your existing permissions. Select an authorized DHCP server below. LDAP mode provides DNS inventory only. WinRM is optional.</span></div></div>{error&&<div className="error-box">{error}</div>}{cfg&&<form onSubmit={save} className="service-connection"><Field field={{label:'DNS SERVER FQDN'}} value={cfg.dns_host} onChange={v=>setCfg({...cfg,dns_host:v})}/><Field field={{label:'DHCP SERVER FQDN'}} value={cfg.dhcp_host} onChange={v=>setCfg({...cfg,dhcp_host:v})}/><Field field={{label:'DNS CONNECTION',type:'select',options:['Direct','LDAP','WinRM']}} value={cfg.dns_mode} onChange={v=>setCfg({...cfg,dns_mode:v})}/><Field field={{label:'DHCP CONNECTION',type:'select',options:['RPC','WinRM']}} value={cfg.dhcp_mode} onChange={v=>setCfg({...cfg,dhcp_mode:v})}/><Field field={{label:'WINRM PORT (WINRM MODE ONLY)',type:'number'}} value={cfg.port} onChange={v=>setCfg({...cfg,port:v})}/><Button type="submit" kind="primary" disabled={busy}>{busy?'SAVING...':'SAVE / RETRY'}</Button><small>ACCOUNT: {cfg.username} · {cfg.password_configured?'SAVED DOMAIN PASSWORD':'SAVE DOMAIN PASSWORD IN SETTINGS'}</small>{servers.length>0&&<label className="discovered-dhcp"><span>AUTHORIZED DHCP SERVERS DISCOVERED FROM AD</span><select value={servers.some(x=>x.host===cfg.dhcp_host)?cfg.dhcp_host:''} onChange={e=>setCfg({...cfg,dhcp_host:e.target.value})}><option value="">SELECT DHCP SERVER</option>{servers.map(x=><option key={x.host} value={x.host}>{x.host} / {x.ip}</option>)}</select></label>}</form>}</Panel></details>{cfg&&<div key={revision}>{React.cloneElement(children,{dnsReadOnly:cfg.dns_mode==='LDAP',dnsZoneReadOnly:cfg.dns_mode!=='WinRM',defaultZone:cfg.domain})}</div>}</div>
}

function SshTerminal({device,onClose}){
  const element=useRef(null),[status,setStatus]=useState('CONNECTING'),[error,setError]=useState('')
  useEffect(()=>{
    let active=true,socket=null,observer=null,keepalive=null
    const term=new XTerminal({cursorBlink:true,fontSize:13,fontFamily:'Menlo, monospace',scrollback:3000,theme:{background:'#071516',foreground:'#d4eeee'}})
    const fit=new FitAddon();term.loadAddon(fit);term.open(element.current);fit.fit()
    const send=x=>{if(socket?.readyState===WebSocket.OPEN)socket.send(JSON.stringify(x))}
    const input=term.onData(data=>send({type:'input',data}))
    const resize=term.onResize(({cols,rows})=>send({type:'resize',cols,rows}))
    api('/api/ssh/switches/'+device.id+'/ticket',{method:'POST'}).then(({ticket})=>{
      if(!active)return
      socket=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/api/ssh/switches/'+device.id+'/terminal')
      socket.onopen=()=>send({ticket})
      socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.type==='ready'){setStatus('CONNECTED');fit.fit();send({type:'resize',cols:term.cols,rows:term.rows});term.focus()}else if(m.type==='output'){term.write(Uint8Array.from(atob(m.data),c=>c.charCodeAt(0)))}else if(m.type==='error'){setError(m.message);setStatus('FAILED')}}
      socket.onclose=()=>{if(active)setStatus(x=>x==='FAILED'?x:'DISCONNECTED')}
      socket.onerror=()=>{if(active)setError('Terminal channel failed. Click Disconnect and connect again.')}
      keepalive=setInterval(()=>send({type:'ping'}),30000)
      observer=new ResizeObserver(()=>fit.fit());observer.observe(element.current)
    }).catch(e=>{if(active){setStatus('FAILED');setError(e.message)}})
    return()=>{active=false;clearInterval(keepalive);send({type:'disconnect'});socket?.close();observer?.disconnect();input.dispose();resize.dispose();term.dispose()}
  },[device.id])
  return <Panel title={'SSH / '+device.name+' / '+device.host} code="PTY" actions={<><Status ok={status==='CONNECTED'}>{status}</Status><Button icon={LogOut} onClick={onClose}>DISCONNECT</Button></>}>{error&&<div className="error-box">{error}</div>}<div ref={element} className="ssh-terminal"/><div className="identity-model-note"><span>Interactive switch CLI. The saved account is used when you connect. Terminal content is not recorded in the audit log.</span></div></Panel>
}
function SSHPage({notify}){
  const[rows,setRows]=useState([]),[sel,setSel]=useState(null),[modal,setModal]=useState(null),[key,setKey]=useState(null),[session,setSession]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  async function load(){try{setRows(await api('/api/ssh/switches'));setError('')}catch(e){setError(e.message)}}
  useEffect(()=>{load()},[])
  async function inspect(){setBusy(true);setError('');try{setKey(await api('/api/ssh/switches/'+sel.id+'/inspect',{method:'POST'}));setModal('trust')}catch(e){setError(e.message)}finally{setBusy(false)}}
  const fields=[{name:'name',label:'SWITCH NAME'},{name:'host',label:'IP ADDRESS / HOSTNAME'},{name:'port',label:'SSH PORT',type:'number',default:22},{name:'username',label:'YOUR SWITCH USERNAME'},{name:'password',label:modal==='edit'?'PASSWORD (EMPTY KEEPS SAVED PASSWORD)':'SWITCH PASSWORD',type:'password'}]
  async function save(v){const r=await api('/api/ssh/switches'+(modal==='edit'?'/'+sel.id:''),{method:modal==='edit'?'PUT':'POST',body:JSON.stringify({...v,port:Number(v.port)})});setSel(r);notify('SWITCH SAVED','ok');await load()}
  return <div className="stack ssh-page">{error&&<div className="error-box">{error}</div>}<Panel title={'SAVED SSH SWITCHES / '+rows.length} code="SSH" actions={<><Button icon={Plus} kind="primary" onClick={()=>setModal('new')}>ADD SWITCH</Button><Button icon={RefreshCw} onClick={load}>REFRESH</Button></>}><div className="identity-model-note"><div><b>DIRECT SSH FROM THE MAC</b><span>Switch accounts are separate from Active Directory. Passwords are encrypted in local storage and used only after the device host key is approved.</span></div></div><Table rows={rows} selectedKey={sel?.id} onRow={r=>{setSel(r);setKey(null);setError('')}} cols={[{key:'name',label:'NAME'},{key:'host',label:'HOST'},{key:'port',label:'PORT'},{key:'username',label:'ACCOUNT',render:v=>v||'NEEDED'},{key:'password_configured',label:'PASSWORD',render:v=>v?'SAVED':'NEEDED'},{key:'login',label:'LOGIN',render:(_,r)=><Status ok={Boolean(r.username&&r.password_configured&&r.fingerprint)}>{!r.username?'ACCOUNT NEEDED':!r.password_configured?'PASSWORD NEEDED':!r.fingerprint?'VERIFY KEY':'READY'}</Status>},{key:'fingerprint',label:'HOST KEY',render:v=><Status ok={Boolean(v)}>{v?'APPROVED':'VERIFY FIRST'}</Status>}]}/>{sel&&<div className="inline-tools"><span className="ssh-login-status">{!sel.fingerprint?'Verify the host key first.':!sel.username?'Host key approved · Switch username is missing.':!sel.password_configured?'Host key approved · Switch password is missing.':'Host key and login configured · Ready to connect.'}</span><Button icon={KeyRound} onClick={()=>setModal('edit')}>EDIT / CREDENTIALS</Button><Button icon={ShieldCheck} disabled={busy} onClick={inspect}>{busy?'INSPECTING...':'VERIFY HOST KEY'}</Button><Button icon={Terminal} kind="primary" disabled={!sel.fingerprint||Boolean(session)} onClick={()=>{if(!sel.password_configured||!sel.username){setError('The host key is approved. Save this switch username and password to connect.');setModal('edit')}else{setError('');setSession(sel)}}}>CONNECT</Button><Button icon={Trash2} kind="danger" disabled={Boolean(session)} onClick={()=>setModal('delete')}>DELETE</Button></div>}</Panel>
  {session&&<SshTerminal device={session} onClose={()=>setSession(null)}/>}
  {(modal==='new'||modal==='edit')&&<Modal title={modal==='edit'?'EDIT SSH SWITCH':'ADD SSH SWITCH'} subtitle="Credentials are optional when adding inventory. Save your switch account here before connecting." fields={fields} initial={modal==='edit'?{...sel,password:''}:{}} submitLabel="SAVE SWITCH" onClose={()=>setModal(null)} onSubmit={save}/>}
  {modal==='trust'&&key&&<Modal title="VERIFY SWITCH HOST KEY" subtitle={'Compare this SHA256 fingerprint with the switch console or a trusted administrator before approving. '+key.host+':'+key.port} fields={[]} submitLabel="APPROVE HOST KEY" onClose={()=>setModal(null)} onSubmit={async()=>{const r=await api('/api/ssh/switches/'+sel.id+'/trust',{method:'POST',body:JSON.stringify({fingerprint:key.fingerprint})});setSel(r);load()}}><div className="ssh-fingerprint"><b>{key.algorithm}</b><code>{key.fingerprint}</code><span>Approval is required only once. A changed host key blocks login before sending your password.</span></div></Modal>}
  {modal==='delete'&&sel&&<Modal title={'REMOVE SWITCH / '+sel.name} fields={[]} danger submitLabel="REMOVE" onClose={()=>setModal(null)} onSubmit={async()=>{await api('/api/ssh/switches/'+sel.id,{method:'DELETE'});setSel(null);await load()}}/>}
  </div>
}

function App(){
  const[section,setSection]=useState(()=>location.hash.slice(1)||'users'),[revision,setRevision]=useState(0),[me,setMe]=useState(null),[toast,setToast]=useState(null),[clock,setClock]=useState(new Date()),[shell,setShell]=useState({summary:null,controllers:[],replication:[],ous:[],audit:[],health:null})
  function notify(text,kind='ok'){setToast({text,kind});setTimeout(()=>setToast(null),3200)}
  async function refreshShell(){
    const results=await Promise.allSettled([api('/api/domain/summary'),api('/api/domain/controllers'),api('/api/domain/replication'),api('/api/ad/ous'),api('/api/audit?limit=12'),api('/api/health'),api('/api/settings')])
    const val=i=>results[i].status==='fulfilled'?results[i].value:null
    setShell({summary:val(0),controllers:val(1)||[],replication:val(2)||[],ous:val(3)||[],audit:val(4)||[],health:val(5),settings:val(6)})
  }
  useEffect(()=>{api('/api/auth/me').then(setMe).catch(()=>{});refreshShell();const tick=setInterval(()=>setClock(new Date()),1000);const poll=setInterval(refreshShell,30000);const settingsChanged=()=>{refreshShell();setRevision(x=>x+1)};window.addEventListener('directory-settings-changed',settingsChanged);return()=>{clearInterval(tick);clearInterval(poll);window.removeEventListener('directory-settings-changed',settingsChanged)}},[])
  const Page=useMemo(()=>({overview:Overview,domain:Domain,users:UsersPage,groups:GroupsPage,computers:ComputersPage,ous:OUsPage,recycle:RecyclePage,dns:DNSPage,dhcp:DHCPPage,gpo:GPOPage,audit:AuditPage,ssh:SSHPage,settings:SettingsPage})[section]||Overview,[section])
  const domain=(shell.summary?.domain||shell.settings?.native?.domain||'DIRECTORY.LOCAL').toUpperCase(),dc=shell.controllers?.[0]?.name||'—'
  return <div className="admin-desktop">
    <header className="app-titlebar">
      <div className="app-ident"><span className="app-icon">▣</span><b>RSAT FULL :: ACTIVE DIRECTORY ADMINISTRATION CENTER</b><small>v1.2.3</small></div>
      <div className="connection-strip"><span className={shell.summary?'connected':'red-text'}>[ {shell.summary?'Connected':'Directory offline'} ]</span><span>Domain: <b className="green-text">{domain}</b></span><span>DC: <u>{dc}</u></span><span>{clock.toLocaleDateString()} &nbsp; {clock.toLocaleTimeString()}</span><span>▣ &nbsp; {me?.username||'admin'}⌄</span></div>
    </header>
    <nav className="module-tabs">{nav.map(([id,num,label,Icon])=><button key={id} className={section===id?'active':''} onClick={()=>setSection(id)}><span>[{num}]</span><Icon size={13}/>{label}</button>)}</nav>
    <div className="desktop-main">
      <DirectoryTree section={section} setSection={setSection} shell={shell}/>
      <div className="page-host">{!shell.health?<div className="loading">READING CONNECTION SETTINGS...</div>:shell.health?.connection_mode==='native'&&['recycle'].includes(section)?<NativeUnavailable section={section}/>:shell.health?.connection_mode==='native'&&section==='gpo'?<NativeGPO key={revision} notify={notify}/>:shell.health?.connection_mode==='native'&&['dns','dhcp'].includes(section)?<ServiceConnection key={section+revision} notify={notify}><Page notify={notify} native/></ServiceConnection>:<Page key={section==='settings'?'settings':revision} notify={notify} native={shell.health?.connection_mode==='native'}/>}</div>
    </div>
    <BottomDock shell={shell} section={section}/>
    <Toast toast={toast}/>
  </div>
}

createRoot(document.getElementById('root')).render(localStorage.getItem(TOKEN)?<App/>:<Login/>)
