// Stage 0 check: two Mineflayer bots on the local Paper server; one hits the other; both health values read.
import mineflayer from 'mineflayer'
import { Rcon } from './rcon.mjs'

const HOST = '127.0.0.1', PORT = 25565, VERSION = '26.1'
const sleep = ms => new Promise(r => setTimeout(r, ms))

const rcon = await new Rcon(HOST, 25575, 'local-dev-only').connect()
const say = async (c) => { const r = await rcon.cmd(c); console.log(`  /${c}  ->  ${r.trim() || '(ok)'}`) }

console.log('gamerules:')
// 26.1 names (from the server's own tab completion); old camelCase names no longer work
for (const g of ['spawn_mobs false', 'spawn_monsters false', 'advance_time false', 'advance_weather false', 'natural_health_regeneration false',
  'immediate_respawn true', 'respawn_radius 0', 'show_advancement_messages false', 'show_death_messages true', 'keep_inventory true',
  'fire_spread_radius_around_player 0', 'random_tick_speed 0', 'mob_griefing false', 'spawn_phantoms false', 'spawn_patrols false',
  'spawn_wandering_traders false', 'spawn_wardens false', 'players_sleeping_percentage 101']) await say(`gamerule ${g}`)
await say('time set noon'); await say('weather clear')

function makeBot (username) {
  const bot = mineflayer.createBot({ host: HOST, port: PORT, username, version: VERSION, auth: 'offline' })
  bot.on('kicked', r => console.log(`${username} kicked:`, JSON.stringify(r)))
  bot.on('error', e => console.log(`${username} error:`, e.message))
  return new Promise(res => bot.once('spawn', () => res(bot)))
}

const t0 = Date.now()
const [alpha, bravo] = await Promise.all([makeBot('Alpha'), makeBot('Bravo')])
console.log(`both spawned in ${Date.now() - t0} ms; server version seen by bot: ${alpha.version}`)
console.log('block under Alpha:', alpha.blockAt(alpha.entity.position.offset(0, -1, 0))?.name, 'at y =', alpha.entity.position.y)

await say('list')
await say('gamemode survival Alpha'); await say('gamemode survival Bravo')
await say('tp Alpha 0 -60 0 -90 0'); await say('tp Bravo 2.5 -60 0 90 0')
await say('clear Alpha'); await say('give Alpha diamond_sword 1')
await sleep(800)

const target = () => alpha.players.Bravo?.entity
console.log('Alpha sees Bravo:', !!target(), 'distance:', target() && alpha.entity.position.distanceTo(target().position).toFixed(2))
console.log(`health before: Alpha=${alpha.health}  Bravo=${bravo.health}`)

let swings = 0
for (let i = 0; i < 6; i++) {
  const e = target(); if (!e) break
  await alpha.lookAt(e.position.offset(0, 1.6, 0), true)
  alpha.attack(e); swings++
  await sleep(600)
}
await sleep(500)
console.log(`health after ${swings} swings: Alpha=${alpha.health}  Bravo=${bravo.health}  (Bravo as seen from its own client)`)
console.log('Bravo took damage:', bravo.health < 20 ? 'YES' : 'NO')

alpha.quit(); bravo.quit(); rcon.close()
await sleep(300)
process.exit(0)
