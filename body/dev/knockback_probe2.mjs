// Where does the knockback velocity go? Log B's velocity at packet time, after the event loop turn, and at the next physics tick.
import mineflayer from 'mineflayer'
import { Rcon } from './rcon.mjs'
const sleep = ms => new Promise(r => setTimeout(r, ms))
const rcon = await new Rcon('127.0.0.1', 25575, 'local-dev-only').connect()
const mk = u => { const b = mineflayer.createBot({ host: '127.0.0.1', port: 25565, username: u, version: '26.1', auth: 'offline' }); return new Promise(r => b.once('spawn', () => r(b))) }
const [A, B] = await Promise.all([mk('ProbeA'), mk('ProbeB')])
await sleep(800)
for (const c of ['gamemode survival ProbeA', 'gamemode survival ProbeB', 'effect give ProbeB minecraft:resistance infinite 4 true', 'tp ProbeB 0.5 -49 5.5 180 0', 'tp ProbeA 0.5 -49 3.0 0 0']) await rcon.cmd(c)
await sleep(600)
console.log('listeners on entity_velocity before override:', B._client.listenerCount('entity_velocity'))
console.log('bot.entity is bot.entities[id]:', B.entity === B.entities[B.entity.id], 'physicsEnabled:', B.physicsEnabled)
const log = []
let pending = null
B._client.on('entity_velocity', p => {
  if (p.entityId !== B.entity.id) return
  const before = B.entity.velocity.clone()
  B.entity.velocity.set(p.velocity.x, p.velocity.y, p.velocity.z)
  const after = B.entity.velocity.clone()
  pending = { pkt: p.velocity, before, after, pos: B.entity.position.clone() }
  setImmediate(() => { pending.afterImmediate = B.entity.velocity.clone() })
})
B.on('physicsTick', () => {
  if (pending) { log.push(`pkt z=${pending.pkt.z.toFixed(3)} | before ${pending.before.z.toFixed(4)} -> set ${pending.after.z.toFixed(3)} -> afterImmediate ${pending.afterImmediate?.z.toFixed(4)} -> at next tick vel.z ${B.entity.velocity.z.toFixed(4)} pos.z ${pending.pos.z.toFixed(3)} -> ${B.entity.position.z.toFixed(3)}`); pending = null }
})
console.log('listeners on entity_velocity after override:', B._client.listenerCount('entity_velocity'))
for (let i = 0; i < 4; i++) { const e = A.players.ProbeB?.entity; if (e) { await A.lookAt(e.position.offset(0, 1.6, 0), true); A.attack(e) } await sleep(400) }
await sleep(400)
console.log(log.join('\n') || '(no self velocity packets)')
console.log('B pos now', B.entity.position.toString(), '| server:', (await rcon.cmd('data get entity ProbeB Pos')).trim().slice(-30))
A.quit(); B.quit(); rcon.close(); await sleep(300); process.exit(0)
