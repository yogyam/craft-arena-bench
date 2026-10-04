// Starts two bodies, drives one with intents over the bridge, prints a few state lines, then quits both.
import { spawn } from 'node:child_process'
import WebSocket from 'ws'
import { Rcon } from './rcon.mjs'
const sleep = ms => new Promise(r => setTimeout(r, ms))
const start = (u, o, p) => spawn('node', ['src/main.mjs', '--username', u, '--opponent', o, '--ws-port', String(p)], { stdio: ['ignore', 'inherit', 'inherit'] })
const pa = start('BotA', 'BotB', 8701), pb = start('BotB', 'BotA', 8702)
await sleep(800)
const connect = p => new Promise(res => { const ws = new WebSocket(`ws://127.0.0.1:${p}`); ws.on('open', () => res(ws)) })
const [wa, wb] = await Promise.all([connect(8701), connect(8702)])
let latestA = null, latestB = null, nA = 0
wa.on('message', d => { for (const l of d.toString().split('\n')) if (l.trim()) { const m = JSON.parse(l); if (m.type === 'state') { latestA = m; nA++ } else console.log('A msg:', l.slice(0, 120)) } })
wb.on('message', d => { for (const l of d.toString().split('\n')) if (l.trim()) { const m = JSON.parse(l); if (m.type === 'state') latestB = m; else console.log('B msg:', l.slice(0, 120)) } })
await sleep(2500)
const rcon = await new Rcon('127.0.0.1', 25575, 'local-dev-only').connect()
await rcon.cmd('tp BotA 0 -60 0 -90 0'); await rcon.cmd('tp BotB 6 -60 0 90 0')
await rcon.cmd('effect give BotB minecraft:instant_health 1 5 true')
await sleep(500)
console.log('A sees:', JSON.stringify(latestA?.opponent)); console.log('B health:', latestB?.self.health, 'states/s from A so far:', (nA / 3).toFixed(1))
wa.send(JSON.stringify({ type: 'freeze', value: false }) + '\n'); wb.send(JSON.stringify({ type: 'freeze', value: false }) + '\n')
wa.send(JSON.stringify({ type: 'intent', intent: 'rush' }) + '\n')
for (let i = 0; i < 5; i++) { await sleep(600); console.log(`t+${(i + 1) * 0.6}s A pos ${latestA?.self.pos} dist ${latestA?.opponent?.distance} intent ${latestA?.intent} | B health ${latestB?.self.health} events ${JSON.stringify(latestB?.events)}`) }
wa.send(JSON.stringify({ type: 'intent', intent: 'retreat' }) + '\n'); await sleep(1000)
console.log(`after retreat: dist ${latestA?.opponent?.distance}`)
wa.send(JSON.stringify({ type: 'quit' }) + '\n'); wb.send(JSON.stringify({ type: 'quit' }) + '\n')
rcon.close(); await sleep(500); pa.kill(); pb.kill(); process.exit(0)
