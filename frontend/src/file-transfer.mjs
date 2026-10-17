export const MAX_FILE_BYTES=512*1024*1024
export function localPath(file){
  const path=file.webkitRelativePath||file.name
  if(!path||path.startsWith('/')||path.includes('\\')||path.includes('\0')||path.split('/').some(x=>!x||x==='.'||x==='..'))throw new Error('Unsupported local filename or relative path')
  return path
}
export function remoteJoin(base,relative){
  localPath({name:relative})
  return base.replace(/\/$/,'')+'/'+relative
}
export function localRows(files,directory=''){
  const prefix=directory?directory+'/':'',rows=new Map()
  for(const file of files){
    const path=localPath(file)
    if(!path.startsWith(prefix))continue
    const tail=path.slice(prefix.length),parts=tail.split('/'),name=parts[0],key=prefix+name
    if(parts.length>1){if(!rows.has(key))rows.set(key,{name,path:key,type:'directory',size:0});rows.get(key).size+=file.size}
    else rows.set(key,{name,path:key,type:'file',size:file.size,modified:file.lastModified/1000,file})
  }
  return [...rows.values()].sort((a,b)=>(a.type!=='directory')-(b.type!=='directory')||a.name.localeCompare(b.name))
}
export function uploadFiles(files,selected,directory,remote){
  const prefix=directory?directory+'/':''
  return files.filter(file=>{const path=localPath(file);return [...selected].some(key=>path===key||path.startsWith(key+'/'))})
    .map(file=>({file,path:remoteJoin(remote,localPath(file).slice(prefix.length)),createParents:localPath(file).slice(prefix.length).includes('/')}))
}
export function bytes(value){
  if(!Number.isFinite(value))return '—'
  const units=['B','KiB','MiB','GiB'];let index=0
  while(value>=1024&&index<3){value/=1024;index++}
  return value.toFixed(index?1:0)+' '+units[index]
}
