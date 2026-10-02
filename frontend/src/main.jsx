import React,{useEffect,useState} from 'react'
import {createRoot} from 'react-dom/client'
import {Activity,Users,Group,Computer,Boxes,Globe2,Network,ShieldCheck,FileClock,LogOut,Search} from 'lucide-react'
import './styles.css'

const sections=[
  ['dashboard','Dashboard',Activity],['users','Users',Users],['groups','Groups',Group],['computers','Computers',Computer],
  ['ous','OUs',Boxes],['dns','DNS',Globe2],['dhcp','DHCP',Network],['gpo','Group Policy',ShieldCheck],['audit','Audit Log',FileClock]
]
const key='rsat_token'
async function api(path,init={}){
  const headers={'Content-Type':'application/json',...(init.headers||{})}
  const t=localStorage.getItem(key); if(t) headers.Authorization='Bearer '+t
  const r=await fetch(path,{...init,headers})
  if(r.status===401){localStorage.removeItem(key);location.reload();throw new Error('Unauthorized')}
  if(!r.ok) throw new Error(await r.text())
  return r.json()
}
function Badge({ok,children}){return <span className={'badge '+(ok===true?'good':ok===false?'bad':'')}>{children}</span>}
function Login(){
  const[u,setU]=useState('admin'),[p,setP]=useState(''),[e,setE]=useState('')
  async function submit(ev){ev.preventDefault();setE('');try{const r=await api('/api/auth/login',{method:'POST',body:JSON.stringify({username:u,password:p})});localStorage.setItem(key,r.access_token);location.reload()}catch{setE('Login failed')}}
  return <div className="login-wrap"><form className="login-card" onSubmit={submit}><div className="logo"><ShieldCheck/></div><h1>RSAT Full</h1><p>Cross-platform infrastructure administration</p><label>Username<input value={u} onChange={x=>setU(x.target.value)}/></label><label>Password<input type="password" value={p} onChange={x=>setP(x.target.value)}/></label>{e&&<div className="error">{e}</div>}<button className="primary">Sign in</button></form></div>
}
function Table({rows,columns}){return <div className="table-wrap"><table><thead><tr>{columns.map(c=><th key={c.k}>{c.t}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={i}>{columns.map(c=><td key={c.k}>{c.render?c.render(r[c.k],r):String(r[c.k]??'-')}</td>)}</tr>)}</tbody></table></div>}
function App(){
  const[section,setSection]=useState('dashboard'),[data,setData]=useState([]),[loading,setLoading]=useState(false),[q,setQ]=useState('')
  async function load(){
    if(section==='dashboard'){setLoading(true);const[u,c]=await Promise.all([api('/api/ad/users'),api('/api/ad/computers')]);setData([{users:u.length,locked:u.filter(x=>x.lockedOut).length,computers:c.length}]);setLoading(false);return}
    const map={users:'/api/ad/users'+(q?'?q='+encodeURIComponent(q):''),groups:'/api/ad/groups',computers:'/api/ad/computers',ous:'/api/ad/ous',dns:'/api/dns/records',dhcp:'/api/dhcp/scopes',gpo:'/api/gpo',audit:'/api/audit'}
    setLoading(true);try{setData(await api(map[section]))}finally{setLoading(false)}
  }
  useEffect(()=>{load()},[section])
  const title=sections.find(x=>x[0]===section)?.[1]
  const cols={
    users:[{k:'displayName',t:'User',render:(v,r)=><><strong>{v}</strong><span className="sub">{r.samAccountName} · {r.mail}</span></>},{k:'department',t:'Department'},{k:'title',t:'Title'},{k:'enabled',t:'Status',render:(v,r)=><><Badge ok={v}>{v?'Enabled':'Disabled'}</Badge>{r.lockedOut&&<Badge ok={false}>Locked</Badge>}</>}],
    groups:[{k:'name',t:'Group'},{k:'description',t:'Description'},{k:'scope',t:'Scope'},{k:'members',t:'Members'}],
    computers:[{k:'name',t:'Computer'},{k:'os',t:'OS'},{k:'enabled',t:'Status',render:v=><Badge ok={v}>{v?'Enabled':'Disabled'}</Badge>},{k:'ou',t:'OU'}],
    ous:[{k:'name',t:'OU'},{k:'dn',t:'Distinguished Name'}],
    dns:[{k:'zone',t:'Zone'},{k:'name',t:'Name'},{k:'type',t:'Type'},{k:'value',t:'Value'},{k:'ttl',t:'TTL'}],
    dhcp:[{k:'scopeId',t:'Scope'},{k:'name',t:'Name'},{k:'startRange',t:'Start'},{k:'endRange',t:'End'},{k:'inUse',t:'In Use'},{k:'free',t:'Free'}],
    gpo:[{k:'displayName',t:'GPO'},{k:'id',t:'ID'},{k:'status',t:'Status'},{k:'modified',t:'Modified'}],
    audit:[{k:'at',t:'Time'},{k:'actor',t:'Actor'},{k:'action',t:'Action'},{k:'target',t:'Target'},{k:'status',t:'Status'}]
  }
  return <div className="shell"><aside><div className="brand"><div className="logo"><Activity/></div><div><b>RSAT Full</b><span>Admin Center</span></div></div><nav>{sections.map(([id,label,Icon])=><button key={id} className={section===id?'active':''} onClick={()=>setSection(id)}><Icon size={18}/>{label}</button>)}</nav><button className="logout" onClick={()=>{localStorage.removeItem(key);location.reload()}}><LogOut size={17}/>Sign out</button></aside><main><header><div><h1>{title}</h1><p>Unified Microsoft infrastructure administration from macOS and Linux.</p></div>{section==='users'&&<div className="search"><Search size={16}/><input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&load()} placeholder="Search users"/></div>}</header>{loading?<div className="card">Loading…</div>:section==='dashboard'?<div className="stats"><div className="card"><span>Directory users</span><strong>{data[0]?.users||0}</strong></div><div className="card"><span>Locked accounts</span><strong>{data[0]?.locked||0}</strong></div><div className="card"><span>Computers</span><strong>{data[0]?.computers||0}</strong></div><div className="card"><span>Control plane</span><strong className="healthy">Healthy</strong></div></div>:<div className="card">{data.length?<Table rows={data} columns={cols[section]}/>:<div className="empty">No data found</div>}</div>}</main></div>
}
createRoot(document.getElementById('root')).render(localStorage.getItem(key)?<App/>:<Login/>)
