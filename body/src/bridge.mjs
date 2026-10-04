// Websocket bridge between one body and the harness. Newline-delimited JSON, one message per line.
// The harness connects as a client; the body is the server so the harness can start it and wait for the port.
import { WebSocketServer } from 'ws'

export class Bridge {
  constructor (port, onMessage) {
    this.clients = new Set()
    this.wss = new WebSocketServer({ host: '127.0.0.1', port })
    this.wss.on('connection', ws => {
      this.clients.add(ws)
      ws.on('message', data => {
        for (const line of data.toString().split('\n')) {
          if (!line.trim()) continue
          let msg
          try { msg = JSON.parse(line) } catch { this.send({ type: 'error', error: 'bad json' }); continue }
          onMessage(msg)
        }
      })
      ws.on('close', () => this.clients.delete(ws))
    })
  }

  send (msg) {
    const line = JSON.stringify(msg) + '\n'
    for (const ws of this.clients) if (ws.readyState === ws.OPEN) ws.send(line)
  }

  close () { for (const ws of this.clients) ws.close(); this.wss.close() }
}
