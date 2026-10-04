import mineflayer from 'mineflayer'
import { Rcon } from './rcon.mjs'
const sleep = ms => new Promise(r => setTimeout(r, ms))
const rcon = await new Rcon('127.0.0.1', 25575, 'local-dev-only').connect()
const bot = mineflayer.createBot({ host: '127.0.0.1', port: 25565, username: 'Probe', version: '26.1', auth: 'offline' })
await new Promise(r => bot.once('spawn', r))
await sleep(2500)
const p = bot.entity.position
console.log('pos', p.toString(), 'onGround', bot.entity.onGround, 'velocity y', bot.entity.velocity.y.toFixed(3))
for (let y = -58; y >= -65; y--) console.log(`  y=${y}:`, bot.blockAt(p.offset(0, y - p.y, 0))?.name)
console.log('loaded columns:', Object.keys(bot.world.async.columns ?? {}).length)
for (const c of ['execute if block 0 -61 0 grass_block', 'execute if block 0 -64 0 bedrock', 'execute if block 0 -61 0 air', 'gamerule', 'gamerule list', 'gamerule minecraft:spawn_radius 0', 'gamerule spawn_radius 0'])
  console.log(`/${c} -> ${(await rcon.cmd(c)).trim().replace(/\n/g, ' | ')}`)
bot.quit(); rcon.close(); process.exit(0)
