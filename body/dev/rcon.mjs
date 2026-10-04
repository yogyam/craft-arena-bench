// Minimal RCON client (Source RCON protocol, as used by Minecraft). Dev use only.
import net from 'node:net'

export class Rcon {
  constructor (host, port, password) { Object.assign(this, { host, port, password, id: 0, pending: new Map(), buf: Buffer.alloc(0) }) }
  connect () {
    return new Promise((resolve, reject) => {
      this.sock = net.createConnection({ host: this.host, port: this.port }, async () => {
        try { await this.#send(3, this.password); resolve(this) } catch (e) { reject(e) }
      })
      this.sock.on('error', reject)
      this.sock.on('data', d => this.#onData(d))
    })
  }
  #send (type, body) {
    const id = ++this.id
    const payload = Buffer.from(body, 'utf8')
    const pkt = Buffer.alloc(14 + payload.length)
    pkt.writeInt32LE(10 + payload.length, 0); pkt.writeInt32LE(id, 4); pkt.writeInt32LE(type, 8)
    payload.copy(pkt, 12); pkt.writeInt16LE(0, 12 + payload.length)
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      this.sock.write(pkt)
    })
  }
  #onData (d) {
    this.buf = Buffer.concat([this.buf, d])
    while (this.buf.length >= 4) {
      const len = this.buf.readInt32LE(0)
      if (this.buf.length < 4 + len) return
      const id = this.buf.readInt32LE(4)
      const body = this.buf.subarray(12, 4 + len - 2).toString('utf8')
      this.buf = this.buf.subarray(4 + len)
      const p = this.pending.get(id) ?? this.pending.get(this.id)
      if (id === -1) { for (const q of this.pending.values()) q.reject(new Error('RCON auth failed')); return }
      if (p) { this.pending.delete(id); p.resolve(body) }
    }
  }
  cmd (s) { return this.#send(2, s) }
  close () { this.sock.end() }
}
