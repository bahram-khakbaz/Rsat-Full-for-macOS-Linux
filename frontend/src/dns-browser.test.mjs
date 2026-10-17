import test from 'node:test'
import assert from 'node:assert/strict'
import {dnsFolderView,dnsBreadcrumbs,dnsRecordOwner,relativeDnsName} from './dns-browser.mjs'

const zone='example.com'
const records=[
  {id:1,name:'@',type:'SOA',value:'test'},
  {id:2,name:'www',type:'A',value:'192.0.2.1'},
  {id:3,name:'_ldap._tcp.dc._msdcs',type:'SRV',value:'0 0 389 dc.example.com.'},
  {id:4,name:'api.dev',type:'A',value:'192.0.2.2'},
  {id:5,name:'api.dev',type:'A',value:'192.0.2.3'},
  {id:6,name:'dev',type:'TXT',value:'parent record'},
  {id:7,name:'*.dev.example.com.',type:'A',value:'192.0.2.4'},
  {id:8,name:'other.notdev',type:'TXT',value:'unrelated'}
]

test('root groups child domains without losing apex or direct records',()=>{
  const root=dnsFolderView(records,zone)
  assert.deepEqual(root.folders.map(f=>f.label),['_msdcs','dev','notdev'])
  assert.deepEqual(root.records.map(r=>r.id),[1,2,6])
  assert.equal(root.folders.find(f=>f.label==='dev').count,3)
})

test('nested folders follow DNS label order and preserve original records for writes',()=>{
  assert.deepEqual(dnsFolderView(records,zone,'_msdcs').folders.map(f=>f.path),['dc._msdcs'])
  assert.deepEqual(dnsFolderView(records,zone,'dc._msdcs').folders.map(f=>f.path),['_tcp.dc._msdcs'])
  const leaf=dnsFolderView(records,zone,'_tcp.dc._msdcs')
  assert.deepEqual(leaf.records.map(r=>r.name),['_ldap._tcp.dc._msdcs'])
  assert.equal(leaf.records[0],records[2])
  assert.deepEqual(dnsBreadcrumbs('_tcp.dc._msdcs').map(c=>c.path),['_msdcs','dc._msdcs','_tcp.dc._msdcs'])
})

test('folder includes parent RR and every value in a multi-value record set',()=>{
  const view=dnsFolderView(records,zone,'DEV')
  assert.deepEqual(view.records.map(r=>r.id),[4,5,6,7])
  assert.equal(relativeDnsName('example.com.',zone),'')
  assert.equal(relativeDnsName('*.dev.example.com.',zone),'*.dev')
})

test('search covers selected subtree, respects label boundaries and handles values/types',()=>{
  assert.deepEqual(dnsFolderView(records,zone,'dev','192.0.2.3').records.map(r=>r.id),[5])
  assert.deepEqual(dnsFolderView(records,zone,'dev','unrelated').records,[])
  assert.deepEqual(dnsFolderView(records,zone,'_msdcs','srv').records.map(r=>r.id),[3])
  assert.deepEqual(dnsFolderView(records,zone,'','_ldap').records.map(r=>r.id),[3])
})

test('new record stays in selected folder and cannot double append a full zone name',()=>{
  assert.equal(dnsRecordOwner('www','dev',zone),'www.dev')
  assert.equal(dnsRecordOwner('@','_tcp.dc._msdcs',zone),'_tcp.dc._msdcs')
  assert.equal(dnsRecordOwner('','',zone),'@')
  assert.equal(dnsRecordOwner('api.dev.example.com.','dev',zone),'api.dev')
  assert.equal(dnsRecordOwner('www.example.com.','',zone),'www')
  assert.throws(()=>dnsRecordOwner('api.other.example.com.','dev',zone),/inside the selected/)
  assert.throws(()=>dnsRecordOwner('api.outside.example.net.','dev',zone),/relative name/)
  assert.throws(()=>dnsRecordOwner('api..dev','dev',zone),/relative name/)
})

test('reverse lookup and empty zones are navigable without fabricated records',()=>{
  const reverse=dnsFolderView([{name:'12.5',type:'PTR'}],'2.0.192.in-addr.arpa','5')
  assert.equal(reverse.records[0].name,'12.5')
  assert.deepEqual(dnsFolderView([],zone),{folders:[],records:[]})
})
