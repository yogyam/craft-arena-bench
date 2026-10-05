// Everything the body does without asking the model, and how each intent is executed.
// This file is the reflex/decision boundary described in docs/INTERFACE.md. Keep it boring.
import { Vec3 } from 'vec3'

export const SUMO_INTENTS = ['rush', 'strafe_left', 'strafe_right', 'retreat', 'feint', 'hold']
export const UHC_INTENTS = ['rush', 'strafe_left', 'strafe_right', 'retreat', 'shoot_bow', 'place_wall', 'pillar_up', 'bucket_water', 'bucket_lava', 'hold']
export const ATTACKING_INTENTS = new Set(['rush', 'strafe_left', 'strafe_right', 'feint', 'hold'])
const JOB_INTENTS = new Set(['shoot_bow', 'place_wall', 'pillar_up', 'bucket_water', 'bucket_lava'])

export const REACH = 3.0            // blocks; vanilla melee reach
export const ATTACK_COOLDOWN = 6    // ticks between swings (fist speed 4/s is 5 ticks; one extra for full knockback)
const SWORD_COOLDOWN = 13           // diamond sword: 1.6 attacks/s = 12.5 ticks
const ALL_MOVES = ['forward', 'back', 'left', 'right', 'sprint', 'jump']
const UP = new Vec3(0, 1, 0)
const HAZARDS = new Set(['lava', 'fire', 'soul_fire', 'magma_block'])

const sleepTicks = n => new Promise(r => setTimeout(r, n * 50))

export class Reflexes {
  constructor (bot, opts) {
    this.bot = bot
    this.mode = opts.mode
    this.platform = opts.platform ?? null   // Sumo: {min, max} top surface of the platform
    this.arena = opts.arena ?? null         // Block UHC: {floor_y, min:[x,y,z], max:[x,y,z]} interior bounds
    this.reset()
  }

  reset () {
    this.intent = 'hold'; this.intentTick = 0; this.lastAttackTick = -100; this.sprintResetTick = -1
    this.frozen = true; this.events = []
    this.cancelJob(); this.jobDone = false; this.dodgeUntil = -1; this.dodgeDir = 'left'; this.equipping = false
    this.clearMoves()
  }

  setIntent (intent, tick) {
    if (intent !== this.intent) { this.cancelJob(); this.jobDone = false }
    this.intent = intent; this.intentTick = tick
  }

  // Called once per physics tick with the opponent entity (may be null).
  tick (tick, opp) {
    const bot = this.bot
    if (this.frozen) { this.clearMoves(); this.cancelJob(); return }

    if (this.mode === 'block_uhc') this.bucketGuard(tick)
    if (this.job) return   // a multi-tick action owns the body until it finishes or the intent changes
    if (!opp) { this.clearMoves(); return }

    const dist = bot.entity.position.distanceTo(opp.position)

    if (this.mode === 'block_uhc' && JOB_INTENTS.has(this.intent) && !this.jobDone) {
      this.startJob(tick, opp)
      return
    }

    // Reflex: aim at the opponent's head.
    bot.lookAt(opp.position.offset(0, opp.height * 0.9, 0), true)
    if (this.mode === 'block_uhc') this.ensureHeld('diamond_sword')

    // Intent: movement.
    this.clearMoves()
    this.move(tick, dist)

    // Reflex: arrow dodge (Block UHC). A short sidestep when an arrow is heading for us.
    if (this.mode === 'block_uhc') this.arrowDodge(tick)

    // Reflex: edge guard (Sumo). Never walk off the platform unless rushing an opponent in reach.
    if (this.platform && !(this.intent === 'rush' && dist <= REACH) && this.headingOffPlatform()) this.clearMoves()
    // Reflex: lava guard (Block UHC). Never walk into lava or fire.
    if (this.mode === 'block_uhc' && this.headingIntoHazard()) this.clearMoves()

    // Reflex: swing when in reach and the intent allows attacking.
    const cooldown = this.mode === 'block_uhc' ? SWORD_COOLDOWN : ATTACK_COOLDOWN
    if (ATTACKING_INTENTS.has(this.intent) && dist <= REACH && tick - this.lastAttackTick >= cooldown) {
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
      default:
        break
    }
  }

  // ----- Block UHC multi-tick actions -----

  startJob (tick, opp) {
    const run = { cancelled: false }
    this.job = run
    const done = () => { if (this.job === run) { this.job = null; this.jobDone = this.intent !== 'shoot_bow' } }
    const body = {
      shoot_bow: () => this.jobShoot(run, opp),
      place_wall: () => this.jobWall(run, opp),
      pillar_up: () => this.jobPillar(run),
      bucket_water: () => this.jobWater(run),
      bucket_lava: () => this.jobLava(run, opp)
    }[this.intent]
    this.clearMoves()
    body().catch(e => this.events.push({ tick, event: 'action_failed', action: this.intent, error: String(e.message ?? e).slice(0, 80) })).finally(done)
  }

  cancelJob () { if (this.job) { this.job.cancelled = true; this.job = null } }

