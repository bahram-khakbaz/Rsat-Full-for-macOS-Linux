import React,{useEffect,useMemo,useState} from 'react'
import {createRoot} from 'react-dom/client'
import {
  Activity,Archive,Box,ChevronRight,Command,Computer,Database,FileClock,FolderTree,
  Globe2,Group,HardDrive,KeyRound,Link2,LockKeyhole,LogOut,Network,Plus,RefreshCw,
  Search,Server,ShieldCheck,Terminal,Trash2,UnlockKeyhole,UserRoundCog,Users,Wifi
} from 'lucide-react'
import './styles.css'

const TOKEN='rsat_token'
const enc=encodeURIComponent
const nav=[
  ['overview','00','OVERVIEW',Activity],
  ['domain','01','DOMAIN / FOREST',Server],
  ['users','02','USERS',Users],
  ['groups','03','GROUPS',Group],
  ['computers','04','COMPUTERS',Computer],
  ['ous','05','ORGANIZATIONAL UNITS',FolderTree],
  ['recycle','06','RECYCLE BIN',Archive],
  ['dns','07','DNS',Globe2],
  ['dhcp','08','DHCP',Network],
  ['gpo','09','GROUP POLICY',ShieldCheck],
  ['audit','10','AUDIT LOG',FileClock],
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
  const[rows,setRows]=useState([]),[q,setQ]=useState(''),[selected,setSelected]=useState(null),[detail,setDetail]=useState(null),[groups,setGroups]=useState([]),[modal,setModal]=useState(null)
  async function load(){try{setRows(await api('/api/ad/users'+(q?'?q='+enc(q):'')))}catch(e){notify(e.message,'bad')}}
  async function open(r){setSelected(r);try{const[d,g]=await Promise.all([api('/api/ad/users/'+enc(r.samAccountName)),api('/api/ad/users/'+enc(r.samAccountName)+'/groups')]);setDetail(d);setGroups(g)}catch(e){notify(e.message,'bad')}}
  async function act(path,method='POST',body){try{await api(path,{method,body:body?JSON.stringify(body):undefined});notify('COMMAND COMPLETED','ok');await load();if(selected)await open(selected)}catch(e){notify(e.message,'bad')}}
  useEffect(()=>{load()},[])
  const createFields=[['sam_account_name','SAM ACCOUNT'],['given_name','GIVEN NAME'],['surname','SURNAME'],['display_name','DISPLAY NAME'],['email','EMAIL'],['department','DEPARTMENT'],['title','TITLE'],['company','COMPANY'],['manager','MANAGER (SAM/DN)'],['ou','TARGET OU DN'],['password','INITIAL PASSWORD','password']]
  return <div className="split">
    <Panel title="DIRECTORY USERS" code="USR" actions={<><div className="searchbox"><Search size={14}/><input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&load()} placeholder="name / sam / email"/></div><Button icon={Plus} kind="primary" onClick={()=>setModal('create')}>NEW USER</Button><Button icon={RefreshCw} onClick={load}>REFRESH</Button></>}>
      <Table rows={rows} rowKey="samAccountName" selectedKey={selected?.samAccountName} onRow={open} cols={[
        {key:'displayName',label:'DISPLAY NAME',render:(v,r)=><><b>{v}</b><small className="line2">{r.samAccountName}</small></>},
        {key:'department',label:'DEPARTMENT'},{key:'title',label:'TITLE'},
        {key:'enabled',label:'STATE',render:(v,r)=><>{<Status ok={v}>{v?'ENABLED':'DISABLED'}</Status>}{r.lockedOut&&<Status ok={false}>LOCKED</Status>}</>}
      ]}/>
    </Panel>
    <Panel title="OBJECT INSPECTOR" code="OBJ" className="inspector">
      {!detail?<div className="empty inspector-empty">SELECT A USER OBJECT</div>:<>
        <div className="object-head"><div className="avatar">{(detail.displayName||'?').slice(0,2).toUpperCase()}</div><div><h3>{detail.displayName}</h3><p>{detail.samAccountName}</p></div></div>
        <KV items={[['MAIL',detail.mail],['DEPARTMENT',detail.department],['TITLE',detail.title],['COMPANY',detail.company],['MOBILE',detail.mobile],['LAST LOGON',detail.lastLogon],['DN',detail.dn]]}/>
        <div className="action-grid">
          <Button icon={UserRoundCog} onClick={()=>setModal('edit')}>EDIT ATTRIBUTES</Button>
          <Button icon={UnlockKeyhole} onClick={()=>act('/api/ad/users/'+enc(detail.samAccountName)+'/unlock')}>UNLOCK</Button>
          <Button icon={KeyRound} onClick={()=>setModal('password')}>RESET PASSWORD</Button>
          <Button icon={FolderTree} onClick={()=>setModal('move')}>MOVE OU</Button>
          <Button icon={detail.enabled?LockKeyhole:UnlockKeyhole} onClick={()=>act('/api/ad/users/'+enc(detail.samAccountName)+'/'+(detail.enabled?'disable':'enable'))}>{detail.enabled?'DISABLE':'ENABLE'}</Button>
          <Button icon={Trash2} kind="danger" onClick={()=>setModal('delete')}>DELETE</Button>
        </div>
        <div className="subsection"><span className="eyebrow">GROUP MEMBERSHIP</span>{groups.map(g=><div className="mini-row" key={g.name}><Group size={13}/><span>{g.name}</span><small>{g.scope}</small></div>)}</div>
      </>}
    </Panel>
    {modal==='create'&&<Modal title="CREATE DIRECTORY USER" fields={createFields.map(x=>({name:x[0],label:x[1],type:x[2]})).concat([{name:'enabled',label:'ACCOUNT ENABLED',type:'checkbox',default:true},{name:'must_change',label:'CHANGE PASSWORD AT LOGON',type:'checkbox',default:true}])} onClose={()=>setModal(null)} onSubmit={async v=>{await api('/api/ad/users',{method:'POST',body:JSON.stringify(v)});notify('USER CREATED','ok');load()}}/>}
    {modal==='edit'&&detail&&<Modal title={'EDIT '+detail.samAccountName} initial={{display_name:detail.displayName,email:detail.mail,department:detail.department,title:detail.title,company:detail.company,manager:detail.manager,mobile:detail.mobile}} fields={[
      {name:'display_name',label:'DISPLAY NAME'},{name:'email',label:'EMAIL'},{name:'department',label:'DEPARTMENT'},{name:'title',label:'TITLE'},{name:'company',label:'COMPANY'},{name:'manager',label:'MANAGER'},{name:'mobile',label:'MOBILE'}
    ]} onClose={()=>setModal(null)} onSubmit={v=>act('/api/ad/users/'+enc(detail.samAccountName),'PATCH',v)}/>}
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

