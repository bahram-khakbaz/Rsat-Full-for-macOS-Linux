import React,{useMemo} from 'react'
import {Folder,ChevronRight,ArrowUp,Globe2} from 'lucide-react'
import {dnsFolderView,dnsBreadcrumbs,relativeDnsName,withinDnsFolder} from './dns-browser.mjs'

export default function DnsBrowser({records,zones,zone,folder,onFolder,onZone,query,selected,onSelect,loading,Table,Button}){
  const view=useMemo(()=>dnsFolderView(records,zone,folder,query),[records,zone,folder,query])
  const crumbs=dnsBreadcrumbs(folder)
  const shownZones=useMemo(()=>[...zones].sort((a,b)=>Number(b.name===zone)-Number(a.name===zone)),[zones,zone])
  function branch(path='',depth=0){
    if(depth>127)return null
    return dnsFolderView(records,zone,path).folders.map(child=>{
      const open=folder.toLowerCase()===child.path.toLowerCase()||folder.toLowerCase().endsWith('.'+child.path.toLowerCase())
      return <div key={child.path}>
        <button className={'dns-tree-folder '+(folder===child.path?'active':'')} style={{paddingLeft:12+Math.min(depth,8)*12}} onClick={()=>onFolder(child.path)} title={child.path+'.'+zone}>
          <ChevronRight size={12} className={open?'expanded':''}/><Folder size={13}/><span>{child.label}</span>
        </button>
        {open&&branch(child.path,depth+1)}
      </div>
    })
  }
  return <div className="dns-browser">
    <aside className="dns-zone-tree" aria-label="DNS zones and subdomains">
      <div className="dns-tree-caption">DNS ZONES / {zones.length}</div>
      {shownZones.map(item=><div key={item.name}>
        <button className={'dns-tree-zone '+(zone===item.name&&!folder?'active':'')} onClick={()=>onZone(item.name)} title={item.name}><Globe2 size={14}/><span>{item.name}</span></button>
        {zone===item.name&&branch()}
      </div>)}
      {!zones.length&&<div className="empty">{loading?'READING ZONES...':'NO ZONES AVAILABLE'}</div>}
    </aside>
    <div className="dns-folder-content">
      <nav className="dns-breadcrumbs" aria-label="DNS folder path">
        <Button icon={ArrowUp} disabled={!folder} onClick={()=>onFolder(folder.split('.').slice(1).join('.'))}>UP</Button>
        <button disabled={!zone} onClick={()=>onFolder('')}>{zone||'SELECT ZONE'}</button>
        {crumbs.map(crumb=><React.Fragment key={crumb.path}><ChevronRight size={12}/><button onClick={()=>onFolder(crumb.path)}>{crumb.label}</button></React.Fragment>)}
      </nav>
      <div className="dns-folder-caption">{[folder,zone].filter(Boolean).join('.')} · {view.folders.length} FOLDERS · {view.records.length} RECORDS {query&&'· SEARCH INCLUDES SUBFOLDERS'}</div>
      {!query&&view.folders.length>0&&<div className="dns-folders">{view.folders.map(child=><button key={child.path} onClick={()=>onFolder(child.path)} title={'Open '+child.path+'.'+zone}><Folder size={20}/><span>{child.label}</span><small>{child.count} nested records</small><ChevronRight size={14}/></button>)}</div>}
      <Table rows={view.records} rowKey="id" selectedKey={selected?.id} onRow={onSelect} empty={loading?'READING DNS...':query?'NO MATCHING RECORDS':'NO RECORDS AT THIS LEVEL · OPEN A FOLDER OR CREATE A RECORD'} cols={[
        {key:'name',label:'NAME',render:value=>withinDnsFolder(relativeDnsName(value,zone),folder)||'@ (same as parent)'},
        {key:'type',label:'TYPE'},{key:'value',label:'VALUE'},{key:'ttl',label:'TTL'}
      ]}/>
    </div>
  </div>
}
