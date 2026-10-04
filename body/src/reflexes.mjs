// Everything the body does without asking the model, and how each intent is executed.
// This file is the reflex/decision boundary described in docs/INTERFACE.md. Keep it boring.

export const SUMO_INTENTS = ['rush', 'strafe_left', 'strafe_right', 'retreat', 'feint', 'hold']
export const ATTACKING_INTENTS = new Set(['rush', 'strafe_left', 'strafe_right', 'feint', 'hold'])

export const REACH = 3.0            // blocks; vanilla melee reach
export const ATTACK_COOLDOWN = 6    // ticks between swings (fist speed 4/s is 5 ticks; one extra for full knockback)
const ALL_MOVES = ['forward', 'back', 'left', 'right', 'sprint', 'jump']

export class Reflexes {
  constructor (bot, opts) {
    this.bot = bot
    this.mode = opts.mode
    this.platform = opts.platform ?? null   // {min:[x,y,z], max:[x,y,z]} top surface of the Sumo platform, or null
    this.intent = 'hold'
    this.intentTick = 0
    this.lastAttackTick = -100
    this.sprintResetTick = -1
    this.frozen = true
    this.events = []
  }

  setIntent (intent, tick) { this.intent = intent; this.intentTick = tick }

  // Called when the harness resets the tick counter between matches; every tick-stamped timer must restart too.
  reset () { this.intent = 'hold'; this.intentTick = 0; this.lastAttackTick = -100; this.sprintResetTick = -1; this.frozen = true; this.events = []; this.clearMoves() }

  // Called once per physics tick with the opponent entity (may be null).
  tick (tick, opp) {
    const bot = this.bot
    if (this.frozen || !opp) { this.clearMoves(); return }

    const dist = bot.entity.position.distanceTo(opp.position)

    // Reflex: aim at the opponent's head.
    bot.lookAt(opp.position.offset(0, opp.height * 0.9, 0), true)

    // Intent: movement.
    this.clearMoves()
    this.move(tick, dist)

    // Reflex: edge guard. Never walk off the platform unless rushing an opponent in reach.
    if (this.platform && !(this.intent === 'rush' && dist <= REACH) && this.headingOffPlatform()) this.clearMoves()

    // Reflex: swing when in reach and the intent allows attacking.
    if (ATTACKING_INTENTS.has(this.intent) && dist <= REACH && tick - this.lastAttackTick >= ATTACK_COOLDOWN) {
      bot.attack(opp)
      this.lastAttackTick = tick
      this.sprintResetTick = tick       // reflex: drop sprint for one tick so the next sprint hit knocks back again
      this.events.push({ tick, event: 'swung' })
    }
    if (tick === this.sprintResetTick) bot.setControlState('sprint', false)
  }

  move (tick, dist) {
    const bot = this.bot
    switch (this.intent) {
      case 'rush':
        bot.setControlState('forward', true); bot.setControlState('sprint', true); break
      case 'strafe_left':
        bot.setControlState('left', true); if (dist > 4) bot.setControlState('forward', true); break
      case 'strafe_right':
        bot.setControlState('right', true); if (dist > 4) bot.setControlState('forward', true); break
      case 'retreat':
        bot.setControlState('back', true); break
      case 'feint': {
        const phase = tick - this.intentTick
        if (phase < 2) { bot.setControlState('forward', true); bot.setControlState('sprint', true) } else if (phase < 4) bot.setControlState('back', true)
        break
      }
      case 'hold':
      default:
        break
    }
  }

  // Looks a few ticks ahead along the current velocity; true if the ground there is not part of the platform.
  headingOffPlatform () {
    const p = this.bot.entity.position
    const v = this.bot.entity.velocity
    const speed = Math.hypot(v.x, v.z)
    if (speed < 0.02) return false
    const ahead = p.offset(v.x / speed * (speed * 4 + 0.45), 0, v.z / speed * (speed * 4 + 0.45))
    const [minX, , minZ] = this.platform.min
    const [maxX, , maxZ] = this.platform.max
    return ahead.x < minX || ahead.x > maxX + 1 || ahead.z < minZ || ahead.z > maxZ + 1
  }

  clearMoves () { for (const m of ALL_MOVES) this.bot.setControlState(m, false) }

  drainEvents () { const e = this.events; this.events = []; return e }
}
