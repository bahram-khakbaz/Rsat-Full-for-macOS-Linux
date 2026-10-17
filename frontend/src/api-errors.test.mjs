import assert from 'node:assert/strict'
import test from 'node:test'
import {formatApiError} from './api-errors.mjs'

test('validation message excludes password input and context', () => {
  const result = formatApiError({detail:[{loc:['body','new_password'],msg:'String should have at least 8 characters',input:'private-password',ctx:{secret:'private-password'}}]})
  assert.equal(result, 'new_password: String should have at least 8 characters')
  assert.ok(!result.includes('private-password'))
})
test('AD error is preserved and unknown objects are not serialized', () => {
  assert.equal(formatApiError({detail:'Access denied'}), 'Access denied')
  assert.equal(formatApiError({password:'private-password'}), 'Request failed')
})
