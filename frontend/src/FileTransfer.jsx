import React,{useEffect,useRef,useState} from 'react'
import {ArrowUp,Download,Upload,Folder,Plus,RefreshCw,LogOut,FileText,Pencil,Trash2,ShieldCheck,X} from 'lucide-react'
import {formatApiError} from './api-errors.mjs'
import {bytes,localPath,localRows,remoteJoin,uploadFiles,MAX_FILE_BYTES} from './file-transfer.mjs'

const ready=row=>Boolean(row?.username&&row?.password_configured&&row?.fingerprint)
const inventory=row=>'/api/ssh/'+(row.kind==='linux'?'linux-servers':'switches')+'/'+row.id
const endpoint=row=>'/api/sftp/'+row.kind+'/'+row.id
const auth=()=>({Authorization:'Bearer '+localStorage.getItem('rsat_token')})
const parent=path=>path.split('/').slice(0,-1).join('/')||'/'

async function responseError(response){
  let message='Request failed (HTTP '+response.status+')'
  try{message=formatApiError(await response.json())}catch{}
  return Object.assign(new Error(message),{status:response.status})
}
function putFile(job,signal,progress){
  return new Promise((resolve,reject)=>{
    const query=new URLSearchParams({path:job.path,overwrite:String(Boolean(job.overwrite)),create_parents:String(Boolean(job.createParents))})
    if(job.expected){query.set('expected_mtime',job.expected.modified);query.set('expected_size',job.expected.size)}
    const xhr=new XMLHttpRequest(),abort=()=>xhr.abort()
    xhr.open('PUT',endpoint(job.server)+'/file?'+query)
    xhr.setRequestHeader('Authorization',auth().Authorization);xhr.setRequestHeader('Content-Type','application/octet-stream')
    xhr.upload.onprogress=e=>progress(e.loaded,e.total||job.file.size,e.loaded===(e.total||job.file.size)?'COMMITTING':'UPLOADING')
    xhr.onload=()=>{signal.removeEventListener('abort',abort);let data={};try{data=JSON.parse(xhr.responseText)}catch{}
      if(xhr.status>=200&&xhr.status<300)resolve(data)
      else reject(Object.assign(new Error(formatApiError(data)||'Upload failed (HTTP '+xhr.status+')'),{status:xhr.status}))}
    xhr.onerror=()=>{signal.removeEventListener('abort',abort);reject(new Error('Transfer channel failed; check the remote folder before retrying'))}
    xhr.onabort=()=>{signal.removeEventListener('abort',abort);reject(new DOMException('Cancelled; refresh the remote directory to verify its final state','AbortError'))}
    signal.addEventListener('abort',abort,{once:true})
    if(signal.aborted)abort();else xhr.send(job.file)
  })
}

async function getFile(job,signal,progress){
  const response=await fetch(endpoint(job.server)+(job.directory?'/archive':'/file')+'?'+new URLSearchParams({path:job.path}),{headers:auth(),signal})
  if(!response.ok)throw await responseError(response)
  const total=Number(response.headers.get('Content-Length')||0),chunks=[];let count=0
  // ZIP headers can add overhead to the maximum uncompressed file data.
  const cap=MAX_FILE_BYTES+16*1024*1024
  if(total>cap)throw new Error('Download exceeds the browser transfer limit')
  const reader=response.body?.getReader()
  if(!reader)throw new Error('This embedded browser cannot stream downloads')
  try{for(;;){const {done,value}=await reader.read();if(done)break;count+=value.length
    if(count>cap)throw new Error('Download exceeds the transfer limit')
    chunks.push(value);progress(count,total,'DOWNLOADING')
  }}catch(error){await reader.cancel().catch(()=>{});throw error}
  if(total&&count!==total)throw new Error('Download was incomplete; no file was offered for saving')
  const url=URL.createObjectURL(new Blob(chunks,{type:job.directory?'application/zip':'application/octet-stream'}))
  const link=document.createElement('a');link.href=url;link.download=job.name+(job.directory?'.zip':'');document.body.appendChild(link);link.click();link.remove()
  setTimeout(()=>URL.revokeObjectURL(url),60000)
  return {bytes:count,skipped:Number(response.headers.get('X-Skipped-Links')||0)}
}

