// One body: a Mineflayer client for one bot, its reflexes, and a websocket bridge for the harness.
//   node src/main.mjs --username BotA --opponent BotB --ws-port 8701 [--host 127.0.0.1] [--port 25565] [--version 26.1] [--mode sumo]
// The body makes no decisions. It executes the current intent, runs the reflexes, and streams state every tick.
import mineflayer from 'mineflayer'
import { parseArgs } from 'node:util'
import { Bridge } from './bridge.mjs'
import { Reflexes } from './reflexes.mjs'
import { snapshot, opponentEntity } from './state.mjs'

const { values: a } = parseArgs({ options: {
  username: { type: 'string' }, opponent: { type: 'string' }, 'ws-port': { type: 'string' },
  host: { type: 'string', default: '127.0.0.1' }, port: { type: 'string', default: '25565' },
  version: { type: 'string', default: '26.1' }, mode: { type: 'string', default: 'sumo' }
} })
for (const k of ['username', 'opponent', 'ws-port']) if (!a[k]) { console.error(`--${k} is required`); process.exit(2) }

const log = (...m) => console.log(`[${a.username}]`, ...m)
let tick = 0
let reflexes = null
const lastSeen = {}
let bot = null

const bridge = new Bridge(Number(a['ws-port']), msg => {
  switch (msg.type) {
    case 'intent':
      if (reflexes) reflexes.setIntent(msg.intent, tick); break
    case 'freeze':
      if (reflexes) { reflexes.frozen = Boolean(msg.value); if (reflexes.frozen) reflexes.clearMoves() } break
    case 'configure':      // {platform: {min, max}} and anything else the arena needs the body to know
      if (reflexes) reflexes.platform = msg.platform ?? null; break
    case 'reset':
      if (reflexes) reflexes.reset()
      tick = 0; break
    case 'quit':
      shutdown(0); break
    default:
      bridge.send({ type: 'error', error: `unknown message type ${msg.type}` })
  }
})
log(`bridge listening on ws://127.0.0.1:${a['ws-port']}`)

function connect () {
  bot = mineflayer.createBot({ host: a.host, port: Number(a.port), username: a.username, version: a.version, auth: 'offline' })
  reflexes = new Reflexes(bot, { mode: a.mode })

  bot.once('spawn', () => {
    log('spawned')
    // Mineflayer 4.39 scales entity_velocity by 1/8000, which was right for the old short-encoded packet. Since 1.21.9 the
    // packet carries floats in blocks per tick, so knockback came out as ~0 and nobody could be pushed. Apply the raw value.
    // Registered at spawn so it runs after Mineflayer's own handler (attached at login) and overrides it. Remove once upstream fixes it.
    bot._client.on('entity_velocity', p => {
      const e = bot.entities[p.entityId]
      if (e && Math.abs(p.velocity.x) < 20) e.velocity.set(p.velocity.x, p.velocity.y, p.velocity.z)
    })
    bridge.send({ type: 'spawned', username: a.username })
  })
  bot.on('death', () => bridge.send({ type: 'death', tick }))
  bot.on('health', () => bridge.send({ type: 'health', tick, health: bot.health, food: bot.food }))
  bot.on('entityHurt', e => { if (e === bot.entity) reflexes.events.push({ tick, event: 'hurt' }) })
  bot.on('kicked', r => { log('kicked', JSON.stringify(r)); bridge.send({ type: 'kicked', reason: String(r) }) })
  bot.on('error', e => { log('error', e.message); bridge.send({ type: 'error', error: e.message }) })
  bot.on('end', r => { log('disconnected', r); bridge.send({ type: 'disconnected', reason: String(r) }) })

  bot.on('physicsTick', () => {
    tick++
    const opp = opponentEntity(bot, a.opponent)
    try { reflexes.tick(tick, opp) } catch (e) { bridge.send({ type: 'error', error: `reflex: ${e.message}` }) }
    const s = snapshot(bot, a.opponent, tick, reflexes.intent, lastSeen)
    s.events = reflexes.drainEvents()
    s.frozen = reflexes.frozen
    bridge.send(s)
  })
}

function shutdown (code) { try { bot?.quit() } catch {} bridge.close(); setTimeout(() => process.exit(code), 100) }
process.on('SIGINT', () => shutdown(0))
process.on('SIGTERM', () => shutdown(0))
connect()