  item (name) { return this.bot.inventory.items().find(i => i.name === name) ?? null }

  async equipItem (name) {
    const it = this.item(name)
    if (!it) throw new Error(`no ${name}`)
    if (this.bot.heldItem?.name !== name) await this.bot.equip(it, 'hand')
  }

  // Fire-and-forget: keep the sword in hand during melee intents.
  ensureHeld (name) {
    if (this.equipping || this.bot.heldItem?.name === name) return
    const it = this.item(name)
    if (!it) return
    this.equipping = true
    this.bot.equip(it, 'hand').catch(() => {}).finally(() => { this.equipping = false })
  }

  aimAt (target, lead = 0) {
    const bot = this.bot
    const d = bot.entity.position.distanceTo(target.position)
    const future = target.position.plus(target.velocity.scaled(lead * d))
    return bot.lookAt(future.offset(0, 1.6 + d * d * 0.006, 0), true)
  }

  async jobShoot (run, opp) {
    const bot = this.bot
    if (!this.item('arrow')) throw new Error('no arrows')
    await this.equipItem('bow')
    await this.aimAt(opp)
    bot.activateItem()
    await sleepTicks(20)
    if (run.cancelled) { bot.deactivateItem(); return }
    const live = bot.players[opp.username]?.entity ?? opp
    await this.aimAt(live, 3)
    bot.deactivateItem()
    this.events.push({ tick: 0, event: 'shot_arrow' })
    await sleepTicks(4)
    if (!run.cancelled) await this.equipItem('diamond_sword').catch(() => {})
  }

  async jobWall (run, opp) {
    const bot = this.bot
    await this.equipItem('cobblestone')
    const p = bot.entity.position
    const dir = opp.position.minus(p); dir.y = 0
    const n = dir.norm() || 1
    const ux = dir.x / n, uz = dir.z / n
    const px = -uz, pz = ux
    const floorY = this.arena ? this.arena.floor_y - 1 : Math.floor(p.y) - 1
    const cx = Math.floor(p.x + ux * 2), cz = Math.floor(p.z + uz * 2)
    for (const k of [0, -1, 1]) {
      if (run.cancelled) return
      const x = Math.floor(cx + px * k + 0.5), z = Math.floor(cz + pz * k + 0.5)
      const floor = bot.blockAt(new Vec3(x, floorY, z))
      if (!floor || floor.name === 'air') continue
      let base = floor
      for (let h = 0; h < 2; h++) {
        if (run.cancelled) return
        const above = bot.blockAt(base.position.offset(0, 1, 0))
        if (above && above.name !== 'air' && above.name !== 'water') { base = above; continue }
        try { await bot.placeBlock(base, UP) } catch { /* a bot stood there or the server refused; try the next cell */ break }
        base = bot.blockAt(base.position.offset(0, 1, 0))
      }
    }
    if (!run.cancelled) await this.equipItem('diamond_sword').catch(() => {})
  }

  async jobPillar (run) {
    const bot = this.bot
    await this.equipItem('cobblestone')
    const maxY = this.arena ? this.arena.floor_y + 3 : bot.entity.position.y + 3
    for (let n = 0; n < 3 && !run.cancelled && bot.entity.position.y < maxY; n++) {
      const y0 = bot.entity.position.y
      bot.setControlState('jump', true)
      let placed = false
      for (let i = 0; i < 16 && !placed && !run.cancelled; i++) {
        await sleepTicks(1)
        if (bot.entity.position.y > y0 + 1.0) {
          bot.setControlState('jump', false)
          const under = bot.blockAt(bot.entity.position.offset(0, -2, 0))
          try { await bot.lookAt(under.position.offset(0.5, 1, 0.5), true); await bot.placeBlock(under, UP); placed = true } catch { /* missed the window */ }
        }
      }
      bot.setControlState('jump', false)
      await sleepTicks(4)
    }
    if (!run.cancelled) await this.equipItem('diamond_sword').catch(() => {})
  }

  async jobWater (run) {
    const bot = this.bot
    await this.equipItem('water_bucket')
    const feet = bot.blockAt(bot.entity.position.offset(0, -1, 0))
    await bot.lookAt(feet.position.offset(0.5, 1, 0.5), true)
    bot.activateItem()
    this.events.push({ tick: 0, event: 'placed_water' })
    for (let i = 0; i < 40 && !run.cancelled; i++) await sleepTicks(1)
    if (run.cancelled) return
    const here = bot.entity.position
    const water = [here, here.offset(1, 0, 0), here.offset(-1, 0, 0), here.offset(0, 0, 1), here.offset(0, 0, -1)].map(v => bot.blockAt(v)).find(b => b?.name === 'water')
    if (water && this.item('bucket')) {
      await this.equipItem('bucket')
      await bot.lookAt(water.position.offset(0.5, 0.5, 0.5), true)
      bot.activateItem()
      await sleepTicks(2)
    }
    await this.equipItem('diamond_sword').catch(() => {})
  }

