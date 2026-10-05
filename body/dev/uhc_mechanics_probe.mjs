// Block UHC mechanics in isolation: equip, draw and release a bow at a target, place a block on the floor, pillar up, water and lava buckets.
import mineflayer from 'mineflayer'
import { Vec3 } from 'vec3'
import { Rcon } from './rcon.mjs'
const sleep = ms => new Promise(r => setTimeout(r, ms))
const rcon = await new Rcon('127.0.0.1', 25575, 'local-dev-only').connect()
const say = async c => { const r = await rcon.cmd(c); return r.trim() }
const mk = u => { const b = mineflayer.createBot({ host: '127.0.0.1', port: 25565, username: u, version: '26.1', auth: 'offline' }); return new Promise(r => b.once('spawn', () => r(b))) }
const [A, B] = await Promise.all([mk('ProbeA'), mk('ProbeB')])
await sleep(800)
// Arena patch: stone floor at y=-61 from x,z in [30,60], clear above
await say('fill 30 -61 30 60 -61 60 stone'); await say('fill 30 -60 30 60 -50 60 air')
await say('gamerule fall_damage false')
for (const c of ['gamemode survival ProbeA', 'gamemode survival ProbeB', 'clear ProbeA', 'clear ProbeB', 'effect clear ProbeA', 'effect clear ProbeB',
  'effect give ProbeA instant_health 1 5 true', 'effect give ProbeB instant_health 1 5 true', 'effect give ProbeB resistance infinite 4 true',
  'give ProbeA diamond_sword', 'give ProbeA bow', 'give ProbeA arrow 16', 'give ProbeA water_bucket', 'give ProbeA lava_bucket', 'give ProbeA cobblestone 64',
  'tp ProbeA 40.5 -60 40.5 -90 0', 'tp ProbeB 50.5 -60 40.5 90 0']) await say(c)
await sleep(1200)
const inv = () => Object.fromEntries(A.inventory.items().map(i => [i.name, i.count]))
console.log('A inventory:', inv(), 'held:', A.heldItem?.name)
const item = n => A.inventory.items().find(i => i.name === n)

// 1. Equip sword then bow
await A.equip(item('diamond_sword'), 'hand'); console.log('equipped:', A.heldItem?.name)
await A.equip(item('bow'), 'hand'); console.log('equipped:', A.heldItem?.name)

// 2. Draw and release at B (10 blocks away)
const target = () => A.players.ProbeB?.entity
let arrowsSeen = 0
A.on('entitySpawn', e => { if (e.name === 'arrow') arrowsSeen++ })
let bHurt = 0; B.on('entityHurt', e => { if (e === B.entity) bHurt++ })
for (let shot = 0; shot < 3; shot++) {
  const t = target(); const d = A.entity.position.distanceTo(t.position)
  await A.lookAt(t.position.offset(0, 1.6 + d * d * 0.006, 0), true)
  A.activateItem()                      // start drawing
  await sleep(1100)                      // full charge
  await A.lookAt(target().position.offset(0, 1.6 + d * d * 0.006, 0), true)
  A.deactivateItem()                     // release
  await sleep(900)
}
console.log(`bow: arrows left ${inv().arrow}, arrow entities seen ${arrowsSeen}, B hurt events ${bHurt}, B health ${B.health}`)

// 3. Place a block on the floor two blocks ahead (toward +x)
await A.equip(item('cobblestone'), 'hand')
const p = A.entity.position
const floorAhead = A.blockAt(new Vec3(Math.floor(p.x) + 2, -61, Math.floor(p.z)))
try { await A.placeBlock(floorAhead, new Vec3(0, 1, 0)); console.log('placeBlock on floor ok:', A.blockAt(floorAhead.position.offset(0, 1, 0))?.name) } catch (e) { console.log('placeBlock failed:', e.message) }
// second row on top of it
try { await A.placeBlock(A.blockAt(floorAhead.position.offset(0, 1, 0)), new Vec3(0, 1, 0)); console.log('second row ok:', A.blockAt(floorAhead.position.offset(0, 2, 0))?.name) } catch (e) { console.log('second row failed:', e.message) }

// 4. Pillar up once: jump, place block under feet
const y0 = A.entity.position.y
A.setControlState('jump', true)
let placed = false
for (let i = 0; i < 20 && !placed; i++) {
  await sleep(50)
  if (A.entity.position.y > y0 + 1.0) {
    A.setControlState('jump', false)
    const under = A.blockAt(A.entity.position.offset(0, -2, 0))
    try { await A.lookAt(under.position.offset(0.5, 1, 0.5), true); await A.placeBlock(under, new Vec3(0, 1, 0)); placed = true } catch (e) { console.log('pillar place failed:', e.message) }
  }
}
A.setControlState('jump', false); await sleep(400)
console.log(`pillar: placed ${placed}, y ${y0.toFixed(1)} -> ${A.entity.position.y.toFixed(1)}, block under feet ${A.blockAt(A.entity.position.offset(0, -1, 0))?.name}`)

// 5. Water bucket at feet, then pick it back up
await A.equip(item('water_bucket'), 'hand')
const feet = A.blockAt(A.entity.position.offset(0, -1, 0))
await A.lookAt(feet.position.offset(0.5, 1, 0.5), true); A.activateItem(); await sleep(300)
console.log('after water use: held', A.heldItem?.name, '| block at feet:', A.blockAt(A.entity.position)?.name, '| adjacent water:', ['water'].includes(A.blockAt(A.entity.position.offset(1, 0, 0))?.name))
await sleep(500)
const waterBlock = [A.entity.position, A.entity.position.offset(1, 0, 0), A.entity.position.offset(-1, 0, 0), A.entity.position.offset(0, 0, 1), A.entity.position.offset(0, 0, -1)].map(v => A.blockAt(v)).find(b => b?.name === 'water')
if (waterBlock) { await A.equip(item('bucket'), 'hand'); await A.lookAt(waterBlock.position.offset(0.5, 0.5, 0.5), true); A.activateItem(); await sleep(300); console.log('after pickup: held', A.heldItem?.name, 'water still there:', A.blockAt(waterBlock.position)?.name) } else console.log('no water found to pick up')

// 6. Lava bucket two blocks toward B
await A.equip(item('lava_bucket'), 'hand')
const lavaSpot = A.blockAt(new Vec3(Math.floor(A.entity.position.x) + 3, -61, Math.floor(A.entity.position.z) + 1))
await A.lookAt(lavaSpot.position.offset(0.5, 1, 0.5), true); A.activateItem(); await sleep(300)
console.log('after lava use: held', A.heldItem?.name, '| block above spot:', A.blockAt(lavaSpot.position.offset(0, 1, 0))?.name)

await say('fill 30 -60 30 60 -50 60 air'); await say('kill @e[type=arrow]'); await say('kill @e[type=item]')
A.quit(); B.quit(); rcon.close(); await sleep(300); process.exit(0)
