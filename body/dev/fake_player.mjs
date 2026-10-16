// A stand-in for a person in the lobby: joins, types chat commands at given delays, and fights when put in survival.
// Usage: node dev/fake_player.mjs Name "3:!fight house random sumo 5" "90:!me house sumo 5"
import mineflayer from 'mineflayer'
const [name, ...script] = process.argv.slice(2)
const bot = mineflayer.createBot({ host: '127.0.0.1', port: Number(process.env.CAB_MC_PORT ?? 25565), username: name ?? 'Tester', version: '26.1', auth: 'offline' })
bot.on('message', m => { const t = m.toString(); if (t.trim()) console.log('chat:', t.slice(0, 140)) })
bot.once('spawn', () => {
  console.log(`${bot.username} joined`)
  for (const item of script) {
    const [delay, ...rest] = item.split(':'); const text = rest.join(':')
    setTimeout(() => { console.log('typing:', text); bot.chat(text) }, Number(delay) * 1000)
  }
  bot._client.on('entity_velocity', p => { const e = bot.entities[p.entityId]; if (e && Math.abs(p.velocity.x) < 20) e.velocity.set(p.velocity.x, p.velocity.y, p.velocity.z) })
  let last = -100, tick = 0
  bot.on('physicsTick', () => {
    tick++
    if (bot.game.gameMode !== 'survival') { bot.clearControlStates(); return }
    const target = Object.values(bot.players).map(p => p.entity).find(e => e && e !== bot.entity)
    if (!target) return
    bot.lookAt(target.position.offset(0, 1.6, 0), true)
    bot.setControlState('forward', true); bot.setControlState('sprint', true)
    if (bot.entity.position.distanceTo(target.position) <= 3 && tick - last >= 8) { bot.attack(target); last = tick }
  })
})
bot.on('kicked', r => console.log('kicked', r))
bot.on('end', () => process.exit(0))
