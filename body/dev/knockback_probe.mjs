// Does the victim client receive and apply knockback? B stands still, A punches; log velocity packets and B's position.
import mineflayer from 'mineflayer'
import { Rcon } from './rcon.mjs'
const sleep = ms => new Promise(r => setTimeout(r, ms))
const rcon = await new Rcon('127.0.0.1', 25575, 'local-dev-only').connect()
const mk = u => { const b = mineflayer.createBot({ host: '127.0.0.1', port: 25565, username: u, version: '26.1', auth: 'offline' }); return new Promise(r => b.once('spawn', () => r(b))) }
const [A, B] = await Promise.all([mk('ProbeA'), mk('ProbeB')])
await sleep(800)
for (const c of ['gamemode survival ProbeA', 'gamemode survival ProbeB', 'effect give ProbeB minecraft:resistance infinite 4 true', 'tp ProbeB 0.5 -49 5.5 180 0', 'tp ProbeA 0.5 -49 3.0 0 0']) await rcon.cmd(c)
await sleep(600)
const log = []
B._client.on('packet', (data, meta) => { if (/veloc|motion|hurt|damage|knock/i.test(meta.name)) log.push(`pkt ${meta.name} ${JSON.stringify(data).slice(0, 140)}`) })
B.on('entityHurt', e => { if (e === B.entity) log.push(`entityHurt self vel=${B.entity.velocity} pos=${B.entity.position}`) })
let maxZ = B.entity.position.z, maxV = 0
B.on('physicsTick', () => { maxZ = Math.max(maxZ, B.entity.position.z); maxV = Math.max(maxV, Math.hypot(B.entity.velocity.x, B.entity.velocity.z)) })
for (let i = 0; i < 6; i++) { const e = A.players.ProbeB?.entity; if (e) { await A.lookAt(e.position.offset(0, 1.6, 0), true); A.attack(e) } await sleep(400) }
await sleep(500)
console.log(log.slice(0, 12).join('\n') || '(no velocity/hurt packets logged)')
console.log(`B max z ${maxZ.toFixed(2)} (start 5.5), max horizontal velocity ${maxV.toFixed(3)}`)
console.log('server-side B pos:', (await rcon.cmd('data get entity ProbeB Pos')).trim())
console.log('server-side B motion:', (await rcon.cmd('data get entity ProbeB Motion')).trim())
A.quit(); B.quit(); rcon.close(); await sleep(300); process.exit(0)
