import test from 'node:test'
import assert from 'node:assert/strict'
import { Rcon } from '../dev/rcon.mjs'

test('rcon client constructs without connecting', () => {
  const r = new Rcon('127.0.0.1', 25575, 'x')
  assert.equal(r.host, '127.0.0.1')
  assert.equal(r.pending.size, 0)
})
