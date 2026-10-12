// A stand-in for a person during tests of the challenge mode: a Mineflayer client that joins, waits, then walks at the
// nearest other player and swings. Usage: node dev/fake_human.mjs [name]
import mineflayer from 'mineflayer'
const name = process.argv[2] ?? 'Tester'
const bot = mineflayer.createBot({ host: '127.0.0.1', port: Number(process.env.CAB_MC_PORT ?? 25565), username: name, version: '26.1', auth: 'offline' })
bot.once('spawn', () => {
  console.log(`${name} joined`)
  bot._client.on('entity_velocity', p => { const e = bot.entities[p.entityId]; if (e && Math.abs(p.velocity.x) < 20) e.velocity.set(p.velocity.x, p.velocity.y, p.velocity.z) })
  let last = -100, tick = 0
  bot.on('physicsTick', () => {
    tick++
    const target = Object.values(bot.players).map(p => p.entity).find(e => e && e !== bot.entity)
    if (!target || bot.game.gameMode === 'spectator') { bot.clearControlStates(); return }
    bot.lookAt(target.position.offset(0, 1.6, 0), true)
    bot.setControlState('forward', true); bot.setControlState('sprint', true)
    if (bot.entity.position.distanceTo(target.position) <= 3 && tick - last >= 8) { bot.attack(target); last = tick }
  })
})
bot.on('kicked', r => console.log('kicked', r))
bot.on('end', () => process.exit(0))