  async jobLava (run, opp) {
    const bot = this.bot
    await this.equipItem('lava_bucket')
    const p = bot.entity.position
    const dir = opp.position.minus(p); dir.y = 0
    const n = dir.norm() || 1
    const floorY = this.arena ? this.arena.floor_y - 1 : Math.floor(p.y) - 1
    const spot = bot.blockAt(new Vec3(Math.floor(p.x + dir.x / n * 2), floorY, Math.floor(p.z + dir.z / n * 2)))
    if (spot) {
      await bot.lookAt(spot.position.offset(0.5, 1, 0.5), true)
      bot.activateItem()
      this.events.push({ tick: 0, event: 'placed_lava' })
    }
    await sleepTicks(2)
    // Two steps back, away from what we just poured.
    bot.setControlState('back', true)
    for (let i = 0; i < 10 && !run.cancelled; i++) await sleepTicks(1)
    bot.setControlState('back', false)
    await this.equipItem('diamond_sword').catch(() => {})
  }

  // ----- Block UHC reflexes -----

  // Standing in lava or fire with a water bucket: pour it at our feet, whatever the intent.
  bucketGuard (tick) {
    const bot = this.bot
    if (this.guarding || this.job?.guard) return
    const here = bot.blockAt(bot.entity.position)?.name
    const below = bot.blockAt(bot.entity.position.offset(0, -1, 0))?.name
    const burning = HAZARDS.has(here) || here === 'fire' || (below === 'lava')
    if (!burning || !this.item('water_bucket')) return
    const run = { cancelled: false, guard: true }
    this.cancelJob(); this.job = run; this.guarding = true
    this.clearMoves()
    this.events.push({ tick, event: 'bucket_guard' })
    this.jobWater(run).catch(() => {}).finally(() => { if (this.job === run) this.job = null; this.guarding = false; this.jobDone = false })
  }

  headingIntoHazard () {
    const p = this.bot.entity.position
    const v = this.bot.entity.velocity
    const speed = Math.hypot(v.x, v.z)
    if (speed < 0.02) return false
    const ahead = p.offset(v.x / speed * (speed * 3 + 0.6), 0, v.z / speed * (speed * 3 + 0.6))
    for (const dy of [0, -1]) {
      const b = this.bot.blockAt(ahead.offset(0, dy, 0))
      if (b && HAZARDS.has(b.name)) return true
    }
    return false
  }

  arrowDodge (tick) {
    const bot = this.bot
    if (tick < this.dodgeUntil) { this.clearMoves(); bot.setControlState(this.dodgeDir, true); return }
    const me = bot.entity.position.offset(0, 0.9, 0)
    for (const e of Object.values(bot.entities)) {
      if (e.name !== 'arrow' || !e.velocity) continue
      const rel = me.minus(e.position)
      const d = rel.norm()
      if (d > 12 || d < 0.5) continue
      const speed = e.velocity.norm()
      if (speed < 0.3) continue
      const along = rel.dot(e.velocity) / speed
      if (along <= 0) continue                                  // flying away
      const miss = Math.sqrt(Math.max(0, d * d - along * along)) // closest approach to us
      if (miss > 1.2) continue
      const cross = e.velocity.x * rel.z - e.velocity.z * rel.x
      this.dodgeDir = cross > 0 ? 'left' : 'right'
      this.dodgeUntil = tick + 4
      this.events.push({ tick, event: 'dodged_arrow' })
      this.clearMoves(); bot.setControlState(this.dodgeDir, true)
      return
    }
  }

  // Nearest lava or fire within 4 blocks, for the state: {kind, distance, direction}
  nearestHazard () {
    const bot = this.bot
    const p = bot.entity.position
    let best = null
    for (let dx = -4; dx <= 4; dx++) for (let dz = -4; dz <= 4; dz++) for (let dy = -1; dy <= 1; dy++) {
      const b = bot.blockAt(p.offset(dx, dy, dz))
      if (!b || !HAZARDS.has(b.name)) continue
      const d = Math.hypot(dx, dy, dz)
      if (!best || d < best.distance) best = { kind: b.name === 'magma_block' ? 'magma' : b.name.replace('soul_', ''), distance: Math.round(d * 10) / 10, direction: this.relativeDirection(dx, dz) }
    }
    return best
  }

  relativeDirection (dx, dz) {
    const yaw = this.bot.entity.yaw   // mineflayer yaw: 0 = +z? use the forward vector instead
    const fx = -Math.sin(yaw), fz = -Math.cos(yaw)
    const dot = fx * dx + fz * dz
    const cross = fx * dz - fz * dx
    if (Math.abs(dot) >= Math.abs(cross)) return dot >= 0 ? 'ahead' : 'behind'
    return cross > 0 ? 'left' : 'right'
  }

  // ----- Sumo reflex -----

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

  clearMoves () { if (typeof this.bot.setControlState !== 'function') return; for (const m of ALL_MOVES) this.bot.setControlState(m, false) }

  drainEvents () { const e = this.events; this.events = []; return e }
}
