// The body's view of the fight, as one plain object per tick. No decisions here, only reading.

const v3 = v => [round(v.x), round(v.y), round(v.z)]
const round = x => Math.round(x * 1000) / 1000

export function inventoryCounts (bot) {
  const counts = {}
  for (const item of bot.inventory.items()) counts[item.name] = (counts[item.name] ?? 0) + item.count
  return counts
}

export function opponentEntity (bot, name) {
  return bot.players[name]?.entity ?? null
}

// Line of sight from the bot's eyes to the opponent's chest. A solid block in between means not visible.
export function canSee (bot, entity) {
  const from = bot.entity.position.offset(0, bot.entity.height * 0.9, 0)
  const to = entity.position.offset(0, entity.height * 0.6, 0)
  const dir = to.minus(from)
  const dist = dir.norm()
  if (dist < 0.01) return true
  const hit = bot.world.raycast(from, dir.scaled(1 / dist), dist)
  return hit === null
}

export function snapshot (bot, opponentName, tick, intent, lastSeen) {
  const self = bot.entity
  const opp = opponentEntity(bot, opponentName)
  const visible = opp ? canSee(bot, opp) : false
  // Observed velocity: position change since the previous tick. Other players' velocity is not sent while they walk.
  let oppVel = { x: 0, y: 0, z: 0 }
  if (opp) {
    if (lastSeen.prevPos && lastSeen.prevTick === tick - 1) oppVel = opp.position.minus(lastSeen.prevPos)
    lastSeen.prevPos = opp.position.clone(); lastSeen.prevTick = tick
  }
  if (opp && visible) { lastSeen.pos = opp.position.clone(); lastSeen.velocity = oppVel; lastSeen.yaw = opp.yaw; lastSeen.pitch = opp.pitch }
  const oppPos = opp && visible ? opp.position : lastSeen.pos
  return {
    type: 'state',
    tick,
    intent,
    self: {
      pos: v3(self.position), yaw: round(self.yaw * 180 / Math.PI), pitch: round(self.pitch * 180 / Math.PI),
      velocity: v3(self.velocity), on_ground: self.onGround,
      health: round(bot.health), food: bot.food,
      held: bot.heldItem?.name ?? null, inventory: inventoryCounts(bot),
      effects: Object.values(bot.entity.effects ?? {}).map(e => ({ name: bot.registry.effects[e.id]?.name ?? String(e.id), amplifier: e.amplifier }))
    },
    opponent: opp ? {
      pos: oppPos ? v3(oppPos) : null,
      yaw: round((visible ? opp.yaw : lastSeen.yaw ?? 0) * 180 / Math.PI),
      pitch: round((visible ? opp.pitch : lastSeen.pitch ?? 0) * 180 / Math.PI),
      velocity: v3(visible ? oppVel : (lastSeen.velocity ?? oppVel)),
      on_ground: opp.onGround, held: opp.heldItem?.name ?? null,
      visible, distance: oppPos ? round(self.position.distanceTo(oppPos)) : null
    } : null
  }
}
