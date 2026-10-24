import test from 'node:test'
import assert from 'node:assert/strict'
import {emptySessions,sessionReducer as reduce} from './ssh-sessions.mjs'
const device={id:7,name:'Test Host',host:'127.0.0.1',port:22,username:'operator',password:'must-not-copy'}
const open=(state,id,baseUrl='/api/ssh/linux-servers')=>reduce(state,{type:'open',id,device,baseUrl})
test('server and switch with identical inventory IDs remain independent',()=>{
  let s=open(emptySessions,'server');s=open(s,'switch','/api/ssh/switches');s=open(s,'server-again')
  assert.equal(s.items.length,3);assert.equal(s.activeId,'server-again')
  assert.equal(s.items[0].device.password,undefined)
  s=reduce(s,{type:'status',id:'server',status:'CONNECTED'})
  assert.equal(s.items[0].status,'CONNECTED');assert.equal(s.items[1].status,'CONNECTING')
  s=reduce(s,{type:'select',id:'switch'})
  assert.equal(s.items[0].status,'CONNECTED');assert.equal(s.items.length,3)
})
test('closing one tab preserves peers and chooses a valid adjacent tab',()=>{
  let s=open(open(open(emptySessions,'one'),'two'),'three')
  s=reduce(s,{type:'close',id:'two'});assert.equal(s.activeId,'three');assert.deepEqual(s.items.map(x=>x.id),['one','three'])
  s=reduce(s,{type:'close',id:'three'});assert.equal(s.activeId,'one')
  assert.equal(reduce(s,{type:'status',id:'three',status:'FAILED'}),s)
  assert.equal(reduce(s,{type:'select',id:'missing'}),s)
  s=reduce(s,{type:'close',id:'one'});assert.deepEqual(s,emptySessions)
})
