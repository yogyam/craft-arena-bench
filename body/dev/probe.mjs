import { Rcon } from './rcon.mjs'
const rcon = await new Rcon('127.0.0.1', 25575, 'local-dev-only').connect()
for (const c of ['gamerule do_mob_spawning false', 'gamerule minecraft:do_mob_spawning false', 'gamerule doMobSpawning', 'gamerule do_mob_spawning', 'help gamerule',
  'execute if block 0 -61 0 air', 'execute if block 0 -64 0 bedrock', 'execute if block 0 -61 0 grass_block', 'setblock 0 -61 0 stone', 'execute if block 0 -61 0 stone']) {
  const r = await rcon.cmd(c); console.log(`/${c}\n   -> ${r.trim().replace(/\n/g, '\n      ')}`)
}
rcon.close(); process.exit(0)
