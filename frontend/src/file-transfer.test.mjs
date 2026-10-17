import test from 'node:test'
import assert from 'node:assert/strict'
import {localPath,remoteJoin,localRows,uploadFiles} from './file-transfer.mjs'

test('local paths never escape a selected folder',()=>{
  for(const name of ['../secret','/secret','folder/../secret','folder\\secret','folder//file','x\0y'])assert.throws(()=>localPath({name}))
  assert.equal(remoteJoin('/home/user','a b/فارسی.txt'),'/home/user/a b/فارسی.txt')
})
test('local navigation and selected directory upload preserve hierarchy once',()=>{
  const files=[{name:'a',webkitRelativePath:'project/src/a.py',size:4},{name:'b',webkitRelativePath:'project/b.txt',size:2}]
  assert.deepEqual(localRows(files).map(x=>[x.name,x.type]),[['project','directory']])
  const rows=localRows(files,'project')
  assert.equal(rows.length,2)
  const all=uploadFiles(files,new Set(['project']),'','/srv')
  assert.deepEqual(all.map(x=>x.path),['/srv/project/src/a.py','/srv/project/b.txt'])
  const inside=uploadFiles(files,new Set(['project/src']),'project','/srv')
  assert.equal(inside[0].path,'/srv/src/a.py')
  assert.equal(inside.length,1)
})
