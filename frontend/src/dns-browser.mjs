export function relativeDnsName(name,zone){
  const value=String(name??'').trim().replace(/\.$/,'')
  const domain=String(zone??'').replace(/\.$/,'')
  if(!value||value==='@'||value.toLowerCase()===domain.toLowerCase())return ''
  return domain&&value.toLowerCase().endsWith('.'+domain.toLowerCase())?value.slice(0,-domain.length-1):value
}

export function withinDnsFolder(owner,folder){
  if(!folder)return owner
  if(owner.toLowerCase()===folder.toLowerCase())return ''
  return owner.toLowerCase().endsWith('.'+folder.toLowerCase())?owner.slice(0,-folder.length-1):null
}

export function dnsFolderView(records,zone,folder='',query=''){
  const folders=new Map(),direct=[],search=[]
  const needle=query.trim().toLowerCase()
  for(const record of records){
    const local=withinDnsFolder(relativeDnsName(record.name,zone),folder)
    if(local===null)continue
    if(local.includes('.')){
      const label=local.split('.').at(-1),key=label.toLowerCase()
      if(!folders.has(key))folders.set(key,{label,path:[label,folder].filter(Boolean).join('.'),count:0})
      folders.get(key).count++
    }else direct.push(record)
    if(needle&&[record.name,record.value,record.type].some(value=>String(value??'').toLowerCase().includes(needle)))search.push(record)
  }
  return {folders:[...folders.values()].sort((a,b)=>a.label.localeCompare(b.label)),records:needle?search:direct}
}

export function dnsBreadcrumbs(folder){
  const labels=folder?folder.split('.').reverse():[]
  return labels.map((label,index)=>({label,path:labels.slice(0,index+1).reverse().join('.')}))
}

export function dnsRecordOwner(name,folder,zone){
  const value=String(name??'').trim()
  if(!value||value==='@')return folder||'@'
  const bare=value.replace(/\.$/,'')
  const domain=String(zone??'').replace(/\.$/,'')
  if(bare.toLowerCase()===domain.toLowerCase()||bare.toLowerCase().endsWith('.'+domain.toLowerCase())){
    const owner=relativeDnsName(bare,zone)
    if(withinDnsFolder(owner,folder)===null)throw new Error('The full name must be inside the selected DNS folder')
    return owner||'@'
  }
  if(value.endsWith('.')||value.includes('..'))throw new Error('Use a relative name or a full name within this zone')
  return [value,folder].filter(Boolean).join('.')
}
