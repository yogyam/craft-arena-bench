import mineflayer from 'mineflayer'
import { Rcon } from './rcon.mjs'
const sleep = ms => new Promise(r => setTimeout(r, ms))
const rcon = await new Rcon('127.0.0.1', 25575, 'local-dev-only').connect()
await rcon.cmd('op Probe')
const bot = mineflayer.createBot({ host: '127.0.0.1', port: 25565, username: 'Probe', version: '26.1', auth: 'offline' })
await new Promise(r => bot.once('spawn', r))
await sleep(1500)
const all = await bot.tabComplete('/gamerule ')
console.log('server offers', all.length, 'gamerule names:')
console.log(all.map(m => m.match ?? m).sort().join('  '))
await rcon.cmd('deop Probe')
bot.quit(); rcon.close(); process.exit(0)