function AuditPage({notify}){
  const[rows,setRows]=useState([])
  async function load(){try{setRows(await api('/api/audit?limit=300'))}catch(e){notify(e.message,'bad')}}
  useEffect(()=>{load()},[])
  return <Panel title="IMMUTABLE CHANGE JOURNAL" code="AUD" actions={<Button icon={RefreshCw} onClick={load}>REFRESH</Button>}><Table rows={rows} rowKey="id" cols={[{key:'at',label:'TIMESTAMP'},{key:'actor',label:'ACTOR'},{key:'role',label:'ROLE'},{key:'action',label:'ACTION'},{key:'target',label:'TARGET'},{key:'status',label:'RESULT',render:v=><Status ok={v==='success'}>{v}</Status>}]} /></Panel>
}

function App(){
  const[section,setSection]=useState('overview'),[me,setMe]=useState(null),[toast,setToast]=useState(null),[clock,setClock]=useState(new Date())
  const current=nav.find(x=>x[0]===section)
  function notify(text,kind='ok'){setToast({text,kind});setTimeout(()=>setToast(null),3200)}
  useEffect(()=>{api('/api/auth/me').then(setMe).catch(()=>{});const t=setInterval(()=>setClock(new Date()),1000);return()=>clearInterval(t)},[])
  const Page=useMemo(()=>({overview:Overview,domain:Domain,users:UsersPage,groups:GroupsPage,computers:ComputersPage,ous:OUsPage,recycle:RecyclePage,dns:DNSPage,dhcp:DHCPPage,gpo:GPOPage,audit:AuditPage})[section],[section])
  return <div className="app">
    <aside className="sidebar">
      <div className="brand"><div className="brand-glyph">R&gt;</div><div><b>RSAT//FULL</b><span>REMOTE ADMIN SYSTEM</span></div></div>
      <div className="side-rule">DIRECTORY SERVICES</div>
      <nav>{nav.map(([id,num,label,Icon])=><button key={id} className={id===section?'active':''} onClick={()=>setSection(id)}><span className="nav-num">{num}</span><Icon size={15}/><span>{label}</span><ChevronRight size={12} className="arrow"/></button>)}</nav>
      <div className="session"><span>SESSION</span><b>{me?.username||'operator'}</b><small>{me?.role||'...'}</small></div>
      <button className="logout" onClick={()=>{localStorage.removeItem(TOKEN);location.reload()}}><LogOut size={14}/>LOG OUT</button>
    </aside>
    <main>
      <header className="topbar"><div><span className="crumb">ROOT / {current?.[2]}</span><h1>{current?.[2]}</h1></div><div className="top-status"><div><span>LOCAL TIME</span><b>{clock.toLocaleTimeString()}</b></div><div><span>CONTROL PLANE</span><b className="online">● CONNECTED</b></div></div></header>
      <div className="workspace"><Page notify={notify}/></div>
      <footer><span>RSAT FULL ADMIN CENTER // BUILD 0.2.0</span><span>ALL PRIVILEGED ACTIONS ARE AUDITED</span></footer>
    </main>
    <Toast toast={toast}/>
  </div>
}

createRoot(document.getElementById('root')).render(localStorage.getItem(TOKEN)?<App/>:<Login/>)