export default function FileTransferPage({api,ui,notify,navigate}){
  const {Panel,Button,Modal,Table,Status}=ui
  const [servers,setServers]=useState([]),[target,setTarget]=useState(()=>sessionStorage.getItem('rsat_file_target')||''),[connected,setConnected]=useState(null)
  const [remote,setRemote]=useState({path:'',parent:'/',entries:[]}),[path,setPath]=useState('.'),[selected,setSelected]=useState(new Set()),[loading,setLoading]=useState(false),[error,setError]=useState('')
  const [files,setFiles]=useState([]),[localDir,setLocalDir]=useState(''),[localSelected,setLocalSelected]=useState(new Set())
  const [queue,setQueue]=useState([]),[modal,setModal]=useState(null),[key,setKey]=useState(null),[editor,setEditor]=useState(null)
  const runner=useRef(null),mounted=useRef(true),listSequence=useRef(0),pickFiles=useRef(null),pickFolder=useRef(null),currentRemote=useRef(null)
  const chosen=servers.find(row=>row.kind+':'+row.id===target),selectedRows=remote.entries.filter(row=>selected.has(row.name)),one=selectedRows.length===1?selectedRows[0]:null
  const active=queue.some(job=>['QUEUED','RUNNING','COMMITTING','UPLOADING','DOWNLOADING','PREPARING ZIP'].includes(job.status))
  function changeJob(id,patch){if(mounted.current)setQueue(rows=>rows.map(row=>row.id===id?{...row,...patch}:row))}
  async function loadServers(){try{const [linux,switches]=await Promise.all([api('/api/ssh/linux-servers'),api('/api/ssh/switches')]);setServers([...linux.map(row=>({...row,kind:'linux'})),...switches.map(row=>({...row,kind:'switch'}))])}catch(err){setError(err.message)}}
  useEffect(()=>{mounted.current=true;loadServers();return()=>{mounted.current=false;listSequence.current++;runner.current?.controller.abort()}},[])
  async function browse(server,directory){
    const sequence=++listSequence.current;setLoading(true);setError('')
    try{const result=await api(endpoint(server)+'/list?'+new URLSearchParams({path:directory}));if(!mounted.current||sequence!==listSequence.current)return
      currentRemote.current={server,path:result.path};setConnected(server);setRemote(result);setPath(result.path);setSelected(new Set());if(result.truncated)setError('Showing the first 10,000 entries. Use a more specific directory.')
    }catch(err){if(mounted.current&&sequence===listSequence.current)setError(err.message);throw err}
    finally{if(mounted.current&&sequence===listSequence.current)setLoading(false)}
  }
  const browseCurrent=directory=>connected&&browse(connected,directory).catch(()=>{})
  function stage(incoming){try{const list=Array.from(incoming);list.forEach(localPath);setFiles(list);setLocalDir('');setLocalSelected(new Set());setError('')}catch(err){setError(err.message)}}
  function toggle(setter,name){setter(current=>{const next=new Set(current);if(next.has(name))next.delete(name);else next.add(name);return next})}
  function enqueue(jobs){setQueue(rows=>[...rows,...jobs.map(job=>({...job,id:crypto.randomUUID(),status:'QUEUED',loaded:0,total:job.file?.size||0,message:''}))])}
  function uploadSelected(){if(!connected)return;try{const jobs=uploadFiles(files,localSelected,localDir,remote.path);if(jobs.some(job=>job.file.size>MAX_FILE_BYTES))throw new Error('Maximum file size is 512 MiB');enqueue(jobs.map(job=>({...job,type:'upload',name:job.file.name,server:connected})))}catch(err){setError(err.message)}}
  function downloadSelected(){if(connected)enqueue(selectedRows.filter(row=>['file','directory'].includes(row.type)).map(row=>({type:'download',name:row.name,directory:row.type==='directory',path:remoteJoin(remote.path,row.name),server:connected})))}
  function cancel(id){if(runner.current?.id===id)runner.current.controller.abort();else changeJob(id,{status:'CANCELLED',message:'Not started'})}
  useEffect(()=>{
    if(runner.current)return
    const job=queue.find(row=>row.status==='QUEUED');if(!job)return
    const controller=new AbortController();runner.current={id:job.id,controller};changeJob(job.id,{status:job.directory?'PREPARING ZIP':'RUNNING'})
    const progress=(loaded,total,status)=>changeJob(job.id,{loaded,total,status})
    ;(job.type==='upload'?putFile(job,controller.signal,progress):getFile(job,controller.signal,progress)).then(result=>{
      changeJob(job.id,{status:'DONE',loaded:result.bytes,message:job.type==='upload'?'Remote size verified':result.skipped?'Ready to save · '+result.skipped+' links/special files skipped':'Ready to save / check your download location'})
      const current=currentRemote.current
      if(job.type==='upload'&&mounted.current&&current&&current.server.kind===job.server.kind&&current.server.id===job.server.id)browse(current.server,current.path).catch(()=>{})
    }).catch(err=>changeJob(job.id,{status:err.name==='AbortError'?'CANCELLED':err.status===409&&err.message.startsWith('File already exists.')?'CONFLICT':'FAILED',message:err.message}))
      .finally(()=>{runner.current=null;if(mounted.current)setQueue(rows=>[...rows])})
  },[queue])
  async function inspect(){if(!chosen)return;try{setKey(await api(inventory(chosen)+'/inspect',{method:'POST'}));setModal({type:'trust'})}catch(err){setError(err.message)}}
  function disconnect(){listSequence.current++;currentRemote.current=null;runner.current?.controller.abort();setQueue(rows=>rows.map(row=>row.status==='QUEUED'?{...row,status:'CANCELLED',message:'Disconnected before starting'}:row));setConnected(null);setRemote({path:'',parent:'/',entries:[]});setSelected(new Set())}
  async function openEditor(){
    if(!one||one.type!=='file')return
    if(one.size>512*1024){setError('The built-in text editor supports UTF-8 files up to 512 KiB');return}
    setLoading(true)
    try{const response=await fetch(endpoint(connected)+'/file?'+new URLSearchParams({path:remoteJoin(remote.path,one.name)}),{headers:auth()});if(!response.ok)throw await responseError(response)
      if(Number(response.headers.get('Content-Length')||0)>512*1024){await response.body?.cancel();throw new Error('File exceeds editor limit')}
      const buffer=await response.arrayBuffer();if(buffer.byteLength>512*1024)throw new Error('File exceeds editor limit')
      const text=new TextDecoder('utf-8',{fatal:true}).decode(buffer);if(text.includes('\0'))throw new Error('Binary files cannot be edited as text')
      setEditor({text,path:remoteJoin(remote.path,one.name),name:one.name,server:connected,expected:{modified:one.modified,size:one.size}});setModal({type:'editor'})
    }catch(err){setError(err.message)}finally{setLoading(false)}
  }
  function drop(event,upload=false){event.preventDefault();const items=Array.from(event.dataTransfer.items||[]);if(items.some(item=>item.webkitGetAsEntry?.()?.isDirectory)){setError('Use CHOOSE FOLDER to include nested folders');return}
    const list=Array.from(event.dataTransfer.files);if(!upload){stage(list);return}
    if(!connected){setError('Connect to a server first');return}
    try{const jobs=list.map(file=>{if(file.size>MAX_FILE_BYTES)throw new Error('Maximum file size is 512 MiB');return {file,type:'upload',name:file.name,path:remoteJoin(remote.path,localPath(file)),server:connected}});enqueue(jobs)}catch(err){setError(err.message)}
  }
  const local=localRows(files,localDir)
  return <div className="stack file-transfer-page">
    {error&&<div role="alert" className="error-box">{error}</div>}
    <Panel title="FILE TRANSFER / SFTP" code="SFTP" actions={<><Button icon={Plus} onClick={()=>navigate('linux')}>MANAGE SERVERS</Button><Button icon={RefreshCw} disabled={active} onClick={loadServers}>REFRESH HOSTS</Button></>}>
      <div className="file-connect"><label><span>SAVED SSH HOST</span><select aria-label="SFTP server" value={target} disabled={active||Boolean(connected)} onChange={e=>{setTarget(e.target.value);sessionStorage.setItem('rsat_file_target',e.target.value);setError('')}}><option value="">SELECT SERVER / SWITCH</option>{servers.map(row=><option key={row.kind+':'+row.id} value={row.kind+':'+row.id}>{row.kind==='linux'?'SERVER':'SWITCH'} · {row.name} · {row.host}</option>)}</select></label>
        <Button icon={ShieldCheck} disabled={!chosen||Boolean(connected)} onClick={inspect}>VERIFY HOST KEY</Button>
        <Button kind="primary" disabled={!ready(chosen)||Boolean(connected)||loading} onClick={()=>browse(chosen,'.').catch(()=>{})}>{loading?'CONNECTING…':'CONNECT SFTP'}</Button>
        <Button icon={LogOut} disabled={!connected} onClick={disconnect}>DISCONNECT</Button>
      </div>
      <div className="identity-model-note"><span>Uses your saved SSH account and approved host key. {chosen&&!ready(chosen)?'Save the account/password and verify its key in SSH / Linux Servers first.':'Only files permitted by the remote account are accessible.'} Maximum 512 MiB per file; no FTP or separate client is required.</span></div>
    </Panel>
    <div className="file-panes">
      <div onDragOver={event=>event.preventDefault()} onDrop={event=>drop(event)}><Panel className="file-browser-panel" title="LOCAL / SELECTED MAC FILES" code="MAC" actions={<><Button icon={Plus} onClick={()=>pickFiles.current.click()}>CHOOSE FILES</Button><Button icon={Folder} onClick={()=>pickFolder.current.click()}>CHOOSE FOLDER</Button></>}>
        <input aria-label="Choose local files" ref={pickFiles} type="file" multiple hidden onChange={e=>stage(e.target.files)}/><input aria-label="Choose local folder" ref={pickFolder} type="file" multiple webkitdirectory="" hidden onChange={e=>stage(e.target.files)}/>
        <div className="file-path"><Button icon={ArrowUp} disabled={!localDir} onClick={()=>{setLocalDir(localDir.includes('/')?parent(localDir):'');setLocalSelected(new Set())}}>UP</Button><code>{localDir||'SELECTED FILES / DROP FILES HERE'}</code></div>
        <Table rows={local} rowKey="path" onRow={row=>toggle(setLocalSelected,row.path)} empty="Choose files / a folder, or drop files here" cols={[
          {key:'select',label:'',render:(_,row)=><input aria-label={'Select local '+row.name} type="checkbox" checked={localSelected.has(row.path)} onClick={e=>e.stopPropagation()} onChange={()=>toggle(setLocalSelected,row.path)}/>},
          {key:'name',label:'NAME',render:(_,row)=><button className="file-name" onClick={e=>{if(row.type==='directory'){e.stopPropagation();setLocalDir(row.path);setLocalSelected(new Set())}}}>{row.type==='directory'?'▣ ':'▤ '}{row.name}</button>},
          {key:'size',label:'SIZE',render:value=>bytes(value)}]}/>
        <div className="inline-tools"><Button onClick={()=>setLocalSelected(new Set(local.map(row=>row.path)))}>SELECT ALL</Button><Button icon={Upload} kind="primary" disabled={!connected||!localSelected.size} onClick={uploadSelected}>UPLOAD SELECTED →</Button></div>
      </Panel></div>
      <div onDragOver={event=>event.preventDefault()} onDrop={event=>drop(event,true)}><Panel className="file-browser-panel" title={'REMOTE / '+(connected?.name||'NOT CONNECTED')} code="HOST" actions={<Button icon={RefreshCw} disabled={!connected||loading} onClick={()=>browseCurrent(remote.path)}>REFRESH</Button>}>
        <form className="file-path" onSubmit={e=>{e.preventDefault();browseCurrent(path)}}><Button icon={ArrowUp} disabled={!connected||loading||remote.path==='/'} onClick={()=>browseCurrent(remote.parent)}>UP</Button><input aria-label="Remote directory" value={path} disabled={!connected} onChange={e=>setPath(e.target.value)}/><Button type="submit" disabled={!connected||loading}>GO</Button></form>
        <Table rows={remote.entries} rowKey="name" onRow={row=>toggle(setSelected,row.name)} empty={connected?'DIRECTORY IS EMPTY':'CONNECT SFTP TO BROWSE FILES'} cols={[
          {key:'select',label:'',render:(_,row)=><input aria-label={'Select remote '+row.name} type="checkbox" checked={selected.has(row.name)} onClick={e=>e.stopPropagation()} onChange={()=>toggle(setSelected,row.name)}/>},
          {key:'name',label:'NAME',render:(_,row)=><button className="file-name" onClick={e=>{if(row.type==='directory'){e.stopPropagation();browseCurrent(remoteJoin(remote.path,row.name))}}}>{row.type==='directory'?'▣ ':row.type==='link'?'↗ ':'▤ '}{row.name}</button>},
          {key:'size',label:'SIZE',render:value=>bytes(value)},{key:'permissions',label:'MODE'},
          {key:'modified',label:'MODIFIED',render:value=>value?new Date(value*1000).toLocaleString():'—'}]}/>
        <div className="inline-tools"><Button icon={Download} disabled={!selectedRows.some(row=>['directory','file'].includes(row.type))} onClick={downloadSelected}>DOWNLOAD / ZIP</Button><Button icon={Folder} disabled={!connected} onClick={()=>setModal({type:'mkdir'})}>NEW FOLDER</Button><Button icon={Pencil} disabled={!one} onClick={()=>setModal({type:'rename',entry:one})}>RENAME</Button><Button icon={FileText} disabled={!one||one.type!=='file'||loading} onClick={openEditor}>EDIT TEXT</Button><Button disabled={!one} onClick={()=>setModal({type:'chmod',entry:one})}>PERMISSIONS</Button><Button icon={Trash2} kind="danger" disabled={!one} onClick={()=>setModal({type:'delete',entry:one})}>DELETE</Button></div>
      </Panel></div>
    </div>
    <Panel title={'TRANSFER QUEUE / '+queue.length} code="Q" actions={<Button disabled={active} onClick={()=>setQueue([])}>CLEAR FINISHED</Button>}>
      <Table rows={queue} empty="No transfers. Files remain local until you upload them." cols={[
        {key:'type',label:'DIRECTION',render:value=>value==='upload'?'MAC → HOST':'HOST → MAC'},
        {key:'name',label:'FILE'},{key:'server',label:'SERVER',render:value=>value.name},
        {key:'status',label:'STATE',render:(value,row)=><><Status ok={value==='DONE'?true:['FAILED','CONFLICT'].includes(value)?false:null}>{value}</Status><small className="file-queue-message">{row.message}</small></>},
        {key:'loaded',label:'PROGRESS',render:(value,row)=><span>{bytes(value)}{row.total?' / '+bytes(row.total):''}<progress aria-label={'Progress '+row.name} value={value} max={row.total||Math.max(value,1)}/></span>},
        {key:'action',label:'ACTION',render:(_,row)=><>{['QUEUED','RUNNING','UPLOADING','COMMITTING','DOWNLOADING','PREPARING ZIP'].includes(row.status)&&<Button icon={X} onClick={()=>cancel(row.id)}>CANCEL</Button>}{row.status==='CONFLICT'&&<Button kind="danger" onClick={()=>setModal({type:'overwrite',job:row})}>OVERWRITE…</Button>}{row.status==='FAILED'&&<Button onClick={()=>enqueue([{...row}])}>RETRY</Button>}</>} ]}/>
      <div className="identity-model-note"><span>DONE on upload means remote size verified. Downloads are offered to your browser/native save dialog. Folder downloads are ZIP files; symlinks and special files are skipped. Cancellation can race with final commit: refresh before retrying. Leaving this page cancels queued work; transfers do not resume after closing the app.</span></div>
    </Panel>
    {modal?.type==='trust'&&key&&<Modal title="VERIFY SFTP HOST KEY" subtitle={'Independently compare this fingerprint with the host console. '+chosen.host+':'+chosen.port} fields={[]} submitLabel="APPROVE HOST KEY" onClose={()=>setModal(null)} onSubmit={async()=>{await api(inventory(chosen)+'/trust',{method:'POST',body:JSON.stringify({fingerprint:key.fingerprint})});await loadServers()}}><div className="ssh-fingerprint"><b>{key.algorithm}</b><code>{key.fingerprint}</code></div></Modal>}
    {['mkdir','rename','chmod'].includes(modal?.type)&&<Modal title={{mkdir:'NEW REMOTE FOLDER',rename:'RENAME REMOTE ITEM',chmod:'REMOTE PERMISSIONS'}[modal.type]} subtitle={remote.path} fields={[{name:'value',label:modal.type==='chmod'?'OCTAL MODE (e.g. 0644)':'NAME',required:true}]} initial={{value:modal.type==='mkdir'?'':modal.type==='chmod'?modal.entry.mode:modal.entry.name}} submitLabel="APPLY" onClose={()=>setModal(null)} onSubmit={async values=>{
      const body=modal.type==='mkdir'?{path:remoteJoin(remote.path,values.value)}:modal.type==='rename'?{path:remoteJoin(remote.path,modal.entry.name),destination:remoteJoin(remote.path,values.value)}:{path:remoteJoin(remote.path,modal.entry.name),mode:values.value}
      await api(endpoint(connected)+'/'+modal.type,{method:'POST',body:JSON.stringify(body)});await browse(connected,remote.path);notify('REMOTE CHANGE APPLIED','ok')
    }}/>}
    {modal?.type==='delete'&&<Modal title={'DELETE / '+modal.entry.name} subtitle="This permanently removes this remote file or empty directory. Non-empty directories are never deleted recursively." fields={[]} danger submitLabel="DELETE PERMANENTLY" onClose={()=>setModal(null)} onSubmit={async()=>{await api(endpoint(connected)+'/delete',{method:'POST',body:JSON.stringify({path:remoteJoin(remote.path,modal.entry.name)})});await browse(connected,remote.path)}}/>}
    {modal?.type==='overwrite'&&<Modal title={'OVERWRITE / '+modal.job.name} subtitle={modal.job.server.name+' · '+modal.job.path+' · Existing contents will be replaced only after a complete upload.'} fields={[]} danger submitLabel="OVERWRITE FILE" onClose={()=>setModal(null)} onSubmit={async()=>{changeJob(modal.job.id,{status:'REPLACED',message:'Explicit overwrite queued'});enqueue([{...modal.job,overwrite:true}])}}/>}
    {modal?.type==='editor'&&editor&&<Modal title={'EDIT UTF-8 / '+editor.name} subtitle="Saving replaces this file after a complete upload. Size/mtime changes since opening block the save." fields={[]} submitLabel="SAVE REMOTE FILE" onClose={()=>{setModal(null);setEditor(null)}} onSubmit={async()=>{
      const file=new File([editor.text],editor.name,{type:'text/plain'});if(file.size>512*1024)throw new Error('Editor limit is 512 KiB')
      enqueue([{...editor,type:'upload',file,name:editor.name,overwrite:true}]);setEditor(null)
    }}><textarea aria-label="Remote text file" className="file-editor" value={editor.text} onChange={event=>setEditor({...editor,text:event.target.value})}/></Modal>}
  </div>
}
